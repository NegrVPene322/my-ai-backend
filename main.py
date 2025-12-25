# main.py
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Получаем URL из переменной окружения (имя переменной!)
CLOUDFLARE_PROXY_URL = os.getenv("CLOUDFLARE_PROXY_URL")


class ChatRequest(BaseModel):
    messages: list  # [{"role": "user", "content": "..."}]


@app.post("/chat")
async def chat(request: ChatRequest):
    if not CLOUDFLARE_PROXY_URL:
        raise HTTPException(status_code=500, detail="CLOUDFLARE_PROXY_URL not set")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Отправляем запрос к Worker'у
            response = await client.post(
                f"{CLOUDFLARE_PROXY_URL}/openrouter",
                json={
                    "model": "qwen/qwen-3-4b-free",  # Worker сам исправит
                    "messages": request.messages,
                }
            )
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"OpenRouter error: {response.text}")

            data = response.json()
            return {"reply": data["choices"][0]["message"]["content"]}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# Эндпоинт для озвучки (опционально)
@app.get("/tts_url")
async def get_tts_url(text: str):
    """Возвращает URL для генерации речи через Edge TTS (прокси)"""
    if not CLOUDFLARE_PROXY_URL:
        raise HTTPException(status_code=500, detail="CLOUDFLARE_PROXY_URL not set")

    # Возвращаем URL, по которому MAUI сам сделает запрос
    tts_url = f"{CLOUDFLARE_PROXY_URL}/edge-tts/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken=6A5AA1D4EAFF4E9FB37E23D68491D6F4&text={text}&locale=ru-RU&voice=ru-RU-DmitryNeural"
    return {"tts_url": tts_url}