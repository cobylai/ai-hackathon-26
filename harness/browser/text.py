"""Main-text extraction and char-capped paging.

``page_text`` turns raw HTML into readable text; ``paginate`` cuts that text
into pages of at most ``MAX_CHARS`` without ever splitting a word.
"""

from __future__ import annotations

import re

import trafilatura
from lxml import html as lxml_html

from harness import config

# Break preferences, strongest first: paragraph, sentence, word.
_BREAKS = ("\n\n", ". ", "! ", "? ", ".\n", "\n", " ")


def _normalize(text: str) -> str:
    """Collapse blank lines and repeated whitespace, keep paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t\f\v\u00a0]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fallback_text(html: str) -> str:
    """Approximate ``document.body.innerText`` without a browser."""
    try:
        doc = lxml_html.fromstring(html)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    body = doc.body if doc.body is not None else doc
    return body.text_content()


def page_text(html: str) -> str:
    """Extract the main article text, dropping nav, ads and footer."""
    extracted: str | None = None
    try:
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )
    except Exception:
        extracted = None
    if not extracted or not extracted.strip():
        extracted = _fallback_text(html)
    return _normalize(extracted)


def _find_break(text: str, start: int, limit: int, max_chars: int) -> int:
    """Return the end index of the current page, at or before ``limit``."""
    floor = start + max(1, max_chars // 2)
    for separator in _BREAKS:
        pos = text.rfind(separator, floor, limit)
        if pos != -1:
            return pos + len(separator)
    return limit


def paginate(
    text: str,
    page: int = 1,
    max_chars: int = config.MAX_CHARS,
) -> tuple[str, int]:
    """Return ``(chunk, total_pages)``; chunks join back into the full text."""
    text = _normalize(text)
    if not text:
        return "", 1
    max_chars = max(1, int(max_chars))
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1

    spans: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        if len(text) - start <= max_chars:
            end = len(text)
        else:
            end = _find_break(text, start, start + max_chars, max_chars)
        spans.append((start, end))
        start = end

    if page > len(spans):
        return "", len(spans)
    begin, finish = spans[page - 1]
    return text[begin:finish], len(spans)
