# main.py
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv
import edge_tts
import asyncio
import tempfile

load_dotenv()

app = FastAPI()

# Разрешаем CORS (чтобы MAUI мог обращаться)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CLOUDFLARE_PROXY_URL = os.getenv( "CLOUDFLARE_PROXY_URL")

class ChatRequest(BaseModel):
    messages: list  # [{"role": "user", "content": "..."}]

@app.post("/chat")
async def chat(request: ChatRequest):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{CLOUDFLARE_PROXY_URL}/openrouter/v1/chat/completions",
                json={
                    "model": "qwen/qwen-3-4b-free",
                    "messages": request.messages,
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
            )
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"OpenRouter error: {response.text}")
            data = response.json()
            return {"reply": data["choices"][0]["message"]["content"]}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/tts")
async def text_to_speech(text: str):
    """Генерирует аудио из текста через прокси к Edge TTS"""
    try:
        # Генерируем MP3 через edge-tts
        communicate = edge_tts.Communicate(text, voice="ru-RU-DmitryNeural")  # или "ru-RU-SvetlanaNeural"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_path = tmp_file.name
            await communicate.save(tmp_path)

        # Читаем файл
        with open(tmp_path, "rb") as f:
            audio_data = f.read()

        # Удаляем временный файл
        os.unlink(tmp_path)

        return {"audio_base64": audio_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")