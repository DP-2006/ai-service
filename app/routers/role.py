# app/routers/role.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import base64
import logging

from app.services.ollama_client import chat_text, chat_vision

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/role", tags=["role"])


# ---------- Schemas ----------
class AnalyzeOneRequest(BaseModel):
    role_text: str
    file_b64: str
    filename: str
    is_image: bool = False


class ClassifyItem(BaseModel):
    file_id: int
    file_b64: str
    filename: str
    is_image: bool = False


class ClassifyRequest(BaseModel):
    role_text: str
    files: List[ClassifyItem]


# ---------- Prompts ----------
ROLE_SYSTEM = """تو یک تحلیل‌گر ارشد سازمانی هستی.
وظیفه: تشخیص بده آیا یک فایل با نقش سازمانی کاربر «مرتبط» است یا «نامرتبط».
همچنین یک «دسته‌بندی داینامیک» مناسب برای فایل پیشنهاد بده.

خروجی را دقیقاً به صورت JSON برگردان، بدون هیچ متن اضافه:
{
  "is_related": true/false,
  "relevance_score": 0.0 تا 1.0,
  "category": "یک کلمه یا عبارت کوتاه فارسی برای دسته",
  "top_topic": "موضوع غالب فایل در یک عبارت کوتاه",
  "reason": "توضیح کوتاه فارسی چرا مرتبط یا نامرتبط",
  "threat_level": "low" | "medium" | "high" | "critical"
}

قواعد:
- اگر فایل حاوی اطلاعات محرمانه‌ای است که به نقش کاربر مربوط نیست، threat_level را بالا ببر.
- اگر فایل کاملاً بی‌ربط است اما بی‌خطر، is_related=false و threat_level=low.
- دسته‌بندی را از پیش تعیین نکن؛ بر اساس محتوا و نقش پیشنهاد بده.
"""


def _parse_json(text: str) -> dict:
    import json, re
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"پاسخ JSON نبود: {text[:200]}")
    return json.loads(text[start:end + 1])




@router.post("/analyze")
async def analyze_one(req: AnalyzeOneRequest):
    try:
        user_prompt = (
            f"### نقش سازمانی کاربر:\n{req.role_text}\n\n"
            f"### نام فایل: {req.filename}\n\n"
            "لطفاً تحلیل کن و فقط JSON برگردان."
        )

        if req.is_image:
            resp = await chat_vision(
                prompt=user_prompt,
                images=[req.file_b64],
                system=ROLE_SYSTEM,
            )
        else:

            try:
                content = base64.b64decode(req.file_b64).decode("utf-8", errors="ignore")
            except Exception:
                content = "(محتوای دودویی - قابل خواندن نبود)"
            if len(content) > 15000:
                content = content[:15000] + "\n...[بریده شد]"
            resp = await chat_text(
                prompt=f"{user_prompt}\n\n### محتوای فایل:\n{content}",
                system=ROLE_SYSTEM,
            )

        raw = resp.get("response") or resp.get("message") or str(resp)
        parsed = _parse_json(raw)
        parsed["model_used"] = resp.get("model", "unknown")
        return {"ok": True, "result": parsed, "raw": raw}


    except Exception as e:
        logger.exception("role/analyze failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/classify")
async def classify_many(req: ClassifyRequest):
    results = []
    for item in req.files:
        try:
            single = AnalyzeOneRequest(
                role_text=req.role_text,
                file_b64=item.file_b64,
                filename=item.filename,
                is_image=item.is_image,
            )
            r = await analyze_one(single)
            results.append({
                "file_id": item.file_id,
                "ok": True,
                "result": r["result"],
            })
        except Exception as e:
            results.append({
                "file_id": item.file_id,
                "ok": False,
                "error": str(e),
            })
    return {"ok": True, "results": results}