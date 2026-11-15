"""search_fn for gather(): the harness search first, Bing when that comes back empty.

    from sufficiency.websearch import search
    search("capital of Australia") -> [{"title", "url", "snippet"}, ...]

harness.search.engine.search tries Google, then DuckDuckGo. On some networks
both show a bot check (harness reports BLOCKED); then this reads Bing results
in the same hidden browser. No bot check is solved or bypassed, and harness/
is not changed.

Bing sometimes hands the headless browser results that have nothing to do with
the query ("first president of Kenya" -> ten visitprague.cz pages). Hits that
share too few words with the query are dropped, and when fewer than MIN_GOOD
are left, Wikipedia's public search API (plain HTTPS) fills in.
"""
from __future__ import annotations

import base64
import html
import json
import math
import re
import urllib.request
from urllib.parse import parse_qs, quote, quote_plus, urlencode, urlparse

BING_URL = "https://www.bing.com/search?q={q}&setlang=en"
WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_PAGE = "https://en.wikipedia.org/wiki/"
WIKI_UA = "flux-local-assistant/0.1"
WIKI_RESULTS = 5
MIN_GOOD = 3   # fewer relevant hits than this -> add Wikipedia's

_STOP = set("""a an the and or of to in on at for by with from is are was were be been do does
did can could will would should i me my you your we our it its this that these those what
when where which who whom why how there here any some about into than then so if not no yes
get got have has had am per""".split())

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


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) >= 3 and w not in _STOP}


def _close(a: str, b: str) -> bool:
    """Same word, or one is a 4+ letter prefix of the other (president/presidents)."""
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


def relevant(query: str, row: dict) -> bool:
    """True when the hit shares at least half of the query's content words (at least one)."""
    qw = _words(query)
    if not qw:
        return True
    hw = _words(f"{row.get('title', '')} {row.get('snippet', '')} {row.get('url', '')}")
    shared = sum(1 for q in qw if any(_close(q, h) for h in hw))
    return shared >= max(1, math.ceil(len(qw) / 2))


def _wikipedia(query: str) -> list[dict]:
    """Wikipedia's public search API -> [{title, url, snippet}]. [] on any failure."""
    url = WIKI_API + "?" + urlencode({"action": "query", "list": "search", "srsearch": query,
                                      "srlimit": WIKI_RESULTS, "format": "json", "utf8": 1})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": WIKI_UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
    except Exception:
        return []
    out = []
    for h in (data.get("query") or {}).get("search") or []:
        title = str(h.get("title") or "")
        if not title:
            continue
        snippet = html.unescape(re.sub(r"<[^>]+>", "", str(h.get("snippet") or "")))
        out.append({"title": title, "url": WIKI_PAGE + quote(title.replace(" ", "_")),
                    "snippet": snippet})
    return out


def search(query: str) -> list[dict]:
    global last_engine
    try:
        rows, status = _partner(query)
    except Exception:
        rows, status = [], "ERR"
    if rows:
        last_engine = "harness"
    else:
        last_engine = f"bing (harness said {status})"
        try:
            rows = _bing(query)
        except Exception:
            rows = []
    good = [r for r in rows if relevant(query, r)]
    if len(good) < MIN_GOOD:
        seen = {r["url"] for r in good}
        wiki = [r for r in _wikipedia(query) if r["url"] not in seen]
        if wiki:
            last_engine += f", {len(rows) - len(good)} off-topic dropped, + wikipedia"
        good += wiki
    return good
