import base64
import json
import re
from io import BytesIO

import requests
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
import pptx.enum.shapes


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma3:27b"


def _clean_json(text: str) -> str:
    """
    Remove markdown code fences if Gemma returns ```json ... ```
    """
    text = text.strip()

    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    return text.strip()


def generate_presentation_plan(
    topic: str,
    context_text: str,
    slide_count: int = 10,
    language: str = "fa",
    style: str = "academic",
):
    slide_count = max(3, min(int(slide_count), 30))

    prompt = f"""
You are a professional presentation designer.

Create a PowerPoint presentation based ONLY on the provided source material.

IMPORTANT RULES:
1. Do NOT invent facts that are not supported by the source material.
2. The presentation must have exactly {slide_count} slides.
3. Language: {language}
4. Style: {style}
5. Keep slide text concise.
6. Each content slide should have a title and 3-6 bullet points.
7. Include a final "Sources" slide.
8. Do not write markdown.
9. Return ONLY valid JSON.
10. Do not put ```json around the response.

Required JSON structure:

{{
  "title": "Presentation title",
  "subtitle": "Short subtitle",
  "slides": [
    {{
      "type": "title",
      "title": "Title",
      "subtitle": "Subtitle"
    }},
    {{
      "type": "content",
      "title": "Slide title",
      "bullets": [
        "Bullet 1",
        "Bullet 2",
        "Bullet 3"
      ]
    }},
    {{
      "type": "sources",
      "title": "Sources",
      "bullets": [
        "Source 1"
      ]
    }}
  ]
}}

TOPIC:
{topic}

SOURCE MATERIAL:
{context_text}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You generate structured PowerPoint plans. "
                        "Always return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
            },
        },
        timeout=300,
    )

    response.raise_for_status()

    data = response.json()

    content = data.get("message", {}).get("content", "")

    if not content:
        raise RuntimeError("Ollama returned an empty response.")

    content = _clean_json(content)

    try:
        plan = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemma returned invalid JSON: {content[:1000]}"
        ) from exc

    if "slides" not in plan:
        raise RuntimeError("Generated presentation has no slides.")

    return plan


def _set_font(text_frame, size=22, bold=False):
    for paragraph in text_frame.paragraphs:
        paragraph.alignment = PP_ALIGN.RIGHT

        for run in paragraph.runs:
            run.font.name = "Tahoma"
            run.font.size = Pt(size)
            run.font.bold = bold


def _add_title_slide(prs, title, subtitle):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    title_box = slide.shapes.add_textbox(
        Inches(1),
        Inches(2),
        Inches(11.3),
        Inches(1.5),
    )

    tf = title_box.text_frame
    tf.text = title
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER

    for run in tf.paragraphs[0].runs:
        run.font.name = "Tahoma"
        run.font.size = Pt(34)
        run.font.bold = True

    subtitle_box = slide.shapes.add_textbox(
        Inches(1.5),
        Inches(4),
        Inches(10.3),
        Inches(1),
    )

    tf = subtitle_box.text_frame
    tf.text = subtitle or ""
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER

    for run in tf.paragraphs[0].runs:
        run.font.name = "Tahoma"
        run.font.size = Pt(20)

    return slide


def _add_content_slide(prs, title, bullets):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Title
    title_box = slide.shapes.add_textbox(
        Inches(0.7),
        Inches(0.4),
        Inches(12),
        Inches(0.8),
    )

    tf = title_box.text_frame
    tf.text = title
    tf.paragraphs[0].alignment = PP_ALIGN.RIGHT

    for run in tf.paragraphs[0].runs:
        run.font.name = "Tahoma"
        run.font.size = Pt(28)
        run.font.bold = True

    # Content
    content_box = slide.shapes.add_textbox(
        Inches(1),
        Inches(1.5),
        Inches(11),
        Inches(5),
    )

    tf = content_box.text_frame
    tf.clear()

    for index, bullet in enumerate(bullets[:6]):
        if index == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()

        p.text = str(bullet)
        p.level = 0
        p.alignment = PP_ALIGN.RIGHT
        p.space_after = Pt(14)

        for run in p.runs:
            run.font.name = "Tahoma"
            run.font.size = Pt(21)

    return slide


def _add_sources_slide(prs, title, bullets):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    title_box = slide.shapes.add_textbox(
        Inches(0.7),
        Inches(0.4),
        Inches(12),
        Inches(0.8),
    )

    tf = title_box.text_frame
    tf.text = title or "Sources"

    for run in tf.paragraphs[0].runs:
        run.font.name = "Tahoma"
        run.font.size = Pt(28)
        run.font.bold = True

    content_box = slide.shapes.add_textbox(
        Inches(1),
        Inches(1.5),
        Inches(11),
        Inches(5),
    )

    tf = content_box.text_frame
    tf.clear()

    for index, bullet in enumerate(bullets):
        if index == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()

        p.text = str(bullet)
        p.alignment = PP_ALIGN.RIGHT
        p.space_after = Pt(12)

        for run in p.runs:
            run.font.name = "Tahoma"
            run.font.size = Pt(18)

    return slide


def build_pptx(plan: dict) -> bytes:
    prs = Presentation()

    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    slides = plan.get("slides", [])

    for slide_data in slides:
        slide_type = slide_data.get("type", "content")

        if slide_type == "title":
            _add_title_slide(
                prs,
                slide_data.get("title", plan.get("title", "")),
                slide_data.get("subtitle", plan.get("subtitle", "")),
            )

        elif slide_type == "sources":
            _add_sources_slide(
                prs,
                slide_data.get("title", "Sources"),
                slide_data.get("bullets", []),
            )

        else:
            _add_content_slide(
                prs,
                slide_data.get("title", ""),
                slide_data.get("bullets", []),
            )

    output = BytesIO()
    prs.save(output)

    return output.getvalue()


def generate_presentation(
    topic: str,
    context_text: str,
    slide_count: int = 10,
    language: str = "fa",
    style: str = "academic",
):
    plan = generate_presentation_plan(
        topic=topic,
        context_text=context_text,
        slide_count=slide_count,
        language=language,
        style=style,
    )

    pptx_bytes = build_pptx(plan)

    encoded = base64.b64encode(pptx_bytes).decode("utf-8")

    return {
        "filename": f"{topic[:50] or 'presentation'}.pptx",
        "presentation": plan,
        "file_base64": encoded,
    }