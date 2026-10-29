



# app/routers/chat.py

from fastapi import APIRouter, Depends, HTTPException
from app.core.security import verify_webhook
from app.schemas.rag import SelectedFilesRequest
from app.services.rag_service import RAGService
from app.services.llm_service import LLMService

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(verify_webhook)],
)

rag_service = RAGService()
llm_service = LLMService()


SYSTEM_CHAT = """You are a study assistant. You answer ONLY using the provided source excerpts.

RULES:
- If the answer is not in the sources, say: "در فایل‌های انتخابی شما پاسخی برای این پرسش پیدا نشد."
- Always cite the source file name in parentheses after each claim.
- Never use outside knowledge.
- Answer in the same language as the question.
- Be concise and structured (bullet points when helpful).
"""


@router.post("/with-context")
def chat_with_context(payload: SelectedFilesRequest):
    if not payload.file_ids:
        raise HTTPException(
            status_code=400,
            detail="هیچ فایلی انتخاب نشده است. لطفاً حداقل یک فایل انتخاب کنید.",
        )

    context = rag_service.build_context(
        question=payload.question,
        file_ids=payload.file_ids,
        user_id=payload.user_id,
    )

    if not context.strip():
        return {
            "answer": "در فایل‌های انتخابی شما محتوایی برای پاسخ به این پرسش یافت نشد.",
            "sources": [],
        }

    answer = llm_service.generate(
        system=SYSTEM_CHAT,
        user=f"""Question:
{payload.question}

Source excerpts:
{context}
""",
    )

    return {
        "answer": answer,
        "sources": sorted(set(
            m.get("file_name", "unknown")
            for m in rag_service.query_selected(
                payload.question, payload.file_ids, payload.user_id, top_k=8
            ).get("metadatas", [[]])[0]
        )),
    }
