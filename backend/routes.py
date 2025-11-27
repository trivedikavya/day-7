from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
import os
import requests
import json
import google.generativeai as genai
import assemblyai as aai
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

router = APIRouter()

# 1. CONFIGURE GEMINI
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

# 2. LOAD CATALOG
CATALOG_FILE = "grocery_catalog.json"
def load_catalog():
    try:
        with open(CATALOG_FILE, "r") as f:
            return json.load(f)
    except:
        return []

CATALOG = load_catalog()

# 3. HELPER: MURF VOICE
def generate_murf_speech(text):
    MURF_API_KEY = os.getenv('MURF_AI_API_KEY')
    # Using 'en-US-ken' for a friendly, quick-service vibe
    voice_id = "en-US-ken"
    
    url = "https://api.murf.ai/v1/speech/generate"
    headers = {"api-key": MURF_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "voice_id": voice_id,
        "style": "Conversational",
        "multiNativeLocale": "en-US"
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        if response.status_code != 200:
             # Fallback
             payload["voice_id"] = "en-UK-ruby"
             retry = requests.post(url, headers=headers, data=json.dumps(payload))
             return retry.json().get('audioFile')
        return response.json().get('audioFile')
    except:
        return None

@router.get("/health")
async def health_check():
    return HTMLResponse(content="<h1>Blinkit Voice Agent 🛍️</h1>", status_code=200)

@router.post("/start-session")
async def start_session():
    greeting = "Hi! Welcome to Blinkit Voice. I can help you order groceries or even ingredients for a full meal. What can I get for you?"
    return JSONResponse(content={
        "text": greeting,
        "audioUrl": generate_murf_speech(greeting)
    })

# --- MAIN GROCERY AGENT LOGIC ---
@router.post("/chat-with-voice")
async def chat_with_voice(
    file: UploadFile = File(...), 
    current_state: str = Form(...)
):
    try:
        # A. SETUP
        aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
        
        try:
            state = json.loads(current_state)
        except:
            state = {"cart": [], "total_price": 0, "is_complete": False}

        # B. TRANSCRIBE
        audio_data = await file.read()
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_data)
        user_text = transcript.text or ""
        print(f"🛒 User: {user_text}")

        # C. INTELLIGENT AGENT (Gemini)
        # We give the LLM the entire catalog so it can "pick" the right items.
        
        system_prompt = f"""
        You are a friendly Blinkit Voice Assistant.
        
        STORE CATALOG:
        {json.dumps(CATALOG)}
        
        CURRENT CART:
        {json.dumps(state['cart'])}
        
        USER SAID: "{user_text}"
        
        GOALS:
        1. **Understand Intent:** Does the user want a specific item OR ingredients for a dish?
        2. **Smart Add:** - If user says "Milk", add Milk.
           - If user says "Ingredients for a sandwich", look at TAGS and add Bread + Peanut Butter (or Cheese).
           - If user says "Ingredients for Pasta", add Pasta + Sauce + Cheese.
        3. **Manage Cart:** Update quantities if asked. Remove if asked.
        4. **Checkout:** If user says "That's all" or "Place order", set 'is_complete' to true.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "updated_cart": [
                {{ "id": "101", "name": "Milk", "price": 27, "qty": 2 }}
            ],
            "total_price": number,
            "is_complete": boolean,
            "reply": "Spoken response confirming what was added."
        }}
        """

        result = model.generate_content(
            system_prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        
        ai_resp = json.loads(result.text)
        new_cart = ai_resp["updated_cart"]
        total_price = ai_resp["total_price"]
        is_complete = ai_resp["is_complete"]
        agent_reply = ai_resp["reply"]
        
        print(f"🛍️ Blinkit: {agent_reply}")

        # D. SAVE ORDER (If Complete)
        if is_complete:
            order_entry = {
                "timestamp": datetime.now().isoformat(),
                "order_details": new_cart,
                "total": total_price,
                "status": "placed"
            }
            # Save to a generic 'orders.json'
            with open("orders.json", "a") as f:
                f.write(json.dumps(order_entry) + "\n")
            print("✅ Order Placed!")

        # E. AUDIO
        audio_url = generate_murf_speech(agent_reply)

        return {
            "user_transcript": user_text,
            "ai_text": agent_reply,
            "audio_url": audio_url,
            "updated_state": {
                "cart": new_cart,
                "total_price": total_price,
                "is_complete": is_complete
            }
        }

    except Exception as e:
        print(f"Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})