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

# 2. LOAD COMPANY DATA
COMPANY_FILE = "company_data.json"
def load_company_data():
    try:
        with open(COMPANY_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

COMPANY_DATA = load_company_data()

# 3. HELPER: MURF SPEECH GENERATION (Professional Voice)
def generate_murf_speech(text):
    MURF_API_KEY = os.getenv('MURF_AI_API_KEY')
    # Using 'en-US-marcus' for a professional male SDR voice, or 'en-US-natalie' for female
    voice_id = "en-US-marcus" 
    
    url = "https://api.murf.ai/v1/speech/generate"
    headers = {"api-key": MURF_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "voice_id": voice_id,
        "style": "Promo", # Professional style
        "multiNativeLocale": "en-US"
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        data = response.json()
        if response.status_code != 200:
            # Fallback to Ruby if Marcus fails
            payload["voice_id"] = "en-UK-ruby"
            retry = requests.post(url, headers=headers, data=json.dumps(payload))
            return retry.json().get('audioFile')
        return data.get('audioFile')
    except Exception as e:
        print(f"Murf Error: {e}")
        return None

@router.get("/health")
async def health_check():
    return HTMLResponse(content="<h1>SDR Agent Running 💼</h1>", status_code=200)

@router.post("/start-session")
async def start_session():
    greeting = f"Hello! This is Marcus from {COMPANY_DATA['company_name']}. Thanks for stopping by. What brings you to our page today?"
    return JSONResponse(content={
        "text": greeting,
        "audioUrl": generate_murf_speech(greeting)
    })

# --- MAIN SDR LOGIC ---
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
            state = {
                "lead_info": {}, 
                "is_complete": False,
                "conversation_stage": "intro" 
            }

        # B. TRANSCRIBE
        audio_data = await file.read()
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_data)
        user_text = transcript.text or ""
        print(f"👤 User: {user_text}")

        # C. REASONING (The SDR Brain)
        system_prompt = f"""
        You are Marcus, an expert Sales Development Representative (SDR) for {COMPANY_DATA['company_name']}.
        
        COMPANY KNOWLEDGE BASE:
        {json.dumps(COMPANY_DATA)}
        
        CURRENT LEAD DATA:
        {json.dumps(state['lead_info'])}
        
        USER SAID: "{user_text}"
        
        GOALS:
        1. Answer user questions using the FAQ. Be concise and professional.
        2. If the user asks something not in the FAQ, say you'll check with the team.
        3. Gently collect these lead details naturally during conversation: Name, Company, Role, Team Size, Use Case, Timeline.
        4. Don't ask for everything at once. Ask one qualifying question at a time.
        5. If the user says "bye", "that's all", or "thanks", set 'is_complete' to true and give a summary.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "updated_lead_info": {{ "name": "...", "role": "...", ... }},
            "is_complete": boolean,
            "reply": "Your spoken response here."
        }}
        """

        result = model.generate_content(
            system_prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        
        ai_resp = json.loads(result.text)
        updated_lead = ai_resp["updated_lead_info"]
        is_complete = ai_resp["is_complete"]
        agent_reply = ai_resp["reply"]
        
        print(f"💼 SDR: {agent_reply}")

        # D. SAVE LEAD (If Complete)
        if is_complete:
            lead_entry = {
                "timestamp": datetime.now().isoformat(),
                "lead_data": updated_lead,
                "summary": "Lead qualification call completed."
            }
            with open("leads.json", "a") as f:
                f.write(json.dumps(lead_entry) + "\n")
            print("✅ Lead Saved!")

        # E. GENERATE AUDIO
        audio_url = generate_murf_speech(agent_reply)

        return {
            "user_transcript": user_text,
            "ai_text": agent_reply,
            "audio_url": audio_url,
            "updated_state": {
                "lead_info": updated_lead,
                "is_complete": is_complete
            }
        }

    except Exception as e:
        print(f"Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})