from pathlib import Path
ROOT = Path(__file__).parent

FILES = {}

FILES["requirements.txt"] = """fastapi==0.115.0
uvicorn[standard]==0.32.0
ollama==0.4.1
chromadb==0.5.15
pydantic==2.9.2
pydantic-settings==2.6.0
python-multipart==0.0.12
httpx==0.27.2
Pillow==11.0.0
python-dotenv==1.0.1
"""

FILES[".env"] = """OLLAMA_HOST=http://ollama:11434
MODEL_TEXT=qwen2.5-coder:7b
MODEL_VISION=qwen2.5vl:7b
MODEL_EMBED=nomic-embed-text

CHROMA_HOST=chromadb
CHROMA_PORT=8000
CHROMA_COLLECTION=org_knowledge

WEBHOOK_SECRET=change-this-to-a-long-random-string-min-32-chars
WEBHOOK_MAX_AGE_SECONDS=300

APP_HOST=0.0.0.0
APP_PORT=9000
LOG_LEVEL=INFO
"""

for p in ["app/__init__.py","app/core/__init__.py","app/routers/__init__.py","app/services/__init__.py","app/schemas/__init__.py"]:
    FILES[p] = ""

FILES["app/core/config.py"] = """from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OLLAMA_HOST: str = "http://ollama:11434"
    MODEL_TEXT: str = "qwen2.5-coder:7b"
    MODEL_VISION: str = "qwen2.5vl:7b"
    MODEL_EMBED: str = "nomic-embed-text"

    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION: str = "org_knowledge"

    WEBHOOK_SECRET: str = "dev-secret"
    WEBHOOK_MAX_AGE_SECONDS: int = 300

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 9000
    LOG_LEVEL: str = "INFO"


settings = Settings()
"""

FILES["app/core/security.py"] = """import hmac
import hashlib
import time
from fastapi import Header, HTTPException, Request

from app.core.config import settings


async def verify_webhook(
    request: Request,
    x_signature: str = Header(...),
    x_timestamp: str = Header(...),
):
    try:
        ts = int(x_timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")

    if abs(time.time() - ts) > settings.WEBHOOK_MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Timestamp expired")

    body = await request.body()
    expected = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body + x_timestamp.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(x_signature, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")

    return True
"""

FILES["app/services/ollama_client.py"] = """import ollama

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
"""

FILES["app/services/moderation_service.py"] = '''import json
import re

from app.services.ollama_client import chat_text, chat_vision

SYSTEM_PROMPT = """You are a strict content moderation AI for an organization.
Analyze the given content (text and/or image description) for violations:

CATEGORIES:
1. FRAUD - scam, phishing, extortion, blackmail
2. SEXUAL - sexual content, private images, extortion with intimate media
3. DRUGS - drug use imagery (any visible substance, even cigarettes)
4. CONFIDENTIAL - organizational confidential documents, trade secrets
5. SALES_LEAK - leaking sales data, customer lists, pricing
6. HARASSMENT - threats, abusive language
7. SAFE - no violation

Return ONLY valid JSON (no markdown, no explanation):
{
  "is_violation": true|false,
  "categories": ["FRAUD", ...],
  "confidence": 0.0-1.0,
  "severity": "low|medium|high|critical",
  "reason": "short explanation in English",
  "suggested_action": "allow|flag|block|alert_admin"
}

Be strict. When in doubt, flag for admin review."""


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    match = re.search(r"\\{.*\\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in model response")
    return json.loads(match.group(0))


def _fallback(reason: str) -> dict:
    return {
        "is_violation": True,
        "categories": ["UNKNOWN"],
        "confidence": 0.0,
        "severity": "medium",
        "reason": reason,
        "suggested_action": "flag",
    }


def moderate_text(content: str, context: str = "") -> dict:
    prompt = f"CONTEXT: {context}\\n\\nCONTENT:\\n{content}\\n\\nReturn JSON."
    raw = chat_text(prompt, system=SYSTEM_PROMPT)
    try:
        return _extract_json(raw)
    except Exception as e:
        return _fallback(f"Parse error: {e}; raw={raw[:200]}")


def moderate_image(image_b64: str, context: str = "") -> dict:
    prompt = (
        f"CONTEXT: {context}\\n\\n"
        "Analyze this image strictly. Detect: nudity, sexual content, "
        "drug substances (any visible), confidential documents, sales data, "
        "weapons, violence. Return JSON."
    )
    raw = chat_vision(prompt, [image_b64], system=SYSTEM_PROMPT)
    try:
        return _extract_json(raw)
    except Exception as e:
        return _fallback(f"Parse error: {e}")
'''

