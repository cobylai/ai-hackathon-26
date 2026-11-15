"""search_fn for gather(): the partner's search first, Bing when that comes back empty.

    from sufficiency.websearch import search
    search("capital of Australia") -> [{"title", "url", "snippet"}, ...]

harness.search.engine.search tries Google, then DuckDuckGo. On some networks
both show a bot check (harness reports BLOCKED); then this reads Bing results
in the same hidden browser. No bot check is solved or bypassed, and harness/
is not changed.
"""
from __future__ import annotations

import base64
from urllib.parse import parse_qs, quote_plus, urlparse

BING_URL = "https://www.bing.com/search?q={q}&setlang=en"

# Last engine used, for logs: "harness" or "bing (harness said BLOCKED)".
last_engine = ""

_EXTRACT = """() => [...document.querySelectorAll('li.b_algo')].map(li => {
  const a = li.querySelector('h2 a'); const p = li.querySelector('.b_caption p, p');
  return a ? {title: a.innerText.trim(), url: a.href, snippet: p ? p.innerText.trim() : ''} : null;
}).filter(Boolean)"""


def _unwrap(href: str) -> str:
    """Bing may wrap links as bing.com/ck/a?...&u=a1<base64url target>."""
    p = urlparse(href or "")
    if p.netloc.endswith("bing.com") and p.path.startswith("/ck/"):
        u = parse_qs(p.query).get("u", [""])[0]
        if not u.startswith("a1"):
            return ""
        b = u[2:]
        try:
            return base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
        except Exception:
            return ""
    return href or ""


def _partner(query: str) -> tuple[list[dict], str]:
    from harness.search import engine

    rows = engine.search(query)
    return ([{"title": r.title, "url": r.url, "snippet": r.snippet} for r in rows],
            engine.last_status)


def _bing(query: str) -> list[dict]:
    from harness.browser.session import get_session
    from harness.browser.state import classify

    page = get_session().start().page
    rows: list[dict] = []
    for _ in range(2):  # Bing may navigate again after the first load
        try:
            resp = page.goto(BING_URL.format(q=quote_plus(query)), wait_until="load",
                             timeout=20_000)
            if classify(page, status=getattr(resp, "status", None)) != "OK":
                return []
            page.wait_for_selector("li.b_algo", timeout=5_000)
            rows = page.evaluate(_EXTRACT)
            break
        except Exception:
            rows = []
    out = []
    for r in rows:
        url = _unwrap(r.get("url", ""))
        if url.startswith("http"):
            out.append({"title": r.get("title", ""), "url": url, "snippet": r.get("snippet", "")})
    return out


def search(query: str) -> list[dict]:
    global last_engine
    try:
        rows, status = _partner(query)
    except Exception:
        rows, status = [], "ERR"
    if rows:
        last_engine = "harness"
        return rows
    last_engine = f"bing (harness said {status})"
    return _bing(query)
