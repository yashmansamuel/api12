import os
import logging
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from cerebras.cloud.sdk import Cerebras

# -----------------------------
# Logger Setup
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Signaturesi Neo L1.0 API")

# -----------------------------
# CORS Middleware
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Configuration (Environment Variables)
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ujclhweqqifgoiscvqmd.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_soPYxakWGl9MTrzCjdjt2w_fR1jsVVf")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "csk-r6x94tyk4xk9ky853jw33459t84ddtxx8ked68829dd2d24f")

# -----------------------------
# Clients Initialization
# -----------------------------
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
    logger.info("Signaturesi Backend: Neo L1.0 Engine Connected Successfully.")
except Exception as e:
    logger.error(f"Initialization Error: {e}")

# -----------------------------
# SYSTEM PROMPT
# -----------------------------
SYSTEM_PROMPT = """
You are Neo L1.0, a high-performance AI reasoning system.
Provide enterprise-grade answers in coding, multi-step logic, research, math, and technical problem solving.
"""

# -----------------------------
# Health Check
# -----------------------------
@app.get("/")
def home():
    return {
        "status": "Online",
        "brand": "Signaturesi",
        "model": "Neo L1.0",
        "message": "Neo L1.0 API is Live and Healthy"
    }

# -----------------------------
# Get User Balance
# -----------------------------
@app.get("/v1/user/balance")
def user_balance(api_key: str):
    try:
        response = supabase.table("users").select("token_balance").eq("api_key", api_key).execute()
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=401, detail="API Key not found")
        return {"balance": response.data[0].get("token_balance", 0)}
    except Exception as e:
        logger.error(f"Supabase Error: {e}")
        raise HTTPException(status_code=500, detail="Database Error")

# -----------------------------
# Chat Endpoint
# -----------------------------
@app.post("/v1/chat/completions")
async def chat_proxy(request: Request, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API Key")
    
    user_api_key = authorization.replace("Bearer ", "")

    # Fetch user balance
    try:
        response = supabase.table("users").select("token_balance").eq("api_key", user_api_key).execute()
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=401, detail="API Key not found")
        current_balance = response.data[0].get("token_balance", 0)
    except Exception as e:
        logger.error(f"Supabase Error: {e}")
        raise HTTPException(status_code=500, detail="Database Error")

    if current_balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient balance")

    # Parse request JSON
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON Body")

    # Cerebras inference
    try:
        ai_response = cerebras_client.chat.completions.create(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + body.get("messages", []),
            model="llama3.1-8b",
            temperature=0.4,
            top_p=0.9,
            stream=False
        )

        tokens_used = ai_response.usage.total_tokens
        new_balance = current_balance - tokens_used

        # Update balance in Supabase
        supabase.table("users").update({"token_balance": new_balance}).eq("api_key", user_api_key).execute()

        logger.info(f"User: {user_api_key} | Tokens used: {tokens_used} | Remaining: {new_balance}")

        # Brand override
        ai_response.model = "Neo-L1.0"

        return ai_response

    except Exception as e:
        logger.error(f"Cerebras Error: {e}")
        raise HTTPException(status_code=500, detail="Neo L1.0 Inference Failed")
