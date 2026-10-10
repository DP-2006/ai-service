from __future__ import annotations

from typing import List, Dict
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


DEFAULT_TIMEOUT = 20
MAX_CONTENT_CHARS = 50000


def _validate_url(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme: {url}")

    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")


def extract_url_content(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_chars: int = MAX_CONTENT_CHARS,
) -> Dict:

    _validate_url(url)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/154.0 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=timeout,
        allow_redirects=True,
    )

    response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()

    if "text/html" not in content_type:
        raise ValueError(
            f"URL does not contain HTML content: {content_type}"
        )

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove useless HTML elements.
    for tag in soup([
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "iframe",
        "nav",
        "footer",
        "header",
        "form",
        "aside",
    ]):
        tag.decompose()

    title = ""

    if soup.title:
        title = soup.title.get_text(" ", strip=True)

    # Prefer article/main content.
    main = (
        soup.find("article")
        or soup.find("main")
        or soup.body
        or soup
    )

    text = main.get_text(
        separator="\n",
        strip=True,
    )

    lines = []

    for line in text.splitlines():

        line = " ".join(line.split())

        if not line:
            continue

        if len(line) < 2:
            continue

        lines.append(line)

    cleaned_text = "\n".join(lines)

    if len(cleaned_text) > max_chars:
        cleaned_text = cleaned_text[:max_chars]

    if not cleaned_text.strip():
        raise ValueError(
            "No useful text could be extracted from the webpage."
        )

    return {
        "url": url,
        "final_url": response.url,
        "title": title,
        "text": cleaned_text,
        "content_length": len(cleaned_text),
    }


def extract_urls_content(
    urls: List[str],
    timeout: int = DEFAULT_TIMEOUT,
    max_chars_per_url: int = MAX_CONTENT_CHARS,
) -> Dict:

    results = []
    errors = []

    for url in urls:

        url = url.strip()

        if not url:
            continue

        try:

            result = extract_url_content(
                url=url,
                timeout=timeout,
                max_chars=max_chars_per_url,
            )

            results.append(result)

        except Exception as exc:

            errors.append({
                "url": url,
                "error": str(exc),
            })

    combined_parts = []

    for item in results:

        combined_parts.append(
            f"""
===== SOURCE =====

Title:
{item["title"]}

URL:
{item["final_url"]}

Content:
{item["text"]}

===== END SOURCE =====
""".strip()
        )

    combined_text = "\n\n".join(combined_parts)

    return {
        "sources": results,
        "errors": errors,
        "combined_text": combined_text,
        "source_count": len(results),
        "error_count": len(errors),
    }