from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
import os
import requests
import json
import google.generativeai as genai
import assemblyai as aai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

router = APIRouter()

# 1. CONFIGURE GEMINI
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

# 2. LOAD TRANSACTION DATA
DB_FILE = "suspicious_transactions.json"

def get_active_case():
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            # Find the first pending case
            for case in data:
                if case["status"] == "pending":
                    return case
            return data[0] # Return the first one if all closed (for demo)
    except:
        return {}

def update_case_status(case_id, new_status):
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
        
        for case in data:
            if case["id"] == case_id:
                case["status"] = new_status
                
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"DB Error: {e}")

# 3. MURF VOICE (Authoritative)
def generate_murf_speech(text):
    MURF_API_KEY = os.getenv('MURF_AI_API_KEY')
    voice_id = "en-US-marcus" # Professional/Authoritative Voice
    
    url = "https://api.murf.ai/v1/speech/generate"
    headers = {"api-key": MURF_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "voice_id": voice_id,
        "style": "Promo",
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
    return HTMLResponse(content="<h1>Fraud Alert System Active 🔒</h1>", status_code=200)

@router.post("/start-session")
async def start_session():
    case = get_active_case()
    if not case:
        return JSONResponse(content={"text": "No active alerts."})

    greeting = f"This is an urgent call from HDFC Bank Fraud Detection Department. Am I speaking with {case['userName']}?"
    
    return JSONResponse(content={
        "text": greeting,
        "audioUrl": generate_murf_speech(greeting),
        "case_data": case # Send initial data to frontend
    })

# --- MAIN FRAUD AGENT LOGIC ---
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
            state = {"verification_stage": "unverified", "case_status": "pending"}

        # Get the actual DB record to compare against
        case_record = get_active_case()

        # B. TRANSCRIBE
        audio_data = await file.read()
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_data)
        user_text = transcript.text or ""
        print(f"🔒 User: {user_text}")

        # C. SECURITY BRAIN (Gemini)
        system_prompt = f"""
        You are a Senior Fraud Analyst at HDFC Bank. You are authoritative but polite.
        
        CASE FILE:
        {json.dumps(case_record)}
        
        CURRENT STATUS:
        Verification Stage: {state.get('verification_stage')} (unverified/verified)
        
        USER SAID: "{user_text}"
        
        PROTOCOL:
        1. **Identity Check:** If 'verification_stage' is 'unverified', you MUST ask the user to confirm the **last 4 digits** of their card ending in {case_record['cardEnding']}.
           - If user provides correct digits ({case_record['cardEnding']}), set 'verification_stage' to 'verified'.
           - If wrong, deny access politely and end call.
        
        2. **Transaction Review:** ONLY after verification, read the transaction details: "{case_record['transactionName']} for {case_record['transactionAmount']} at {case_record['transactionTime']}".
           - Ask: "Did you authorize this?"
        
        3. **Action:**
           - If user says YES (Authorized): Mark 'case_status' as 'safe'. Say "Thank you, we have unblocked the card."
           - If user says NO (Fraud): Mark 'case_status' as 'fraudulent'. Say "We have blocked your card immediately and issued a replacement."
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "updated_state": {{
                "verification_stage": "unverified" | "verified",
                "case_status": "pending" | "safe" | "fraudulent"
            }},
            "reply": "Spoken response"
        }}
        """

        result = model.generate_content(
            system_prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        
        ai_resp = json.loads(result.text)
        new_state = ai_resp["updated_state"]
        agent_reply = ai_resp["reply"]
        
        print(f"🛡️ Analyst: {agent_reply}")

        # D. UPDATE DATABASE
        if new_state["case_status"] != "pending":
            update_case_status(case_record["id"], new_state["case_status"])
            print(f"✅ Case {case_record['id']} marked as {new_state['case_status']}")

        # E. AUDIO
        audio_url = generate_murf_speech(agent_reply)

        return {
            "user_transcript": user_text,
            "ai_text": agent_reply,
            "audio_url": audio_url,
            "updated_state": new_state
        }

    except Exception as e:
        print(f"Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})