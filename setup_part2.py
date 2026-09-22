from pathlib import Path
ROOT = Path(__file__).parent

FILES = {}

# ============================================================
# 1) Chat Monitor Service - نظارت بر چت + راهنمایی کاربر
# ============================================================
FILES["app/services/chat_monitor.py"] = '''"""نظارت بر چت + راهنمایی کاربر + تحلیل نقشه کلاهبرداری."""
import json
import re

from app.services.ollama_client import chat_text, chat_vision


MONITOR_SYSTEM = """You are an AI chat moderator for a marketplace (buyer <-> seller).
Your tasks:
1. Detect fraud/scam/phishing/extortion attempts.
2. Detect sexual/private content or blackmail.
3. Detect drug-related content.
4. Detect attempts to leak confidential organization documents or sales data.
5. Detect harassment or threats.
6. Suggest safer/better questions the user could ask.

Return ONLY valid JSON:
{
  "is_violation": true|false,
  "categories": ["FRAUD"|"SEXUAL"|"DRUGS"|"CONFIDENTIAL"|"SALES_LEAK"|"HARASSMENT"|"SAFE"],
  "confidence": 0.0-1.0,
  "severity": "low|medium|high|critical",
  "reason": "short reason",
  "suggested_action": "allow|flag|block|alert_admin",
  "user_hint": "a short, friendly suggestion to the user about what to ask or avoid (in Persian)",
  "admin_summary": "one-line summary for admin"
}
Be strict. When in doubt, flag for admin review."""


HINT_SYSTEM = """You are a helpful assistant that guides marketplace users.
Given the last messages of a chat, suggest 2-3 better/safer questions the user can ask
the other party. Keep it friendly and in Persian. Return plain text (no JSON)."""


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\\{.*\\}", text, re.DOTALL)
    if not m:
        raise ValueError("No JSON found")
    return json.loads(m.group(0))


def _fallback(reason: str) -> dict:
    return {
        "is_violation": True,
        "categories": ["UNKNOWN"],
        "confidence": 0.0,
        "severity": "medium",
        "reason": reason,
        "suggested_action": "flag",
        "user_hint": "",
        "admin_summary": "parse error",
    }


def monitor_chat(messages: list[dict], context: str = "") -> dict:
    """
    messages: [{"role": "user"|"seller", "content": "..."}]
    """
    chat_text_joined = "\\n".join(
        f"{m.get('role','?')}: {m.get('content','')}" for m in messages
    )
    prompt = (
        f"CONTEXT: {context}\\n\\n"
        f"CHAT HISTORY:\\n{chat_text_joined}\\n\\n"
        "Analyze the LAST message primarily. Return JSON."
    )
    raw = chat_text(prompt, system=MONITOR_SYSTEM)
    try:
        return _extract_json(raw)
    except Exception as e:
        return _fallback(f"Parse error: {e}; raw={raw[:200]}")


def suggest_questions(messages: list[dict]) -> str:
    chat_text_joined = "\\n".join(
        f"{m.get('role','?')}: {m.get('content','')}" for m in messages
    )
    return chat_text(chat_text_joined, system=HINT_SYSTEM)
'''

