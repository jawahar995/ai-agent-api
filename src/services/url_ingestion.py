from __future__ import annotations

from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

try:
    from langchain_community.document_loaders import AsyncHtmlLoader
except ImportError:  # pragma: no cover - optional dependency path
    AsyncHtmlLoader = None


@dataclass
class UrlExtractionResult:
    url: str
    markdown: str
    word_count: int


async def extract_url_markdown(url: str) -> UrlExtractionResult:
    markdown = ""

    if AsyncHtmlLoader is not None:
        try:
            docs = await AsyncHtmlLoader(web_path=url).aload()
            if docs:
                text_body = "\n\n".join(doc.page_content for doc in docs if doc.page_content)
                markdown = f"# Extracted Content\n\nSource URL: {url}\n\n{text_body.strip()}"
        except Exception:
            markdown = ""

    if not markdown:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        title = (soup.title.string or "Untitled") if soup.title else "Untitled"
        body = " ".join(s.strip() for s in soup.stripped_strings)
        markdown = f"# {title}\n\nSource URL: {url}\n\n{body}"

    word_count = len(markdown.split())
    return UrlExtractionResult(url=url, markdown=markdown, word_count=word_count)
