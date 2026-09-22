"""نظارت بر چت + راهنمایی کاربر + تحلیل نقشه کلاهبرداری."""
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
    m = re.search(r"\{.*\}", text, re.DOTALL)
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
    chat_text_joined = "\n".join(
        f"{m.get('role','?')}: {m.get('content','')}" for m in messages
    )
    prompt = (
        f"CONTEXT: {context}\n\n"
        f"CHAT HISTORY:\n{chat_text_joined}\n\n"
        "Analyze the LAST message primarily. Return JSON."
    )
    raw = chat_text(prompt, system=MONITOR_SYSTEM)
    try:
        return _extract_json(raw)
    except Exception as e:
        return _fallback(f"Parse error: {e}; raw={raw[:200]}")


def suggest_questions(messages: list[dict]) -> str:
    chat_text_joined = "\n".join(
        f"{m.get('role','?')}: {m.get('content','')}" for m in messages
    )
    return chat_text(chat_text_joined, system=HINT_SYSTEM)
