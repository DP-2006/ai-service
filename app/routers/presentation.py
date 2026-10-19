import base64
# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel, Field
#
# from app.services.presentation_service import generate_presentation
#
#
# router = APIRouter(
#     prefix="/presentation",
#     tags=["presentation"],
# )
#
#
# class PresentationRequest(BaseModel):
#     topic: str
#     context_text: str
#     slide_count: int = Field(default=10, ge=3, le=30)
#     language: str = "fa"
#     style: str = "academic"
#
#
# @router.post("/generate")
# def generate_presentation_api(request: PresentationRequest):
#
#     if not request.topic.strip():
#         raise HTTPException(
#             status_code=400,
#             detail="topic is required",
#         )
#
#     if not request.context_text.strip():
#         raise HTTPException(
#             status_code=400,
#             detail="context_text is required",
#         )
#
#     try:
#         result = generate_presentation(
#             topic=request.topic,
#             context_text=request.context_text,
#             slide_count=request.slide_count,
#             language=request.language,
#             style=request.style,
#         )
#
#         return {
#             "status": "success",
#             **result,
#         }
#
#     except Exception as exc:
#         raise HTTPException(
#             status_code=500,
#             detail=str(exc),
#         )




# app/routers/presentation.py

from fastapi import APIRouter, Depends, HTTPException
from app.core.security import verify_webhook
from app.schemas.rag import PresentationRequest
from app.services.rag_service import RAGService
from app.services.presentation_service import PresentationService

router = APIRouter(
    prefix="/presentation",
    tags=["presentation"],
    dependencies=[Depends(verify_webhook)],
)

rag_service = RAGService()
presentation_service = PresentationService()


SYSTEM_PPT = """You are a senior instructional designer. Build a slide deck outline from the provided source excerpts.

RULES:
- Use ONLY the provided sources. Never invent facts.
- Each slide: title + 3-5 bullet points, each ≤ 15 words.
- First slide: title + subtitle.
- Last slide: summary.
- Language: same as the topic.
- Cite the source file name at the end of each slide's notes.
- Return strict JSON: {"slides":[{"title":str,"bullets":[str],"notes":str}]}
"""


@router.post("/generate")
def generate_presentation(payload: PresentationRequest):
    if not payload.file_ids:
        raise HTTPException(
            status_code=400,
            detail="برای تولید پاورپوینت باید حداقل یک فایل انتخاب شود.",
        )

    context = rag_service.build_context(
        question=payload.topic,
        file_ids=payload.file_ids,
        user_id=payload.user_id,
        max_chars=20000,
    )

    if not context.strip():
        raise HTTPException(
            status_code=422,
            detail="محتوایی در فایل‌های انتخابی برای این موضوع یافت نشد.",
        )

    slides = presentation_service.build_slides(
        topic=payload.topic,
        context=context,
        slide_count=payload.slide_count,
        system=SYSTEM_PPT,
    )

    pptx_bytes = presentation_service.render_pptx(
        title=payload.topic,
        slides=slides,
        rtl=True,
    )

    return {
        "status": "success",
        "topic": payload.topic,
        "slides": slides,
        "pptx_base64": base64.b64encode(pptx_bytes).decode("utf-8"),
        "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }