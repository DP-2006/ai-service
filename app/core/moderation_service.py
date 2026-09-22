import json
import re
from app.services.ollama_client import chat_text, chat_vision

SYSTEM_PROMPT = """You are a strict content moderation AI for an organization.
Analyze the given content (text and/or image description) for violations:

CATEGORIES:
1. FRAUD - scam, phishing, extortion, blackmail
2. SEXUAL - sexual content, private images, extortion with intimate media
3. DRUGS - drug use imagery (any visible substance, even cigarettes)
4. CONFIDENTIAL - organizational confidential documents, trade secrets
5. SALES_LEAK - leaking sales data, customer lists, pricing
6. HARASSMENT - threats, abusive language
7. SAFE - no violation

Return ONLY valid JSON (no markdown, no explanation):
{
  "is_violation": true|false,
  "categories": ["FRAUD", ...],
  "confidence": 0.0-1.0,
  "severity": "low|medium|high|critical",
  "reason": "short explanation in English",
  "suggested_action": "allow|flag|block|alert_admin"
}

Be strict. When in doubt, flag for admin review."""

def _extract_json(text: str) -> dict:
    # حذف markdown fences اگر وجود داشت
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    # اولین { ... } معتبر
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in model response")
    return json.loads(match.group(0))

def moderate_text(content: str, context: str = "") -> dict:
    prompt = f"CONTEXT: {context}\n\nCONTENT:\n{content}\n\nReturn JSON."
    raw = chat_text(prompt, system=SYSTEM_PROMPT)
    try:
        return _extract_json(raw)
    except Exception as e:
        return {
            "is_violation": True,
            "categories": ["UNKNOWN"],
            "confidence": 0.0,
            "severity": "medium",
            "reason": f"Parse error: {e}; raw={raw[:200]}",
            "suggested_action": "flag",
        }

def moderate_image(image_b64: str, context: str = "") -> dict:
    prompt = (
        f"CONTEXT: {context}\n\n"
        "Analyze this image strictly. Detect: nudity, sexual content, "
        "drug substances (any visible), confidential documents, sales data, "
        "weapons, violence. Return JSON."
    )
    raw = chat_vision(prompt, [image_b64], system=SYSTEM_PROMPT)
    try:
        return _extract_json(raw)
    except Exception as e:
        return {
            "is_violation": True,
            "categories": ["UNKNOWN"],
            "confidence": 0.0,
            "severity": "medium",
            "reason": f"Parse error: {e}",
            "suggested_action": "flag",
        }