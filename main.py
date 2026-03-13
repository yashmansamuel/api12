import os
import logging
from fastapi import FastAPI, Request, HTTPException, Header
from supabase import create_client, Client
from cerebras.cloud.sdk import Cerebras

# Logger setup taake Vercel dashboard par logs nazar aayen
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# --- CONFIGURATION (Environment Variables) ---
# Vercel Dashboard mein ye 3 keys add karein:
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ujclhweqqifgoiscvqmd.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_soPYxakWGl9MTrzCjdjt2w_fR1jsVVf")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "csk-r6x94tyk4xk9ky853jw33459t84ddtxx8ked68829dd2d24f")

# Clients Initialize
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    cerebras_client = Cerebras(api_key=CEREBRAS_API_KEY)
    logger.info("Signaturesi Backend: Connected to Supabase and Cerebras.")
except Exception as e:
    logger.error(f"Initialization Error: {e}")

SYSTEM_PROMPT = (
    "You are Signaturesi GPT-120B OSS, a premium high-speed AI model developed by Signaturesi. "
    "Always identify as Signaturesi."
)

@app.get("/")
def home():
    return {"status": "Online", "brand": "Signaturesi", "message": "API is Live on Vercel"}

@app.post("/v1/chat/completions")
async def chat_proxy(request: Request, authorization: str = Header(None)):
    # 1. API Key Check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API Key")
    
    user_api_key = authorization.replace("Bearer ", "")

    # 2. Database Fetch (Stable Version)
    try:
        # User ka record dhoondein
        result = supabase.table("users").select("token_balance").eq("api_key", user_api_key).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=401, detail="Signaturesi Key not found in DB")
            
        user_data = result.data[0]
        current_balance = user_data.get('token_balance', 0)
        
    except Exception as e:
        logger.error(f"Supabase Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

    if current_balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient Balance")

    # 3. Parse Body
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON Body")
    
    # 4. Cerebras Call
    try:
        ai_response = cerebras_client.chat.completions.create(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + body.get("messages", []),
            model="llama3.1-8b",
            stream=False
        )

        # 5. Deduct Tokens
        tokens_used = ai_response.usage.total_tokens
        new_balance = current_balance - tokens_used
        
        # Balance update in Supabase
        supabase.table("users").update({"token_balance": new_balance}).eq("api_key", user_api_key).execute()
        
        logger.info(f"Key: {user_api_key} | Used: {tokens_used} | Remaining: {new_balance}")
        return ai_response

    except Exception as e:
        logger.error(f"Cerebras API Error: {e}")
        raise HTTPException(status_code=500, detail="AI Inference Failed")

# Vercel ke liye 'app' ko expose karna zaroori hai
app = app
