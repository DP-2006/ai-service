"""Vision Service - specialized image analysis for policy violations."""
import json
import re

from app.services.ollama_client import chat_vision


VISION_SYSTEM = """You are a STRICT image content moderation AI.
Analyze the image and detect ANY of the following:

1. NUDITY / SEXUAL: any exposed intimate body parts, sexual acts, suggestive content.
2. DRUGS: any visible drug substance or paraphernalia (meth, opium, pills, syringe,
   pipe, bong). Even a plain cigarette must be flagged under DRUGS/SMOKING.
3. CONFIDENTIAL_DOC: official documents, contracts, ID cards, passports,
   bank statements, salary slips, internal reports.
4. SALES_LEAK: price lists, customer lists, invoices, screenshots of internal
   sales dashboards.
5. VIOLENCE / WEAPONS: guns, knives, missiles, rockets, blood, gore.
6. EXTORTION: screenshots of chats threatening to leak private images.
7. SAFE: none of the above.

CRITICAL OUTPUT RULES:
- Output MUST be a single JSON object.
- DO NOT output any text before or after the JSON.
- DO NOT use markdown fences (no ```json).
- DO NOT explain or describe. ONLY JSON.

Output schema (exact):
{"is_violation": true|false, "categories": ["NUDITY"|"SEXUAL"|"DRUGS"|"SMOKING"|"CONFIDENTIAL_DOC"|"SALES_LEAK"|"VIOLENCE"|"WEAPONS"|"EXTORTION"|"SAFE"], "confidence": 0.0-1.0, "severity": "low|medium|high|critical", "reason": "short neutral explanation", "suggested_action": "allow|flag|block|alert_admin", "admin_summary": "one-line summary"}

Example correct output:
{"is_violation": true, "categories": ["WEAPONS"], "confidence": 0.9, "severity": "high", "reason": "Missile launch visible", "suggested_action": "block", "admin_summary": "Missile image detected"}

Now analyze and output ONLY the JSON."""


def _extract_json(text: str) -> dict:
    # Remove markdown fences
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    # Find first { ... } block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON found in: {text[:300]}")
    return json.loads(m.group(0))


def _fallback(reason: str) -> dict:
    return {
        "is_violation": True,
        "categories": ["UNKNOWN"],
        "confidence": 0.0,
        "severity": "medium",
        "reason": reason,
        "suggested_action": "flag",
        "admin_summary": "parse error - manual review",
    }


def analyze_image(image_b64: str, context: str = "") -> dict:
    prompt = f"CONTEXT: {context}\nAnalyze the image. Output ONLY JSON."
    raw = chat_vision(prompt, [image_b64], system=VISION_SYSTEM)
    try:
        return _extract_json(raw)
    except Exception as e:
        return _fallback(f"Parse error: {e}; raw_head={raw[:200]}")
