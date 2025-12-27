# main.py (бэкенд)
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CLOUDFLARE_PROXY_URL = os.getenv("CLOUDFLARE_PROXY_URL")


class ChatRequest(BaseModel):
    messages: list


@app.post("/chat")
async def chat(request: ChatRequest):
    if not CLOUDFLARE_PROXY_URL:
        raise HTTPException(status_code=500, detail="CLOUDFLARE_PROXY_URL not set")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{CLOUDFLARE_PROXY_URL}/openrouter",
                json={
                    "model": "qwen/qwen3-4b:free",
                    "messages": request.messages,
                    "temperature": 0.7,
                    "max_tokens": 512
                }
            )
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="OpenRouter error")
            data = response.json()
            return {"reply": data["choices"][0]["message"]["content"]}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/tts_url")
async def get_tts_url(text: str):
    tts_url = f"{CLOUDFLARE_PROXY_URL}/edge-tts/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken=6A5AA1D4EAFF4E9FB37E23D68491D6F4&text={text}&locale=ru-RU&voice=ru-RU-DmitryNeural"
    return {"tts_url": tts_url}