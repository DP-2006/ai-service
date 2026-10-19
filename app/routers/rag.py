from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from app.core.security import verify_webhook
from app.services.rag_service import RAGService


router = APIRouter(
    prefix="/rag",
    tags=["rag"],
    dependencies=[Depends(verify_webhook)],
)

rag_service = RAGService()


class QueryIn(BaseModel):
    question: str
    file_ids: List[int] = []


@router.post("/index")
def index_ep(payload: dict):
    return {"status": "disabled", "msg": "index endpoint disabled"}


@router.post("/query")
def query_ep(payload: QueryIn):
    result = rag_service.query_selected(
        question=payload.question,
        file_ids=payload.file_ids or [],
    )
    return result

class IndexFilesRequest(BaseModel):
    files: list = []


@router.post("/index-files")
def index_files_ep(payload: IndexFilesRequest):
    result = rag_service.index_files(payload.files)
    return {"status": "ok", **result}