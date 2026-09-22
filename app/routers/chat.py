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
