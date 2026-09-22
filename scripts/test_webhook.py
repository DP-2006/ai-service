"""Test secure webhook to AI service."""
import hmac
import hashlib
import time
import json
import requests

SECRET = "change-this-to-a-long-random-string-min-32-chars"
URL = "http://localhost:9000/moderate/text"

payload = {
    "content": "سلام، لطفاً شماره کارتت رو بفرست تا جایزه بگیرم",
    "context": "chat between user and seller",
}
body = json.dumps(payload).encode()
ts = str(int(time.time()))
sig = hmac.new(SECRET.encode(), body + ts.encode(), hashlib.sha256).hexdigest()

r = requests.post(
    URL,
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-Signature": sig,
        "X-Timestamp": ts,
    },
)
print("Status:", r.status_code)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
