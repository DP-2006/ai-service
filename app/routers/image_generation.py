import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.core.security import verify_webhook



router = APIRouter(
    prefix="/image-generation",
    tags=["image-generation"],
    dependencies=[Depends(verify_webhook)],
)

WORKER_URL = "http://127.0.0.1:9001/image/generate"

class ImageGenerationRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    context_text: str = Field(min_length=20, max_length=30000)

@router.post("/generate")
def generate_image(payload: ImageGenerationRequest):

    try:
        response = requests.post(
            WORKER_URL,
            json={
                "topic": payload.topic,
                "context_text": payload.context_text,
            },
            timeout=600,
        )

        response.raise_for_status()
        return response.json()

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Image worker error: {exc}",
        )
