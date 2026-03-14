import os
import logging
import secrets
import string
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from supabase import create_client, Client
from cerebras.cloud.sdk import Cerebras

# ----------------- Logger Setup -----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------- FastAPI App -----------------
app = FastAPI()

# --- 1. FINAL CORS FIX (Network Error solve karne ke liye) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Development: allow all. In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Configuration -----------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ujclhweqqifgoiscvqmd.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_soPYxakWGl9MTrzCjdjt2w_fR1jsVVf")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "csk-r6x94tyk4xk9ky853jw33459t84ddtxx8ked68829dd2d24f")
ADMIN_SECRET_PASS = os.getenv("ADMIN_SECRET_PASS", "signaturesi_boss_786")  # use env for security

# ----------------- Initialize Clients -----------------
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
    logger.info("Supabase & Cerebras clients initialized successfully.")
except Exception as e:
    logger.error(f"Initialization Error: {e}")
    raise RuntimeError("Failed to initialize clients.") from e

# ----------------- 2. DASHBOARD ROUTE -----------------
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    try:
        with open("dashboard.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        logger.warning("dashboard.html file not found.")
        return "<h1>Signaturesi Dashboard File Not Found</h1>"
    except Exception as e:
        logger.error(f"Dashboard Error: {e}")
        return "<h1>Unexpected Error Loading Dashboard</h1>"

# ----------------- 3. BALANCE API -----------------
@app.get("/v1/user/balance")
async def get_balance(api_key: str):
    try:
        res = supabase.table("users").select("token_balance").eq("api_key", api_key).execute()
        if not res.data or len(res.data) == 0:
            logger.info(f"Balance check failed: API key not found -> {api_key}")
            raise HTTPException(status_code=404, detail="Key not found")
        
        balance = res.data[0].get('token_balance', 0)
        return {"balance": balance, "model": "Neo-L1.0"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Balance Error: {e}")
        raise HTTPException(status_code=500, detail="Database Error")

# ----------------- 4. ADMIN KEY GENERATOR -----------------
@app.get("/admin/generate-key")
def create_user(tokens: int, admin_pass: str):
    if admin_pass != ADMIN_SECRET_PASS:
        logger.warning("Unauthorized admin key generation attempt.")
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    new_key = f"sig-live-{random_part}"
    
    try:
        supabase.table("users").insert({"api_key": new_key, "token_balance": tokens}).execute()
        logger.info(f"New API key generated: {new_key} with {tokens} tokens.")
        return {"new_api_key": new_key, "tokens": tokens}
    except Exception as e:
        logger.error(f"Admin Key Insert Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create key")

# ----------------- 5. CHAT ENDPOINT -----------------
@app.post("/v1/chat/completions")
async def chat_proxy(request: Request, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("Missing authorization header in chat request.")
        raise HTTPException(status_code=401, detail="Missing Key")
    
    user_api_key = authorization.replace("Bearer ", "")
    
    try:
        res = supabase.table("users").select("token_balance").eq("api_key", user_api_key).execute()
        if not res.data or len(res.data) == 0:
            logger.info(f"Invalid API key attempted: {user_api_key}")
            raise HTTPException(status_code=401, detail="Invalid Key")
        
        current_balance = res.data[0].get('token_balance', 0)
        if current_balance <= 0:
            logger.info(f"No balance for API key: {user_api_key}")
            raise HTTPException(status_code=402, detail="No Balance")
        
        body = await request.json()
        messages = [{"role": "system", "content": "You are Neo L1.0 by Signaturesi."}] + body.get("messages", [])
        
        ai_response = cerebras_client.chat.completions.create(
            messages=messages,
            model="llama3.1-8b",
            temperature=0.4,
            stream=False
        )
        
        # Safely handle token usage
        tokens_used = getattr(getattr(ai_response, 'usage', None), 'total_tokens', 0)
        new_balance = max(0, current_balance - tokens_used)
        
        supabase.table("users").update({"token_balance": new_balance}).eq("api_key", user_api_key).execute()
        
        # Update model info
        setattr(ai_response, "model", "Neo-L1.0")
        
        logger.info(f"Chat completed for {user_api_key}. Tokens used: {tokens_used}, New balance: {new_balance}")
        return ai_response
    
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Chat Proxy Error: {e}")
        raise HTTPException(status_code=500, detail="Chat Service Error")
