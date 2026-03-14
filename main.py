import os
import logging
import secrets
import string
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from supabase import create_client, Client
from cerebras.cloud.sdk import Cerebras

# -------------------------
# 1️⃣ Logger Setup
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# 2️⃣ FastAPI App + CORS
# -------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # * sab domains allow karega
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional: Explicit CORS headers for Vercel / serverless fallback
@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    return response

# -------------------------
# 3️⃣ Configuration
# -------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ujclhweqqifgoiscvqmd.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_soPYxakWGl9MTrzCjdjt2w_fR1jsVVf")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "csk-r6x94tyk4xk9ky853jw33459t84ddtxx8ked68829dd2d24f")
ADMIN_SECRET_PASS = os.getenv("ADMIN_SECRET_PASS", "signaturesi_boss_786")

# -------------------------
# 4️⃣ Clients Initialization
# -------------------------
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
    logger.info("Neo L1.0 Engine: Online & Connected.")
except Exception as e:
    logger.error(f"Initialization Error: {e}")

# -------------------------
# 5️⃣ System Prompt (Neo L1.0)
# -------------------------
SYSTEM_PROMPT = """
You are Neo L1.0, developed by Signaturesi Team. High-speed reasoning engine.
Mission: Enterprise-grade answers in coding, multi-step logic, research, math, and technical problem solving.
Style: Concise, accurate, structured, and professional.
Branding: I am Neo L1.0, powered by Signaturesi technology. Never mention other AI models.
"""

# -------------------------
# 6️⃣ Dashboard Route
# -------------------------
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    try:
        with open("dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "<h1>Dashboard File Not Found</h1>"

# -------------------------
# 7️⃣ Get User Balance
# -------------------------
@app.get("/v1/user/balance")
async def get_balance(api_key: str):
    try:
        res = supabase.table("users").select("token_balance").eq("api_key", api_key).execute()
        if not res.data or len(res.data) == 0:
            raise HTTPException(status_code=404, detail="Key not found")
        balance = res.data[0].get('token_balance', 0)
        return {"balance": balance, "model": "Neo-L1.0"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Balance Error: {e}")
        raise HTTPException(status_code=500, detail="Database Error")

# -------------------------
# 8️⃣ Admin Key Generator
# -------------------------
@app.get("/admin/generate-key")
def create_user(tokens: int, admin_pass: str):
    if admin_pass != ADMIN_SECRET_PASS:
        raise HTTPException(status_code=403, detail="Unauthorized")
    random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    new_key = f"sig-live-{random_part}"
    try:
        supabase.table("users").insert({"api_key": new_key, "token_balance": tokens}).execute()
    except Exception as e:
        logger.error(f"Admin Key Insert Error: {e}")
        raise HTTPException(status_code=500, detail="DB Insert Failed")
    return {"new_api_key": new_key, "tokens": tokens}

# -------------------------
# 9️⃣ Chat Endpoint
# -------------------------
@app.post("/v1/chat/completions")
async def chat_proxy(request: Request, authorization: str = Header(None)):
    # 1. Check Authorization Header
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API Key")
    user_api_key = authorization.replace("Bearer ", "")

    # 2. Fetch User Token Balance
    try:
        res = supabase.table("users").select("token_balance").eq("api_key", user_api_key).execute()
        if not res.data or len(res.data) == 0:
            raise HTTPException(status_code=401, detail="Invalid API Key")
        current_balance = res.data[0].get('token_balance', 0)
    except Exception as e:
        logger.error(f"Supabase Error: {e}")
        raise HTTPException(status_code=500, detail="Database Error")

    if current_balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient Balance")

    # 3. Parse User Messages
    try:
        body = await request.json()
        user_messages = body.get("messages")
        if not user_messages:
            raise HTTPException(status_code=400, detail="Messages missing")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON Body")

    # 4. Cerebras Chat Call
    try:
        ai_response = cerebras_client.chat.completions.create(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + user_messages,
            model="llama3.1-8b",
            temperature=0.4,
            top_p=0.9,
            stream=False
        )
    except Exception as e:
        logger.error(f"Cerebras API Error: {e}")
        raise HTTPException(status_code=500, detail="AI Inference Failed")

    # 5. Deduct Tokens
    tokens_used = int(getattr(ai_response.usage, 'total_tokens', 0))
    new_balance = current_balance - tokens_used
    try:
        supabase.table("users").update({"token_balance": new_balance}).eq("api_key", user_api_key).execute()
    except Exception as e:
        logger.error(f"Token Deduction Error: {e}")

    # 6. Branding
    ai_response.model = "Neo-L1.0"
    return ai_response
