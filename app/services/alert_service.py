"""ارسال هشدار به ادمین از طریق webhook خروجی (Django)."""
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
