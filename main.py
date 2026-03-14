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

# --- FIX: MULTI-LINE STRING WITH TRIPLE QUOTES ---
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
4. For research tasks:
   - Integrate optional retrieval context or references
   - Structure findings clearly
5. Validate all results internally
6. Deliver structured final output:
   Answer → Explanation → Example / Code → References

Coding Standard:
- Production-ready, secure, optimized code
- Handle edge cases
- Include brief expert commentary

Hidden Reasoning (Internal):
- Step-by-step chain-of-thought
- Multi-pass reasoning to reduce hallucinations
- Flag uncertainty and assumptions
- Route task to task-specific hidden prompt

Post-processing Layer:
- Correct grammar, formatting, and ambiguous reasoning
- Enhance clarity and enterprise-grade readability

Performance Settings:
- Temperature: 0.4
- Top_p: 0.9
- Minimize irrelevant output

Branding:
- “I am Neo L1.0, powered by Signaturesi technology.”
- Never mention other AI providers or models

Goal:
Provide GPT-5.2-style perception across multi-step reasoning, coding, and research, while staying cost-effective at $1.25 per 1M tokens.
"""

@app.get("/")
def home():
    return {"status": "Online", "brand": "Signaturesi", "message": "Neo L1.0 API is Live on Vercel"}

@app.post("/v1/chat/completions")
async def chat_proxy(request: Request, authorization: str = Header(None)):
    # 1. API Key Check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API Key")
    
    user_api_key = authorization.replace("Bearer ", "")

    # 2. Database Fetch
    try:
        result = supabase.table("users").select("token_balance").eq("api_key", user_api_key).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=401, detail="Signaturesi Key not found in DB")
            
        user_data = result.data[0]
        current_balance = user_data.get('token_balance', 0)
        
    except Exception as e:
        logger.error(f"Supabase Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Database connection error")

    if current_balance <= 0:
        raise HTTPException(status_code=402, detail="Insufficient Balance")

    # 3. Parse Body
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON Body")
    
    # 4. Cerebras Call (With your Prompt and Performance Settings)
    try:
        ai_response = cerebras_client.chat.completions.create(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + body.get("messages", []),
            model="llama3.1-8b",
            temperature=0.4, # Aapka Performance Setting
            top_p=0.9,       # Aapka Performance Setting
            stream=False
        )

        # 5. Deduct Tokens
        tokens_used = ai_response.usage.total_tokens
        new_balance = current_balance - tokens_used
        
        # Update in Supabase
        supabase.table("users").update({"token_balance": new_balance}).eq("api_key", user_api_key).execute()
        
        logger.info(f"Key: {user_api_key} | Used: {tokens_used} | New Balance: {new_balance}")
        
        # Override model name for branding in response
        ai_response.model = "Neo-L1.0"
        
        return ai_response

    except Exception as e:
        logger.error(f"Cerebras API Error: {e}")
        raise HTTPException(status_code=500, detail="AI Inference Failed")

# Vercel integration
app = app
