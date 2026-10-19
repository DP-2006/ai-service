from typing import List

import httpx
from bs4 import BeautifulSoup


def extract_urls_content(urls: List[str]) -> dict:
    """استخراج متن از URLها با httpx + BeautifulSoup."""
    items = []
    for url in urls:
        try:
            r = httpx.get(url, timeout=30, follow_redirects=True)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            items.append({
                "url": url,
                "title": (soup.title.string if soup.title else ""),
                "text": text[:5000],
                "length": len(text),
            })
        except Exception as e:
            items.append({"url": url, "error": str(e), "text": "", "length": 0})
    return {"items": items, "total": len(items)}
