"""Professional synthetic dataset generator for AI Moderation Service.

Uses gemma3:27b via Ollama as teacher model to generate diverse
samples across violation categories. Outputs JSONL in chat format
suitable for QLoRA fine-tuning.
"""
import asyncio
import json
import random
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import ollama

# ============================================================
# Configuration
# ============================================================
OLLAMA_HOST = "http://localhost:11434"
TEACHER_MODEL = "gemma3:27b"

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "datasets" / "raw"
PROC_DIR = ROOT / "datasets" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROC_DIR.mkdir(parents=True, exist_ok=True)

client = ollama.Client(host=OLLAMA_HOST)


# ============================================================
# Category definitions
# ============================================================
@dataclass
class Category:
    name: str
    fa_label: str
    description: str
    severity: str
    action: str
    examples_fa: list
    examples_en: list


CATEGORIES = [
    Category(
        name="FRAUD",
        fa_label="کلاهبرداری",
        description="Scam, phishing, fake prizes, requesting bank/card/OTP info, fake sales",
        severity="high",
        action="alert_admin",
        examples_fa=[
            "شماره کارتت رو بفرست تا جایزه بگیری",
            "کد پیامکی که برات اومد رو بگو",
            "برای دریافت جایزه اطلاعات بانکی‌ت رو بده",
        ],
        examples_en=[
            "Send your card number to claim the prize",
            "Tell me the OTP code you just received",
        ],
    ),
    Category(
        name="SEXUAL",
        fa_label="محتوای جنسی",
        description="Sexual content, requests for private images, sexual harassment",
        severity="critical",
        action="block",
        examples_fa=[
            "یه عکس خصوصی بفرست",
            "عکس بدون لباس میخوام",
        ],
        examples_en=[
            "Send me a private photo",
            "Send a photo without clothes",
        ],
    ),
    Category(
        name="EXTORTION",
        fa_label="اخاذی",
        description="Threats to publish private info/images, blackmail, demanding money for silence",
        severity="critical",
        action="alert_admin",
        examples_fa=[
            "عکست رو دارم، اگه پول ندی منتشر می‌کنم",
            "چت‌هامون رو می‌فرستم برای خانوادت",
        ],
        examples_en=[
            "I have your photos, pay or I will publish them",
            "I will send our chat to your family",
        ],
    ),
    Category(
        name="DRUGS",
        fa_label="مواد مخدر",
        description="Any mention or image of drug substances, paraphernalia, or smoking",
        severity="high",
        action="alert_admin",
        examples_fa=[
            "قیمت شیشه چنده؟",
            "یه بسته گل میخوام",
        ],
        examples_en=[
            "How much for meth?",
            "I need a pack of weed",
        ],
    ),
    Category(
        name="CONFIDENTIAL",
        fa_label="اسناد محرمانه",
        description="Organizational confidential documents, contracts, IDs, financial reports",
        severity="high",
        action="alert_admin",
        examples_fa=[
            "این قرارداد داخلی رو ببین",
            "لیست حقوق کارکنان رو دارم",
        ],
        examples_en=[
            "Here is the internal contract",
            "I have the employee salary list",
        ],
    ),
    Category(
        name="SALES_LEAK",
        fa_label="افشای اطلاعات فروش",
        description="Leaking customer lists, pricing, discounts, supplier info",
        severity="medium",
        action="flag",
        examples_fa=[
            "لیست مشتریان رو برات می‌فرستم",
            "قیمت عمده چنده؟",
        ],
        examples_en=[
            "I will send the customer list",
            "What is the wholesale price?",
        ],
    ),
    Category(
        name="HARASSMENT",
        fa_label="آزار و تهدید",
        description="Threats, abusive language, insults, intimidation",
        severity="high",
        action="flag",
        examples_fa=[
            "می‌دونم کجا زندگی می‌کنی",
            "بهت نشون می‌دم",
        ],
        examples_en=[
            "I know where you live",
            "I will make you pay",
        ],
    ),
    Category(
        name="VIOLENCE",
        fa_label="خشونت",
        description="Violence, gore, threats of physical harm",
        severity="critical",
        action="alert_admin",
        examples_fa=[
            "میکشمت",
            "خونت رو میریزم",
        ],
        examples_en=[
            "I will kill you",
            "I will spill your blood",
        ],
    ),
    Category(
        name="WEAPONS",
        fa_label="سلاح",
        description="Firearms, knives, explosives, weapon sales",
        severity="critical",
        action="alert_admin",
        examples_fa=[
            "کلت میخوام بخرم",
            "یه چاقو جنگی داری؟",
        ],
        examples_en=[
            "I want to buy a gun",
            "Do you have a combat knife?",
        ],
    ),
    Category(
        name="NUDITY",
        fa_label="برهنگی",
        description="Nudity, explicit imagery",
        severity="critical",
        action="block",
        examples_fa=["عکس برهنه بفرست"],
        examples_en=["Send a nude photo"],
    ),
    Category(
        name="SAFE",
        fa_label="ایمن",
        description="Normal, safe conversation about buying/selling products",
        severity="low",
        action="allow",
        examples_fa=[
            "سلام، این محصول موجوده؟",
            "قیمتش چنده؟",
            "گارانتی داره؟",
        ],
        examples_en=[
            "Hi, is this product available?",
            "What is the price?",
        ],
    ),
]


