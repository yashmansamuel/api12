import os
import logging
import secrets
import string
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from supabase import create_client, Client
from cerebras.cloud.sdk import Cerebras

# 1. Logger Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# 2. CORS SETTINGS (Sab se zaroori - is se Network Error khatam hoga)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ujclhweqqifgoiscvqmd.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_soPYxakWGl9MTrzCjdjt2w_fR1jsVVf")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "csk-r6x94tyk4xk9ky853jw33459t84ddtxx8ked68829dd2d24f")
ADMIN_SECRET_PASS = "signaturesi_boss_786"

# 4. Clients Initialization
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
    logger.info("Signaturesi Backend: Neo L1.0 Engine Connected Successfully.")
except Exception as e:
    logger.error(f"Initialization Error: {e}")

SYSTEM_PROMPT = "You are Neo L1.0, developed and optimized by the Signaturesi Team."

# -----------------------------
# ROUTES
# -----------------------------

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    try:
        with open("dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "<h1>Signaturesi: Dashboard File Not Found</h1>"

@app.get("/admin/generate-key")
def create_user(tokens: int, admin_pass: str):
    if admin_pass != ADMIN_SECRET_PASS:
        raise HTTPException(status_code=403, detail="Unauthorized Admin Access")
    random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    new_key = f"sig-live-{random_part}"
    supabase.table("users").insert({"api_key": new_key, "token_balance": tokens}).execute()
    return {"new_api_key": new_key, "tokens": tokens}

@app.get("/v1/user/balance")
async def get_balance(api_key: str):
    try:
        response = supabase.table("users").select("token_balance").eq("api_key", api_key).execute()
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Key not found")
        
        # Proper way to get balance from list
        user_record = response.data[0]
        return {"balance": user_record.get('token_balance', 0), "model": "Neo L1.0"}
    except Exception as e:
        logger.error(f"Balance Fetch Error: {e}")
        raise HTTPException(status_code=500, detail="Database Error")

@app.post("/v1/chat/completions")
async def chat_proxy(request: Request, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API Key")
    
    user_api_key = authorization.replace("Bearer ", "")
    response = supabase.table("users").select("token_balance").eq("api_key", user_api_key).execute()
    
    if not response.data or len(response.data) == 0:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    current_balance = response.data[0].get('token_balance', 0)
    if current_balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient Balance")

    body = await request.json()
    ai_response = cerebras_client.chat.completions.create(
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + body.get("messages", []),
        model="llama3.1-8b",
        temperature=0.4,
        stream=False
    )

    tokens_used = ai_response.usage.total_tokens
    new_balance = current_balance - tokens_used
    supabase.table("users").update({"token_balance": new_balance}).eq("api_key", user_api_key).execute()
    
    ai_response.model = "Neo-L1.0"
    return ai_response

app = app
