import ollama
from app.core.config import settings

_client = ollama.Client(host=settings.OLLAMA_HOST)

def chat_text(prompt: str, system: str = "", model: str | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = _client.chat(
        model=model or settings.MODEL_TEXT,
        messages=messages,
        options={"temperature": 0.1},
    )
    return resp["message"]["content"]

def chat_vision(prompt: str, images_b64: list[str], system: str = "") -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({
        "role": "user",
        "content": prompt,
        "images": images_b64,
    })
    resp = _client.chat(model=settings.MODEL_VISION, messages=messages)
    return resp["message"]["content"]

def embed(text: str) -> list[float]:
    resp = _client.embeddings(model=settings.MODEL_EMBED, prompt=text)
    return resp["embedding"]