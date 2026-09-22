from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.security import verify_webhook
from app.services.vision_service import analyze_image
from app.services.alert_service import send_alert_to_admin

router = APIRouter(
    prefix="/vision",
    tags=["vision"],
    dependencies=[Depends(verify_webhook)],
)


class ImageIn(BaseModel):
    image_b64: str
    context: Optional[str] = ""
    user_id: Optional[str] = None
    chat_id: Optional[str] = None


@router.post("/analyze")
async def analyze_ep(payload: ImageIn):
    result = analyze_image(payload.image_b64, payload.context or "")

    if result.get("suggested_action") in ("block", "alert_admin"):
        await send_alert_to_admin({
            "source": "image",
            "chat_id": payload.chat_id,
            "user_id": payload.user_id,
            "categories": result.get("categories", []),
            "severity": result.get("severity", "medium"),
            "reason": result.get("reason", ""),
            "admin_summary": result.get("admin_summary", ""),
        })

    return result
