import hmac
import hashlib
import time
from fastapi import Header, HTTPException, Request

from app.core.config import settings


async def verify_webhook(
    request: Request,
    x_signature: str = Header(...),
    x_timestamp: str = Header(...),
):
    try:
        ts = int(x_timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")

    if abs(time.time() - ts) > settings.WEBHOOK_MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Timestamp expired")

    body = await request.body()
    expected = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body + x_timestamp.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(x_signature, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")

    return True
