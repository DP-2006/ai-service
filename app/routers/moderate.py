from fastapi import APIRouter, Depends
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
