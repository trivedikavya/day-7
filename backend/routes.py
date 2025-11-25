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

# 2. LOAD COURSE CONTENT
CONTENT_FILE = "day4_tutor_content.json"
def load_content():
    try:
        with open(CONTENT_FILE, "r") as f:
            return json.load(f)
    except:
        return []

COURSE_CONTENT = load_content()

# 3. VOICE MAPPING (Updated with Safer Defaults)
# If "matthew" or "alicia" fail, we fallback to "ruby" which we know works.
VOICE_MAP = {
    "learn": "en-US-matthew",   
    "quiz": "en-US-alicia",     
    "teach_back": "en-US-ken",  
    "default": "en-UK-ruby"     
}

@router.get("/health")
async def health_check():
    return HTMLResponse(content="<h1>Active Recall Tutor Running 🎓</h1>", status_code=200)

# --- HELPER: MURF SPEECH GENERATION ---
def generate_murf_speech(text, mode):
    MURF_API_KEY = os.getenv('MURF_AI_API_KEY')
    
    # Try to get the specific voice, otherwise default to Ruby
    voice_id = VOICE_MAP.get(mode, "en-UK-ruby")
    
    url = "https://api.murf.ai/v1/speech/generate"
    headers = {"api-key": MURF_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "voice_id": voice_id,
        "style": "Conversational",
        "multiNativeLocale": "en-US"
    }
    
    try:
        print(f"🎤 Generating Audio with Voice: {voice_id}...")
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        data = response.json()
        
        if response.status_code != 200:
            print(f"❌ Murf API Error {response.status_code}: {data}")
            # If specific voice fails, try the safe fallback 'en-UK-ruby' ONCE
            if voice_id != "en-UK-ruby":
                print("⚠️ Retrying with fallback voice 'en-UK-ruby'...")
                payload["voice_id"] = "en-UK-ruby"
                retry_res = requests.post(url, headers=headers, data=json.dumps(payload))
                return retry_res.json().get('audioFile')
            return None
            
        return data.get('audioFile')
    except Exception as e:
        print(f"❌ Murf Request Exception: {e}")
        return None

@router.post("/start-session")
async def start_session():
    greeting = "Welcome to your Active Recall Coach. I have two topics ready: Variables, and Loops. Which one would you like to start with?"
    return JSONResponse(content={
        "text": greeting,
        "audioUrl": generate_murf_speech(greeting, "default")
    })

# --- MAIN LOGIC ---
@router.post("/chat-with-voice")
async def chat_with_voice(
    file: UploadFile = File(...), 
    current_state: str = Form(...)
):
    try:
        # A. SETUP & TRANSCRIPTION
        aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
        
        try:
            state = json.loads(current_state)
        except:
            state = {"mode": "menu", "topic_id": None, "feedback": ""}

        print("🎧 Transcribing...")
        audio_data = await file.read()
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_data)
        user_text = transcript.text or ""
        print(f"👨‍🎓 User: {user_text} | Mode: {state['mode']}")

        # B. DETERMINE CONTEXT (Using Gemini)
        system_prompt = f"""
        You are an Active Recall Tutor. 
        COURSE CONTENT: {json.dumps(COURSE_CONTENT)}
        CURRENT STATE: {json.dumps(state)}
        USER SAID: "{user_text}"
        
        INSTRUCTIONS:
        1. Identify if user wants to switch TOPIC or MODE.
        2. IF 'learn': Explain the topic clearly.
        3. IF 'quiz': Ask a question.
        4. IF 'teach_back': Grade the user's explanation.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "updated_state": {{
                "mode": "menu" | "learn" | "quiz" | "teach_back",
                "topic_id": "variables" | "loops" | null,
                "feedback": "string"
            }},
            "reply": "Spoken response text"
        }}
        """

        result = model.generate_content(
            system_prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        
        ai_resp = json.loads(result.text)
        new_state = ai_resp["updated_state"]
        agent_reply = ai_resp["reply"]
        
        print(f"🤖 Tutor ({new_state['mode']}): {agent_reply}")

        # C. GENERATE SPEECH
        audio_url = generate_murf_speech(agent_reply, new_state['mode'])

        return {
            "user_transcript": user_text,
            "ai_text": agent_reply,
            "audio_url": audio_url,
            "updated_state": new_state
        }

    except Exception as e:
        print(f"Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})