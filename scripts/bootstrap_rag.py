"""Bootstrap RAG: create documents + index them into ChromaDB."""
import hmac
import hashlib
import time
import json
import requests
from pathlib import Path

SECRET = "change-this-to-a-long-random-string-min-32-chars"
BASE = "http://localhost:9000"
ROOT = Path(__file__).parent
RAG_DIR = ROOT / "rag_data"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


# ============================================================
# Documents (English, structured)
# ============================================================
DOCS = {
    "policies/confidentiality.md": """# Organization Confidentiality Policy

## Scope
All internal documents of the organization are classified as confidential, including:
- Financial reports
- Customer lists
- Product pricing sheets
- Contracts and agreements
- Employee records and HR data

## Prohibition
Sharing any of the above outside the organization is a serious violation and
will result in legal action.

## Examples of Violations
- Sending a screenshot of an internal sales dashboard
- Forwarding a customer contact list
- Disclosing internal pricing or discount rules
- Sharing salary or HR documents
""",

    "policies/sales_data.md": """# Sales Data Protection Policy

## Confidential Sales Information
The following must never be shared with unauthorized parties:
- Customer lists and contact details
- Purchase history of any customer
- Special discounts and internal pricing
- Supplier information
- Revenue and margin data

## Prohibited Actions
- Sending screenshots of the sales panel
- Sharing customer lists with third parties
- Revealing internal discount codes
- Discussing supplier pricing publicly

## Reporting
Any suspected leak of sales data must be reported to the admin immediately.
""",

    "policies/chat_rules.md": """# Chat Conduct Rules

## Prohibited Requests
Sellers must never ask buyers for:
- Bank card number, CVV2, or expiry date
- Passwords or one-time codes (OTP)
- National ID card or passport images
- Banking app screenshots

## Interpretation
Any such request is considered a fraud attempt and must be
escalated to the admin.

## Examples of Violations
- "Send your card number to claim the prize"
- "Tell me the SMS code you just received"
- "Send a photo of your national ID"
""",

    "policies/image_rules.md": """# Image Content Policy

## Prohibited Image Content
- Nudity or sexual content
- Violent or gory scenes
- Drug substances (any visible substance, including cigarettes)
- Firearms and weapons
- Threat or extortion screenshots

## Note
Drug-related images must be reported even if the exact substance
is not clearly identifiable.
""",

    "policies/extortion.md": """# Anti-Extortion Policy

## Definition
Any threat to publish private images, personal information,
or private chat logs is considered extortion.

## Action
The case must be reported to the admin immediately and the
offending account must be blocked.

## Common Patterns
- "I have your photos, pay me or I will publish them"
- "I will send our chat to your family"
- "I will sell your information"
""",

    "patterns/fraud_patterns.md": """# Fraud Patterns

## Banking Phishing
- Request for card number, CVV2, or PIN
- Request for OTP / SMS code
- Links to fake bank login pages

## Fake Prizes
- "You have won a prize, send your details"
- "Provide your card number to receive the reward"

## Fake Sales
- Unrealistically low prices
- Pressure to pay before delivery
- Refusal to provide product documents

## Extortion
- Threats to publish private information
- Demanding payment in exchange for silence
""",

    "patterns/sexual_patterns.md": """# Sexual Content and Extortion Patterns

## Requests for Private Images
- "Send me a private photo"
- "Send a photo without clothes"
- "I want a private video"

## Sexual Extortion
- Threatening to publish images
- Demanding money to prevent publication
- Requesting more content in exchange for silence

## Warning Signs
- Unusual pressure to move to another messenger
- Excessive personal questions
- Rapid trust-building followed by requests
""",

    "patterns/drug_patterns.md": """# Drug-Related Content Patterns

## Visual Indicators
- Visible substances (powder, pills, crystals, plants)
- Paraphernalia: syringe, pipe, bong, rolling papers
- Smoking of any kind, including cigarettes

## Contextual Indicators
- Slang terms for substances
- Discussion of prices per gram
- Discussion of delivery methods

## Action
Any of the above must be flagged and reported to the admin.
""",

    "knowledge/organization.md": """# Organization Information

## Legal Framework
The organization operates under the laws of the Islamic Republic of Iran
and the national e-commerce regulations.

## Privacy Policy
User data is protected and will not be published without written consent.

## Violation Reporting Process
Violations detected by the AI service are sent to the admin and
reviewed within 24 hours.
""",
}


# ============================================================
# Helpers
# ============================================================
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
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
    for p in paragraphs:
        if len(current) + len(p) + 2 <= size:
            current = (current + "\n\n" + p).strip()
        else:
            if current:
                chunks.append(current)
            if len(p) > size:
                current = ""
                for s in p.replace(". ", ".\n").split("\n"):
                    if len(current) + len(s) + 1 <= size:
                        current = (current + " " + s).strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = s
            else:
                current = p
    if current:
        chunks.append(current)
    if overlap > 0 and len(chunks) > 1:
        out = [chunks[0]]
        for i in range(1, len(chunks)):
            out.append((chunks[i - 1][-overlap:] + " " + chunks[i]).strip())
        chunks = out
    return chunks


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("STEP 1: Writing RAG documents to disk")
    print("=" * 60)
    for rel, content in DOCS.items():
        p = RAG_DIR / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(f"  written: {rel}")

    print()
    print("=" * 60)
    print("STEP 2: Indexing into ChromaDB via /rag/index")
    print("=" * 60)

    total = 0
    for rel, content in DOCS.items():
        category = rel.split("/")[0]
        chunks = chunk_text(content)
        print(f"\n[{rel}] -> {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            doc_id = f"{rel}#chunk-{i:03d}"
            code, _ = post("/rag/index", {
                "doc_id": doc_id,
                "text": chunk,
                "metadata": {
                    "source": rel,
                    "category": category,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            })
            total += 1
            print(f"  [{code}] {doc_id} ({len(chunk)} chars)")

    print()
    print(f"Indexed {total} chunks from {len(DOCS)} documents.")

    print()
    print("=" * 60)
    print("STEP 3: Testing /rag/query")
    print("=" * 60)
    code, resp = post("/rag/query", {"question": "What is the confidentiality policy?"})
    print(f"[{code}]")
    print(json.dumps(resp, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
