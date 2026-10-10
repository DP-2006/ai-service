from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.research_service import extract_urls_content


router = APIRouter(
    prefix="/research",
    tags=["research"],
)


class ResearchRequest(BaseModel):

    urls: List[str] = Field(
        default_factory=list,
        min_length=1,
        max_length=10,
    )


@router.post("/extract")
def extract_research(request: ResearchRequest):

    if not request.urls:
        raise HTTPException(
            status_code=400,
            detail="At least one URL is required.",
        )

    try:

        result = extract_urls_content(
            urls=request.urls,
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