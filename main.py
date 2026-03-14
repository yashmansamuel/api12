import os
import logging
import secrets
import string
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from supabase import create_client, Client
from cerebras.cloud.sdk import Cerebras

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# 1. CORS Fix (Zaroori for Dashboard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Config
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ujclhweqqifgoiscvqmd.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_soPYxakWGl9MTrzCjdjt2w_fR1jsVVf")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "csk-r6x94tyk4xk9ky853jw33459t84ddtxx8ked68829dd2d24f")
ADMIN_SECRET_PASS = "signaturesi_boss_786"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
except Exception as e:
    logger.error(f"Init Error: {e}")

# 3. Routes
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    try:
        with open("dashboard.html", "r") as f:
            return f.read()
    except:
        return "<h1>Dashboard File Not Found</h1>"

@app.get("/v1/user/balance")
async def get_balance(api_key: str):
    try:
        res = supabase.table("users").select("token_balance").eq("api_key", api_key).execute()
        # FIX: Check if data exists and get the first item from the list
        if not res.data or len(res.data) == 0:
            raise HTTPException(status_code=404, detail="Key not found")
        
        balance = res.data[0].get('token_balance', 0)
        return {"balance": balance, "model": "Neo-L1.0"}
    except Exception as e:
        logger.error(f"Balance API Error: {e}")
        raise HTTPException(status_code=500, detail="Database Error")

@app.post("/v1/chat/completions")
async def chat_proxy(request: Request, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Key")
    user_api_key = authorization.replace("Bearer ", "")
    
    res = supabase.table("users").select("token_balance").eq("api_key", user_api_key).execute()
    if not res.data or len(res.data) == 0:
        raise HTTPException(status_code=401, detail="Invalid Key")
    
    current_balance = res.data[0].get('token_balance', 0)
    if current_balance <= 0:
        raise HTTPException(status_code=402, detail="No Balance")

    body = await request.json()
    ai_response = cerebras_client.chat.completions.create(
        messages=[{"role": "system", "content": "You are Neo L1.0 by Signaturesi."}] + body.get("messages", []),
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