FILES["app/services/rag_service.py"] = '''import chromadb

from app.core.config import settings
from app.services.ollama_client import embed, chat_text

_client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)


def _collection():
    return _client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def index_document(doc_id: str, text: str, metadata: dict | None = None):
    vec = embed(text)
    _collection().upsert(
        ids=[doc_id],
        embeddings=[vec],
        documents=[text],
        metadatas=[metadata or {}],
    )


def query(question: str, top_k: int = 5) -> list[dict]:
    vec = embed(question)
    res = _collection().query(query_embeddings=[vec], n_results=top_k)
    out = []
    for i in range(len(res["ids"][0])):
        out.append({
            "id": res["ids"][0][i],
            "text": res["documents"][0][i],
            "metadata": res["metadatas"][0][i],
            "distance": res["distances"][0][i],
        })
    return out


def rag_answer(question: str) -> dict:
    docs = query(question, top_k=5)
    context = "\\n---\\n".join(d["text"] for d in docs)
    prompt = f"""Answer the question using ONLY the context below.
If not in context, say "not found in knowledge base".

CONTEXT:
{context}

QUESTION: {question}
"""
    answer = chat_text(prompt)
    return {"answer": answer, "sources": docs}
'''

FILES["app/routers/health.py"] = '''from fastapi import APIRouter

from app.core.config import settings
from app.services.ollama_client import _client

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    try:
        models = _client.list()
        ollama_ok = True
    except Exception:
        ollama_ok = False
        models = {"models": []}

    return {
        "status": "ok",
        "ollama": ollama_ok,
        "models": [m["name"] for m in models.get("models", [])] if ollama_ok else [],
        "text_model": settings.MODEL_TEXT,
        "vision_model": settings.MODEL_VISION,
    }
'''

FILES["app/routers/moderate.py"] = '''from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.security import verify_webhook
from app.services.moderation_service import moderate_text, moderate_image

router = APIRouter(
    prefix="/moderate",
    tags=["moderate"],
    dependencies=[Depends(verify_webhook)],
)


class TextIn(BaseModel):
    content: str
    context: Optional[str] = ""


class ImageIn(BaseModel):
    image_b64: str
    context: Optional[str] = ""


@router.post("/text")
def moderate_text_ep(payload: TextIn):
    return moderate_text(payload.content, payload.context)


@router.post("/image")
def moderate_image_ep(payload: ImageIn):
    return moderate_image(payload.image_b64, payload.context)
'''

FILES["app/routers/rag.py"] = '''from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.security import verify_webhook
from app.services.rag_service import index_document, rag_answer

router = APIRouter(
    prefix="/rag",
    tags=["rag"],
    dependencies=[Depends(verify_webhook)],
)


class IndexIn(BaseModel):
    doc_id: str
    text: str
    metadata: Optional[dict] = None


class QueryIn(BaseModel):
    question: str


@router.post("/index")
def index_ep(payload: IndexIn):
    index_document(payload.doc_id, payload.text, payload.metadata)
    return {"status": "indexed", "doc_id": payload.doc_id}


@router.post("/query")
def query_ep(payload: QueryIn):
    return rag_answer(payload.question)
'''

FILES["app/main.py"] = '''import logging

from fastapi import FastAPI

from app.core.config import settings
from app.routers import health, moderate, rag

logging.basicConfig(level=settings.LOG_LEVEL)
log = logging.getLogger("ai-service")

app = FastAPI(title="AI Moderation Service", version="0.1.0")

app.include_router(health.router)
app.include_router(moderate.router)
app.include_router(rag.router)


@app.on_event("startup")
async def _startup():
    log.info("AI Service starting...")
    log.info(f"Ollama: {settings.OLLAMA_HOST}")
    log.info(f"Chroma: {settings.CHROMA_HOST}:{settings.CHROMA_PORT}")
'''

FILES["Dockerfile"] = '''FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential curl \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY rag_data ./rag_data
COPY scripts ./scripts

EXPOSE 9000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
'''

FILES["docker-compose.yml"] = """services:
  ai-service:
    build: .
    container_name: ai-service
    ports:
      - "9000:9000"
    env_file: .env
    depends_on:
      - ollama
      - chromadb
    networks:
      - ai-net
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - ai-net
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  chromadb:
    image: chromadb/chroma:0.5.15
    container_name: chromadb
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma
    networks:
      - ai-net
    restart: unless-stopped

volumes:
  ollama_data:
  chroma_data:

networks:
  ai-net:
    driver: bridge
"""

FILES["scripts/init_ollama.ps1"] = '''Write-Host "Pulling models into Ollama container..." -ForegroundColor Cyan

docker exec ollama ollama pull qwen2.5-coder:7b
docker exec ollama ollama pull qwen2.5vl:7b
docker exec ollama ollama pull nomic-embed-text

Write-Host "Done. Listing models:" -ForegroundColor Green
docker exec ollama ollama list
'''

FILES["scripts/test_webhook.py"] = '''"""Test secure webhook to AI service."""
import hmac
import hashlib
import time
import json
import requests

SECRET = "change-this-to-a-long-random-string-min-32-chars"
URL = "http://localhost:9000/moderate/text"

payload = {
    "content": "سلام، لطفاً شماره کارتت رو بفرست تا جایزه بگیرم",
    "context": "chat between user and seller",
}
body = json.dumps(payload).encode()
ts = str(int(time.time()))
sig = hmac.new(SECRET.encode(), body + ts.encode(), hashlib.sha256).hexdigest()

r = requests.post(
    URL,
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-Signature": sig,
        "X-Timestamp": ts,
    },
)
print("Status:", r.status_code)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
'''


def main():
    for rel, content in FILES.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"written: {rel}")


if __name__ == "__main__":
    main()
