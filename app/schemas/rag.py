# app/schemas/rag.py
from pydantic import BaseModel, Field
from typing import List, Optional


class SelectedFilesRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    file_ids: List[int] = Field(default_factory=list, max_length=50)
    user_id: Optional[str] = None


class PresentationRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    file_ids: List[int] = Field(default_factory=list, max_length=50)
    user_id: Optional[str] = None
    slide_count: int = Field(default=8, ge=3, le=30)
    language: str = "fa"
    style: str = "academic"
