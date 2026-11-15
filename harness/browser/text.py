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

# If extraction keeps less than this share of a page with real body text
# (index pages, search results), use the body text instead.
BODY_FALLBACK_RATIO = 0.2
BODY_FALLBACK_MIN = 600


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
    for tag in doc.xpath("//script|//style|//noscript|//template"):
        tag.drop_tree()
    body = doc.body if doc.body is not None else doc
    return "\n".join(part.strip() for part in body.itertext() if part.strip())


# On index pages, lines this short are almost always menu labels.
MIN_BODY_LINE = 20


def _clean_body(body: str) -> str:
    """Drop menu-label lines from body text used on index pages."""
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    kept = [line for line in lines if len(line) >= MIN_BODY_LINE]
    return "\n".join(kept if kept else lines)


def _pick_text(extracted: str | None, body: str) -> str:
    """Prefer the extracted article unless it is a sliver of the page.

    News homepages and search-result pages have no single article for
    trafilatura to find, but their visible body text is what the model needs.
    """
    if not extracted or not extracted.strip():
        return _clean_body(body)
    if len(body) >= BODY_FALLBACK_MIN and len(extracted) < BODY_FALLBACK_RATIO * len(body):
        return _clean_body(body)
    return extracted


def page_text(html: str, body_text: str | None = None) -> str:
    """Extract the main text, dropping nav, ads and footer when possible.

    ``body_text`` is the browser's ``innerText`` when the caller has a page;
    it is both the last-resort fallback and the reference for deciding that an
    extraction is too small to be the page's real content.
    """
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
    body = body_text if body_text is not None else _fallback_text(html)
    return _normalize(_pick_text(extracted, body))


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
