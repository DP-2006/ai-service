from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List

from app.core.security import verify_webhook
from app.services.chat_monitor import monitor_chat, suggest_questions
from app.services.alert_service import send_alert_to_admin

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(verify_webhook)],
)


class Message(BaseModel):
    role: str  # "user" | "seller" | "admin"
    content: str


class MonitorIn(BaseModel):
    messages: List[Message]
    context: Optional[str] = ""
    chat_id: Optional[str] = None
    user_id: Optional[str] = None


class HintIn(BaseModel):
    messages: List[Message]


@router.post("/monitor")
async def monitor_ep(payload: MonitorIn):
    result = monitor_chat([m.model_dump() for m in payload.messages], payload.context or "")

    if result.get("suggested_action") in ("block", "alert_admin"):
        await send_alert_to_admin({
            "source": "chat",
            "chat_id": payload.chat_id,
            "user_id": payload.user_id,
            "categories": result.get("categories", []),
            "severity": result.get("severity", "medium"),
            "reason": result.get("reason", ""),
            "admin_summary": result.get("admin_summary", ""),
        })

    return result


@router.post("/hint")
def hint_ep(payload: HintIn):
    text = suggest_questions([m.model_dump() for m in payload.messages])
    return {"hint": text}


class WithContextIn(BaseModel):
    question: str
    context_text: str = ""
    file_ids: Optional[List[str]] = None
    history: Optional[List[Message]] = None
    user_id: Optional[str] = None
    images_b64: Optional[List[str]] = None


WITH_CONTEXT_SYSTEM = """You are an AI assistant for an admin panel.
Answer the user's question based ONLY on the provided context.
Answer in Persian (Farsi). Be concise and precise.
If the answer is not in the context, say so honestly."""


@router.post("/with-context")
def with_context_ep(payload: WithContextIn):
    from app.services.ollama_client import chat_text, chat_vision

    history_block = ""
    if payload.history:
        lines = []
        for m in payload.history[-10:]:
            role = "کاربر" if m.role == "user" else "دستیار"
            lines.append(f"{role}: {m.content}")
        history_block = "\n".join(lines)

    prompt = (
        f"=== CONTEXT ===\n{payload.context_text}\n\n"
        f"=== HISTORY ===\n{history_block}\n\n"
        f"=== QUESTION ===\n{payload.question}\n\n"
        f"پاسخ به فارسی:"
    )

    images = [i for i in (payload.images_b64 or []) if i]
    VISION_SYSTEM = """You are a vision assistant. The user has attached an image.
Look at the IMAGE carefully and describe exactly what you see.
Answer in Persian (Farsi). Be precise and concise.
If the user also provides context_text, combine it with what you see.
Never say you cannot see the image - you have direct access to it."""
    if images:
        answer = chat_vision(prompt, images, system=VISION_SYSTEM)
    else:
        answer = chat_text(prompt, system=WITH_CONTEXT_SYSTEM)

    return {
        "answer": answer,
        "model": "gemma3:27b",
        "file_ids": payload.file_ids or [],
        "user_id": payload.user_id,
        "images_used": len(images),
    }
