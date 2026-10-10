from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.presentation_service import generate_presentation


router = APIRouter(
    prefix="/presentation",
    tags=["presentation"],
)


class PresentationRequest(BaseModel):
    topic: str
    context_text: str
    slide_count: int = Field(default=10, ge=3, le=30)
    language: str = "fa"
    style: str = "academic"


@router.post("/generate")
def generate_presentation_api(request: PresentationRequest):

    if not request.topic.strip():
        raise HTTPException(
            status_code=400,
            detail="topic is required",
        )

    if not request.context_text.strip():
        raise HTTPException(
            status_code=400,
            detail="context_text is required",
        )

    try:
        result = generate_presentation(
            topic=request.topic,
            context_text=request.context_text,
            slide_count=request.slide_count,
            language=request.language,
            style=request.style,
        )

        return {
            "status": "success",
            **result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )