"""Pick a search engine: Google first, DuckDuckGo after a wall or empty page.

The choice is sticky for ten minutes, so a walled Google does not cost one
failed navigation per query inside the same research loop.
"""

from __future__ import annotations

import time
from urllib.parse import quote_plus

from playwright.sync_api import Page

from harness.browser.session import get_session
from harness.browser.state import classify
from harness.search import ddg, google
from harness.search.google import Result

GOOGLE_URL = "https://www.google.com/search?q={query}&hl=en"
DDG_URL = "https://html.duckduckgo.com/html/?q={query}&kl=us-en"
FALLBACK_SECONDS = 600
TIMEOUT_MS = 20_000

# Last status word seen by `search`, so the tool layer can lead with it.
last_status = "OK"

_fallback_until = 0.0


def _now() -> float:
    """Monotonic clock, separate so tests can move it."""
    return time.monotonic()


def reset() -> None:
    """Forget the fallback window and the last status (tests and new sessions)."""
    global _fallback_until, last_status
    _fallback_until = 0.0
    last_status = "OK"


def in_fallback() -> bool:
    """True while DuckDuckGo is preferred over Google."""
    return _now() < _fallback_until


def _run(page: Page, url: str, parser) -> list[Result]:
    global last_status
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
    except Exception:
        last_status = "ERR"
        return []
    status = getattr(response, "status", None) if response is not None else None
    word = classify(page, status=status)
    if word != "OK":
        last_status = word
        return []
    try:
        html = page.content()
    except Exception:
        last_status = "ERR"
        return []
    results = parser(html)
    last_status = "OK"
    return results


def search(query: str, page: Page | None = None) -> list[Result]:
    """Results for ``query``: Google, or DuckDuckGo if Google is walled or empty."""
    global _fallback_until
    query = " ".join((query or "").split())
    if not query:
        return []
    current = page if page is not None else get_session().start().page

    if not in_fallback():
        results = _run(current, GOOGLE_URL.format(query=quote_plus(query)), google.parse)
        if results:
            return results
        # Google is not usable: try the fallback, but only remember it when it
        # actually answers. A walled fallback must not pin every later query.
        results = _run(current, DDG_URL.format(query=quote_plus(query)), ddg.parse)
        _fallback_until = _now() + FALLBACK_SECONDS if results else 0.0
        return results

    results = _run(current, DDG_URL.format(query=quote_plus(query)), ddg.parse)
    if not results:
        # The remembered engine stopped working: probe Google again next time.
        _fallback_until = 0.0
    return results