# ============================================================
# 2) Vision Service - تحلیل تصاویر (تفکیک‌شده)
# ============================================================
FILES["app/services/vision_service.py"] = '''"""تحلیل تخصصی تصاویر: برهنگی، مواد مخدر، اسناد محرمانه، فروش."""
import json
import re

from app.services.ollama_client import chat_vision


VISION_SYSTEM = """You are a STRICT image content moderation AI for an organization.
Analyze the image and detect ANY of the following:

1. NUDITY / SEXUAL: any exposed intimate body parts, sexual acts, suggestive content.
2. DRUGS: any visible drug substance or paraphernalia (meth, opium, pills, syringe,
   pipe, bong). Even a plain cigarette must be flagged under DRUGS/SMOKING.
   Report even if the substance is not clearly identifiable.
3. CONFIDENTIAL_DOC: official documents, contracts, ID cards, passports,
   bank statements, salary slips, internal reports.
4. SALES_LEAK: price lists, customer lists, invoices, screenshots of internal
   sales dashboards.
5. VIOLENCE / WEAPONS: guns, knives, blood, gore.
6. EXTORTION: screenshots of chats threatening to leak private images.
7. SAFE: none of the above.

IMPORTANT:
- Be STRICT. Err on the side of flagging.
- The drug substance itself must NOT be described in detail; only its category.
- Output ONLY valid JSON, no markdown, no extra text:

{
  "is_violation": true|false,
  "categories": ["NUDITY"|"SEXUAL"|"DRUGS"|"SMOKING"|"CONFIDENTIAL_DOC"|"SALES_LEAK"|"VIOLENCE"|"WEAPONS"|"EXTORTION"|"SAFE"],
  "confidence": 0.0-1.0,
  "severity": "low|medium|high|critical",
  "reason": "short neutral explanation (no graphic details)",
  "suggested_action": "allow|flag|block|alert_admin",
  "admin_summary": "one-line summary for admin"
}
"""


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\\{.*\\}", text, re.DOTALL)
    if not m:
        raise ValueError("No JSON found")
    return json.loads(m.group(0))


def _fallback(reason: str) -> dict:
    return {
        "is_violation": True,
        "categories": ["UNKNOWN"],
        "confidence": 0.0,
        "severity": "medium",
        "reason": reason,
        "suggested_action": "flag",
        "admin_summary": "parse error",
    }


def analyze_image(image_b64: str, context: str = "") -> dict:
    prompt = f"CONTEXT: {context}\\nAnalyze the image strictly. Return JSON."
    raw = chat_vision(prompt, [image_b64], system=VISION_SYSTEM)
    try:
        return _extract_json(raw)
    except Exception as e:
        return _fallback(f"Parse error: {e}")
'''

# ============================================================
# 3) Alert Service - ارسال هشدار به ادمین (Webhook خروجی)
# ============================================================
FILES["app/services/alert_service.py"] = '''"""ارسال هشدار به ادمین از طریق webhook خروجی (Django)."""
import hmac
import hashlib
import time
import json
import logging

import httpx

from app.core.config import settings

log = logging.getLogger("ai-service.alert")


def _sign(body: bytes, ts: str) -> str:
    return hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body + ts.encode(),
        hashlib.sha256,
    ).hexdigest()


async def send_alert_to_admin(payload: dict) -> bool:
    """
    payload:
      {
        "source": "chat"|"image"|"text",
        "user_id": ...,
        "chat_id": ...,
        "categories": [...],
        "severity": "...",
        "reason": "...",
        "admin_summary": "...",
        "raw_ref": "..."   # id مرجع در سیستم اصلی
      }
    """
    url = getattr(settings, "ADMIN_ALERT_URL", "")
    if not url:
        log.warning("ADMIN_ALERT_URL not set; skipping alert send")
        return False

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ts = str(int(time.time()))
    sig = _sign(body, ts)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": sig,
                    "X-Timestamp": ts,
                },
            )
        return r.status_code < 300
    except Exception as e:
        log.error(f"send_alert_to_admin failed: {e}")
        return False
'''

# ============================================================
# 4) Router: chat
# ============================================================
FILES["app/routers/chat.py"] = '''from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List

from app.core.security import verify_webhook
from app.services.chat_monitor import monitor_chat, suggest_questions
from app.services.alert_service import send_alert_to_admin

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(verify_webhook)],
)


class Message(BaseModel):
    role: str  # "user" | "seller" | "admin"
    content: str


class MonitorIn(BaseModel):
    messages: List[Message]
    context: Optional[str] = ""
    chat_id: Optional[str] = None
    user_id: Optional[str] = None


class HintIn(BaseModel):
    messages: List[Message]


@router.post("/monitor")
async def monitor_ep(payload: MonitorIn):
    result = monitor_chat([m.model_dump() for m in payload.messages], payload.context or "")

    if result.get("suggested_action") in ("block", "alert_admin"):
        await send_alert_to_admin({
            "source": "chat",
            "chat_id": payload.chat_id,
            "user_id": payload.user_id,
            "categories": result.get("categories", []),
            "severity": result.get("severity", "medium"),
            "reason": result.get("reason", ""),
            "admin_summary": result.get("admin_summary", ""),
        })

    return result


@router.post("/hint")
def hint_ep(payload: HintIn):
    text = suggest_questions([m.model_dump() for m in payload.messages])
    return {"hint": text}
'''

