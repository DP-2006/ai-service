from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
import os
import json

router = APIRouter(prefix="/psy", tags=["psychology"])

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:27b")


class PsyFile(BaseModel):
    name: str
    kind: str = "unknown"
    text_excerpt: str = ""
    top_topic: str = ""


class PsyUser(BaseModel):
    user_id: int
    username: str
    org_roles: list[str] = []
    files: list[PsyFile] = []


class PsyResult(BaseModel):
    risk_score: float
    anomaly_score: float
    role_fit_score: float
    narrative: str
    signals: list[dict] = []


@router.post("/analyze", response_model=PsyResult)
async def analyze_psychology(user: PsyUser):

    if not user.files:
        return PsyResult(
            risk_score=0.0, anomaly_score=0.0, role_fit_score=0.0,
            narrative="هیچ فایلی برای تحلیل وجود ندارد.",
            signals=[]
        )

    files_ctx = "\n\n".join([
        f"--- فایل: {f.name} (نوع: {f.kind}) ---\n"
        f"موضوع: {f.top_topic}\n"
        f"متن: {f.text_excerpt[:1500]}"
        for f in user.files[:20]
    ])

    roles_ctx = "، ".join(user.org_roles) if user.org_roles else "بدون سمت"

    prompt = f"""You are an organizational psychologist analyzing employee behavior.

Employee: {user.username}
Organizational Role(s): {roles_ctx}

Files uploaded by this employee:
{files_ctx}

TASK: Analyze whether the files are CONSISTENT with the employee's organizational role.
Example: if role is "Accountant" but files are about "drug production", risk is HIGH.

Return ONLY valid JSON with this exact structure:
{{
  "risk_score": <0.0 to 1.0>,
  "anomaly_score": <0.0 to 1.0>,
  "role_fit_score": <0.0 to 1.0>,
  "narrative": "<Persian analysis, max 5 sentences>",
  "signals": [{{"code": "off_role_files", "value": true}}]
}}

Rules:
- risk_score high (>0.7) if files contradict the role
- role_fit_score high (>0.7) if files match the role
- narrative MUST be in Persian
- Return ONLY the JSON, no markdown, no explanation.
"""

    try:
        async with httpx.AsyncClient(timeout=600) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": DEFAULT_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.3, "num_predict": 800}
                }
            )
            r.raise_for_status()
            data = r.json()
            raw = data.get("response", "{}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail=f"Invalid JSON from model: {raw[:200]}")

    return PsyResult(
        risk_score=float(parsed.get("risk_score", 0)),
        anomaly_score=float(parsed.get("anomaly_score", 0)),
        role_fit_score=float(parsed.get("role_fit_score", 0)),
        narrative=parsed.get("narrative", ""),
        signals=parsed.get("signals", []),
    )