from fastapi import APIRouter

from app.core.config import settings
from app.services.ollama_client import _client

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    try:
        models_resp = _client.list()
        ollama_ok = True
    except Exception:
        ollama_ok = False
        models_resp = {"models": []}

    def _name(m):
        if isinstance(m, dict):
            return m.get("name") or m.get("model") or str(m)
        return getattr(m, "model", None) or getattr(m, "name", None) or str(m)

    return {
        "status": "ok",
        "ollama": ollama_ok,
        "models": [_name(m) for m in models_resp.get("models", [])] if ollama_ok else [],
        "text_model": settings.MODEL_TEXT,
        "vision_model": settings.MODEL_VISION,
    }
