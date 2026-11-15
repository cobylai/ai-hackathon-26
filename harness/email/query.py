"""Turn plain fields into a Gmail search query and a search URL.

The model only ever supplies ``sender``, ``text`` and ``days``; Gmail's own
syntax (``from:``, ``newer_than:``, quoted phrases) is assembled here.
"""

from __future__ import annotations

from urllib.parse import quote

INBOX_URL = "https://mail.google.com/mail/u/0/#inbox"
SEARCH_BASE = "https://mail.google.com/mail/u/0/#search/"


def _phrase(value: object) -> str:
    """Collapse whitespace and quote anything with a space in it."""
    text = " ".join(str(value).split()).replace('"', "").strip()
    if not text:
        return ""
    return f'"{text}"' if " " in text else text


def build(
    sender: str | None = None,
    text: str | None = None,
    days: int | None = None,
    unread: bool = False,
    has_attachment: bool = False,
) -> str:
    """``from:emily "lab safety" newer_than:14d is:unread has:attachment``."""
    parts: list[str] = []
    if sender and (who := _phrase(sender)):
        parts.append(f"from:{who}")
    if text and (words := _phrase(text)):
        parts.append(words)
    if days is not None:
        try:
            count = int(days)
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            parts.append(f"newer_than:{count}d")
    if unread:
        parts.append("is:unread")
    if has_attachment:
        parts.append("has:attachment")
    return " ".join(parts)


def search_url(query: str) -> str:
    """Percent-encode ``query`` into ``#search/``; an empty query is the inbox."""
    query = " ".join(str(query).split())
    if not query:
        return INBOX_URL
    return SEARCH_BASE + quote(query, safe="")
