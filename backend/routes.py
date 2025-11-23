from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse
import os
import requests
import json
from models import TextToSpeechRequest
from dotenv import load_dotenv
import google.generativeai as genai
import assemblyai as aai

# Load environment variables
load_dotenv()

router = APIRouter()

# 1. CONFIGURE GOOGLE GEMINI (The Brain)
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

# Health check
@router.get("/health")
async def health_check():
    return HTMLResponse(content="<h1>Service is running fully fit 📈 </h1>", status_code=200)

# 2. STANDARD TTS ROUTE (For the "Hello" message)
@router.post("/server")
async def server(request: TextToSpeechRequest):
    MURF_API_KEY = os.getenv('MURF_AI_API_KEY')
    if not MURF_API_KEY:
        return JSONResponse(content={"error": "MURF_AI_API_KEY not found"}, status_code=500)

    endpoint = "https://api.murf.ai/v1/speech/generate"
    headers = {
        "api-key": MURF_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    # We force the voice settings here for consistency
    data = {
        "text": request.text,
        "voice_id": "en-UK-ruby",
        "style": "Conversational",
        "multiNativeLocale": "en-US"
    }

    try:
        response = requests.post(endpoint, headers=headers, data=json.dumps(data))
        response_data = response.json()
        if 'audioFile' in response_data:
            return JSONResponse(content={"audioUrl": response_data['audioFile']}, status_code=200)
        else:
            return JSONResponse(content={"error": "Murf API Error", "details": str(response_data)}, status_code=500)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# 3. CONVERSATION ROUTE (Listen -> Think -> Speak)
@router.post("/chat-with-voice")
async def chat_with_voice(file: UploadFile = File(...)):
    try:
        # A. SETUP KEYS
        aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
        murf_api_key = os.getenv('MURF_AI_API_KEY')

        if not murf_api_key or not aai.settings.api_key:
            return JSONResponse(content={"error": "Missing API Keys in .env"}, status_code=500)

        # B. LISTEN (Transcribe User Audio)
        print("🎧 Transcribing audio...")
        audio_data = await file.read()
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_data)
        user_text = transcript.text
        
        if not user_text:
             return JSONResponse(content={"error": "Could not hear audio clearly"}, status_code=400)

        # C. THINK (Ask Gemini)
        print(f"🗣️ User said: {user_text}")
        
        # We instruct Gemini to be concise for voice conversations
        prompt = f"You are AQUA, a friendly voice assistant. The user just said: '{user_text}'. Respond naturally and briefly (1-2 sentences) so it can be spoken out loud."
        
        chat_response = model.generate_content(prompt)
        ai_reply = chat_response.text.replace("*", "") # Clean up asterisks for smoother speech
        print(f"🤖 AQUA replies: {ai_reply}")

        # D. SPEAK (Generate Audio with Murf)
        murf_url = "https://api.murf.ai/v1/speech/generate"
        murf_headers = {
            "api-key": murf_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        murf_data = {
            "text": ai_reply,
            "voice_id": "en-UK-ruby", 
            "style": "Conversational",
            "multiNativeLocale": "en-US"
        }
        
        murf_res = requests.post(murf_url, headers=murf_headers, data=json.dumps(murf_data))
        audio_url = murf_res.json().get('audioFile')

        # E. RETURN EVERYTHING
        return {
            "user_transcript": user_text,
            "ai_text": ai_reply,
            "audio_url": audio_url
        }

    except Exception as e:
        print(f"Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})