# ============================================================
# Generation prompt
# ============================================================
GENERATOR_SYSTEM = """You are a dataset generator for an AI content moderation system.
Generate realistic chat messages from a marketplace (buyer <-> seller) in Persian (Farsi).

CRITICAL RULES:
- Output ONLY a valid JSON array of objects. No markdown, no explanation.
- Each object must have exactly these fields: "text", "role", "variation"
- "text": the message (mostly Persian, sometimes with English words, emoji, or broken spelling)
- "role": "user" | "seller"
- "variation": a short label describing the style (e.g., "formal", "casual", "slang", "typo", "emoji")

Generate DIVERSE samples with different:
- Lengths (very short 3 words, medium, long)
- Tones (polite, aggressive, casual, desperate)
- Spellings (correct, broken, with typos)
- Languages (Persian, mixed Persian-English, some English)
"""


def build_prompt(category: Category, count: int, variation_hint: str = "") -> str:
    examples = "\n".join(f"- {ex}" for ex in category.examples_fa[:3])
    return f"""Generate {count} diverse marketplace chat messages that belong to the category: {category.name} ({category.fa_label}).

Description: {category.description}

Example messages (DO NOT copy exactly, generate NEW variations):
{examples}

{variation_hint}

Remember: output ONLY a JSON array. Each item: {{"text": "...", "role": "user"|"seller", "variation": "..."}}"""


# ============================================================
# Core generation
# ============================================================
def _extract_json_array(text: str) -> Optional[list]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        return None
    return None


def generate_batch(category: Category, count: int, variation_hint: str = "") -> list:
    prompt = build_prompt(category, count, variation_hint)
    try:
        resp = client.chat(
            model=TEACHER_MODEL,
            messages=[
                {"role": "system", "content": GENERATOR_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.9, "num_predict": 2048},
        )
        raw = resp["message"]["content"]
    except Exception as e:
        print(f"    [ERROR] Ollama call failed: {e}")
        return []

    arr = _extract_json_array(raw)
    if not arr:
        print(f"    [WARN] Could not parse JSON from model response")
        return []

    cleaned = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        role = item.get("role", "user")
        variation = item.get("variation", "unknown")
        if len(text) < 3:
            continue
        if role not in ("user", "seller"):
            role = "user"
        cleaned.append({
            "text": text,
            "role": role,
            "variation": variation,
            "category": category.name,
            "severity": category.severity,
            "action": category.action,
        })
    return cleaned


# ============================================================
# Output format (chat-format for training)
# ============================================================
SYSTEM_PROMPT_FOR_TRAINING = """You are a strict content moderation AI for an organization's marketplace.
Analyze the given message and return ONLY a valid JSON object with this exact schema:
{"is_violation": bool, "categories": [str], "confidence": 0.0-1.0, "severity": "low|medium|high|critical", "reason": str, "suggested_action": "allow|flag|block|alert_admin"}
Do not output markdown, explanations, or any text outside the JSON."""


def to_training_sample(sample: dict) -> dict:
    expected = {
        "is_violation": sample["category"] != "SAFE",
        "categories": [sample["category"]],
        "confidence": round(random.uniform(0.85, 0.99), 2),
        "severity": sample["severity"],
        "reason": f"Detected {sample['category']} pattern in the message.",
        "suggested_action": sample["action"],
    }
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_FOR_TRAINING},
            {"role": "user", "content": sample["text"]},
            {"role": "assistant", "content": json.dumps(expected, ensure_ascii=False)},
        ],
        "metadata": {
            "category": sample["category"],
            "severity": sample["severity"],
            "variation": sample.get("variation", "unknown"),
            "role": sample.get("role", "user"),
        },
    }


