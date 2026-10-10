import logging

from fastapi import FastAPI

from app.core.config import settings
from app.routers import health, moderate, rag, chat, vision, document, image, file
from app.routers.presentation import router as presentation_router
from app.routers.image_generation import router as image_generation_router
from app.routers.presentation import router as presentation_router
from app.routers.research import router as research_router

logging.basicConfig(level=settings.LOG_LEVEL)
log = logging.getLogger("ai-service")

app = FastAPI(title="AI Moderation Service", version="0.4.0")

app.include_router(health.router)
app.include_router(moderate.router)
app.include_router(rag.router)
app.include_router(chat.router)
app.include_router(vision.router)      # visual-only
app.include_router(document.router)    # OCR-only
app.include_router(image.router)       # unified (both)
app.include_router(file.router)    # unified file analysis
app.include_router(presentation_router)

app.include_router(presentation_router)
app.include_router(research_router)
app.include_router(image_generation_router)
@app.on_event("startup")
async def _startup():
    log.info("AI Service starting...")
    log.info(f"Ollama: {settings.OLLAMA_HOST}")
    log.info(f"Chroma: {settings.CHROMA_HOST}:{settings.CHROMA_PORT}")

