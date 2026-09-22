import hmac, hashlib, time, json, requests

SECRET = "change-this-to-a-long-random-string-min-32-chars"
BASE = "http://localhost:9000"

def post(path, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ts = str(int(time.time()))
    sig = hmac.new(SECRET.encode(), body + ts.encode(), hashlib.sha256).hexdigest()
    r = requests.post(
        BASE + path,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": sig,
            "X-Timestamp": ts,
        },
    )
    print(path, "->", r.status_code)
    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(r.text)
    print("-" * 60)

# 1) تست چت مشکوک
post("/chat/monitor", {
    "messages": [
        {"role": "user", "content": "سلام این محصول موجوده؟"},
        {"role": "seller", "content": "بله، اول شماره کارتت رو بفرست تا جایزه بگیری"},
    ],
    "context": "marketplace buyer/seller",
    "chat_id": "chat-001",
    "user_id": "user-123",
})

# 2) راهنمای سوال
post("/chat/hint", {
    "messages": [
        {"role": "user", "content": "میخوام یه گوشی بخرم"},
    ],
})

# 3) RAG query
post("/rag/query", {"question": "قوانین محرمانگی سازمان چیست؟"})
