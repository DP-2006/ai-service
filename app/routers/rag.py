from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.security import verify_webhook
from app.services.rag_service import index_document, rag_answer

router = APIRouter(
    prefix="/rag",
    tags=["rag"],
    dependencies=[Depends(verify_webhook)],
)


class IndexIn(BaseModel):
    doc_id: str
    text: str
    metadata: Optional[dict] = None


class QueryIn(BaseModel):
    question: str


@router.post("/index")
def index_ep(payload: IndexIn):
    index_document(payload.doc_id, payload.text, payload.metadata)
    return {"status": "indexed", "doc_id": payload.doc_id}


@router.post("/query")
def query_ep(payload: QueryIn):
    return rag_answer(payload.question)
