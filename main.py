import os
import logging
import secrets
import string
from fastapi import FastAPI, Request, HTTPException, Header
from supabase import create_client, Client
from cerebras.cloud.sdk import Cerebras

# -----------------------------
# Logger Setup
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# -----------------------------
# Configuration (Environment Variables)
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ujclhweqqifgoiscvqmd.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_soPYxakWGl9MTrzCjdjt2w_fR1jsVVf")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "csk-r6x94tyk4xk9ky853jw33459t84ddtxx8ked68829dd2d24f")

# Admin Password (Keys banane ke liye)
ADMIN_SECRET_PASS = "signaturesi_boss_786" 

# -----------------------------
# Clients Initialization
# -----------------------------
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
    logger.info("Signaturesi Backend: Neo L1.0 Engine Connected.")
except Exception as e:
    logger.error(f"Initialization Error: {e}")

# -----------------------------
# SYSTEM PROMPT (Neo L1.0 Premium)
# -----------------------------
SYSTEM_PROMPT = """
Role:
You are Neo L1.0, a high-performance AI reasoning system developed and hyper-optimized by the Signaturesi Team.

Mission:
Provide enterprise-grade answers in coding, multi-step logic, research, math, and technical problem solving.

Core Behavior:
- Accurate, structured, professional, and concise.
- Balance reasoning depth, research insight, and coding precision.
- Avoid filler words or fluff.

Reasoning Protocol:
1. Detect task type (coding / logic / research / analysis)
2. Break problem into internal logical steps
3. Perform multi-pass reasoning for consistency
4. Deliver structured final output:
   Answer → Explanation → Example / Code → References

Branding:
- "I am Neo L1.0, powered by Signaturesi technology."
- Never mention other AI providers or models.

Goal:
Provide GPT-5.2-style perception across multi-step reasoning, coding, and research, while staying cost-effective at $1.25 per 1M tokens.
"""

# -----------------------------
# Admin: Unique Key Generator
# -----------------------------
@app.get("/admin/generate-key")
def create_user(tokens: int, admin_pass: str):
    if admin_pass != ADMIN_SECRET_PASS:
        raise HTTPException(status_code=403, detail="Unauthorized Admin Access")
    
    # Random unique key generate karein
    random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    new_key = f"sig-live-{random_part}"
    
    try:
        supabase.table("users").insert({"api_key": new_key, "token_balance": tokens}).execute()
        return {
            "status": "Success",
            "new_api_key": new_key,
            "tokens_added": tokens,
            "brand": "Signaturesi",
            "model": "Neo L1.0"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# Health Check
# -----------------------------
@app.get("/")
def home():
    return {"status": "Online", "brand": "Signaturesi", "model": "Neo L1.0"}

# -----------------------------
# Chat Endpoint (Neo L1.0 Core)
# -----------------------------
@app.post("/v1/chat/completions")
async def chat_proxy(request: Request, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Signaturesi API Key")
    
    user_api_key = authorization.replace("Bearer ", "")

    # 1. Fetch Balance
    try:
        response = supabase.table("users").select("token_balance").eq("api_key", user_api_key).execute()
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=401, detail="Key not found")
        
        # Sahi tarika balance uthane ka
        current_balance = response.data[0].get('token_balance', 0)
    except HTTPException as e: raise e
    except Exception: raise HTTPException(status_code=500, detail="DB Error")

    if current_balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient Balance")

    # 2. Parse Body & AI Call
    body = await request.json()
    try:
        ai_response = cerebras_client.chat.completions.create(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + body.get("messages", []),
            model="llama3.1-8b",
            temperature=0.4,
            top_p=0.9,
            stream=False
        )

        # 3. Token Deduction
        tokens_used = ai_response.usage.total_tokens
        new_balance = current_balance - tokens_used
        supabase.table("users").update({"token_balance": new_balance}).eq("api_key", user_api_key).execute()
        
        # 4. Branding Override
        ai_response.model = "Neo-L1.0"
        return ai_response

    except Exception as e:
        logger.error(f"Inference Error: {e}")
        raise HTTPException(status_code=500, detail="Neo L1.0 Engine Failed")

app = app
