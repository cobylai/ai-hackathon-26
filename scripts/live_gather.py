"""Live check: typed questions through sufficiency.gather with the partner's browser.

    uv run python scripts/live_gather.py "question one" "question two" ...

Search is the partner's harness.search.engine (Google, then DuckDuckGo). If both
answer with a bot check, this script falls back to Bing results read in the same
hidden browser; no challenge is solved or bypassed. Pages are opened with
harness.search.tools.open_page. Every model call goes to local Bonsai via llm.client.
"""
from __future__ import annotations

import base64
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.browser.session import get_session  # noqa: E402
from harness.browser.state import classify  # noqa: E402
from harness.search import engine, tools  # noqa: E402
from sufficiency.gather import gather  # noqa: E402

BING = "https://www.bing.com/search?q={q}&setlang=en"
used: list[str] = []


def _unwrap(href: str) -> str:
    """Bing wraps result links as bing.com/ck/a?...&u=a1<base64url>."""
    p = urlparse(href)
    if p.netloc.endswith("bing.com") and p.path.startswith("/ck/"):
        u = parse_qs(p.query).get("u", [""])[0]
        if u.startswith("a1"):
            b = u[2:]
            try:
                return base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
            except Exception:
                return ""
    return href


_EXTRACT = """() => [...document.querySelectorAll('li.b_algo')].map(li => {
  const a = li.querySelector('h2 a'); const p = li.querySelector('.b_caption p, p');
  return a ? {title: a.innerText.trim(), url: a.href, snippet: p ? p.innerText.trim() : ''} : null;
}).filter(Boolean)"""


def bing(query: str) -> list[dict]:
    page = get_session().start().page
    for _ in range(2):  # Bing may navigate again after the first load
        try:
            resp = page.goto(BING.format(q=quote_plus(query)), wait_until="load",
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
        url = _unwrap(r["url"])
        if url.startswith("http"):
            out.append({**r, "url": url})
    return out


def search(query: str):
    results = engine.search(query)
    if results:
        used.append("google/ddg")
        return results
    used.append(f"bing (engine said {engine.last_status})")
    return bing(query)


def main(questions: list[str]) -> None:
    for q in questions:
        used.clear()
        t0 = time.monotonic()
        r = gather(q, search, tools.open_page, max_seconds=60)
        dt = time.monotonic() - t0
        print(f"\nQ: {q}\n  seconds: {dt:.1f}   search: {', '.join(used)}")
        if r.found:
            print(f"  answer: {r.answer}\n  source: {r.source.url}\n  evidence: {r.evidence}")
        else:
            print(f"  not found: {r.message}")
        print(f"  queries: {r.queries}\n  opened: {r.opened}")
    get_session().stop()


if __name__ == "__main__":
    main(sys.argv[1:])