# ============================================================
# Main pipeline
# ============================================================
VARIATION_HINTS = [
    "Focus on FORMAL, polite style.",
    "Focus on CASUAL, everyday chat style.",
    "Focus on SLANG and street language.",
    "Focus on messages with TYPOS and broken spelling.",
    "Focus on messages with EMOJI and slang.",
    "Focus on SHORT messages (3-6 words).",
    "Focus on LONGER messages (2-3 sentences).",
    "Mix Persian with some English words.",
]


def main(target_per_category: int = 200, batch_size: int = 20):
    print("=" * 70)
    print(f"Synthetic Dataset Generator")
    print(f"Teacher model: {TEACHER_MODEL}")
    print(f"Target: {target_per_category} samples per category")
    print(f"Categories: {len(CATEGORIES)}")
    print(f"Total target: ~{target_per_category * len(CATEGORIES)} samples")
    print("=" * 70)

    all_samples = []
    stats = {"per_category": {}, "total": 0, "started_at": time.time()}

    for ci, category in enumerate(CATEGORIES, 1):
        print(f"\n[{ci}/{len(CATEGORIES)}] Generating for: {category.name} ({category.fa_label})")
        collected = []
        attempt = 0
        max_attempts = (target_per_category // batch_size) * 3

        while len(collected) < target_per_category and attempt < max_attempts:
            attempt += 1
            hint = VARIATION_HINTS[(attempt - 1) % len(VARIATION_HINTS)]
            need = min(batch_size, target_per_category - len(collected))
            print(f"  batch {attempt} (need {need}, have {len(collected)}) | hint: {hint[:40]}...")

            batch = generate_batch(category, need, hint)
            if not batch:
                time.sleep(2)
                continue

            collected.extend(batch)
            print(f"    -> got {len(batch)}, total {len(collected)}")

        stats["per_category"][category.name] = len(collected)
        print(f"  DONE: {category.name} -> {len(collected)} samples")
        all_samples.extend(collected)

        # ذخیره تدریجی
        with open(RAW_DIR / "generated.jsonl", "w", encoding="utf-8") as f:
            for s in all_samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

    stats["total"] = len(all_samples)
    stats["finished_at"] = time.time()
    stats["duration_seconds"] = round(stats["finished_at"] - stats["started_at"], 1)

    print("\n" + "=" * 70)
    print(f"TOTAL GENERATED: {stats['total']} samples")
    print(f"DURATION: {stats['duration_seconds']} seconds")
    print("=" * 70)

    # تبدیل به فرمت chat برای آموزش
    print("\nConverting to training format...")
    training_samples = [to_training_sample(s) for s in all_samples]

    # Split
    random.seed(42)
    random.shuffle(training_samples)
    n = len(training_samples)
    n_train = int(n * 0.8)
    n_val = int(n * 0.1)

    train = training_samples[:n_train]
    val = training_samples[n_train:n_train + n_val]
    test = training_samples[n_train + n_val:]

    def write_jsonl(path, data):
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    write_jsonl(PROC_DIR / "train.jsonl", train)
    write_jsonl(PROC_DIR / "val.jsonl", val)
    write_jsonl(PROC_DIR / "test.jsonl", test)

    with open(ROOT / "datasets" / "stats.json", "w", encoding="utf-8") as f:
        json.dump({
            "stats": stats,
            "splits": {"train": len(train), "val": len(val), "test": len(test)},
            "categories": [c.name for c in CATEGORIES],
        }, f, ensure_ascii=False, indent=2)

    print(f"\nSaved:")
    print(f"  raw:       {RAW_DIR / 'generated.jsonl'}")
    print(f"  train:     {PROC_DIR / 'train.jsonl'} ({len(train)})")
    print(f"  val:       {PROC_DIR / 'val.jsonl'} ({len(val)})")
    print(f"  test:      {PROC_DIR / 'test.jsonl'} ({len(test)})")
    print(f"  stats:     {ROOT / 'datasets' / 'stats.json'}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-category", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()

    main(target_per_category=args.per_category, batch_size=args.batch_size)