# ============================================================
# 5) Router: vision (اختصاصی تصویر)
# ============================================================
FILES["app/routers/vision.py"] = '''from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.security import verify_webhook
from app.services.vision_service import analyze_image
from app.services.alert_service import send_alert_to_admin

router = APIRouter(
    prefix="/vision",
    tags=["vision"],
    dependencies=[Depends(verify_webhook)],
)


class ImageIn(BaseModel):
    image_b64: str
    context: Optional[str] = ""
    user_id: Optional[str] = None
    chat_id: Optional[str] = None


@router.post("/analyze")
async def analyze_ep(payload: ImageIn):
    result = analyze_image(payload.image_b64, payload.context or "")

    if result.get("suggested_action") in ("block", "alert_admin"):
        await send_alert_to_admin({
            "source": "image",
            "chat_id": payload.chat_id,
            "user_id": payload.user_id,
            "categories": result.get("categories", []),
            "severity": result.get("severity", "medium"),
            "reason": result.get("reason", ""),
            "admin_summary": result.get("admin_summary", ""),
        })

    return result
'''

# ============================================================
# 6) به‌روزرسانی main.py
# ============================================================
FILES["app/main.py"] = '''import logging

from fastapi import FastAPI

from app.core.config import settings
from app.routers import health, moderate, rag, chat, vision

logging.basicConfig(level=settings.LOG_LEVEL)
log = logging.getLogger("ai-service")

app = FastAPI(title="AI Moderation Service", version="0.2.0")

app.include_router(health.router)
app.include_router(moderate.router)
app.include_router(rag.router)
app.include_router(chat.router)
app.include_router(vision.router)


@app.on_event("startup")
async def _startup():
    log.info("AI Service starting...")
    log.info(f"Ollama: {settings.OLLAMA_HOST}")
    log.info(f"Chroma: {settings.CHROMA_HOST}:{settings.CHROMA_PORT}")
'''

# ============================================================
# 7) به‌روزرسانی config.py - اضافه شدن ADMIN_ALERT_URL
# ============================================================
FILES["app/core/config.py"] = '''from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OLLAMA_HOST: str = "http://localhost:11434"
    MODEL_TEXT: str = "qwen2.5-coder:7b"
    MODEL_VISION: str = "qwen2.5vl:7b"
    MODEL_EMBED: str = "nomic-embed-text"

    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION: str = "org_knowledge"

    WEBHOOK_SECRET: str = "dev-secret"
    WEBHOOK_MAX_AGE_SECONDS: int = 300

    # خروجی: آدرس Django برای دریافت هشدار ادمین
    ADMIN_ALERT_URL: str = ""

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 9000
    LOG_LEVEL: str = "INFO"


settings = Settings()
'''

# ============================================================
# 8) .env به‌روزرسانی‌شده
# ============================================================
FILES[".env"] = """OLLAMA_HOST=http://localhost:11434
MODEL_TEXT=qwen2.5-coder:7b
MODEL_VISION=qwen2.5vl:7b
MODEL_EMBED=nomic-embed-text

CHROMA_HOST=localhost
CHROMA_PORT=8001
CHROMA_COLLECTION=org_knowledge

WEBHOOK_SECRET=change-this-to-a-long-random-string-min-32-chars
WEBHOOK_MAX_AGE_SECONDS=300

# آدرس Django برای دریافت هشدار (فعلا خالی)
ADMIN_ALERT_URL=

APP_HOST=0.0.0.0
APP_PORT=9000
LOG_LEVEL=INFO
"""


def main():
    for rel, content in FILES.items():
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(f"written: {rel}")


if __name__ == "__main__":
    main()
