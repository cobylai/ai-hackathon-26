"""gather(): search, open, judge, rephrase, give up cleanly.

search_fn and open_fn are passed in (see docs/INTERFACES.md §2). Their shapes are
assumed only in _hits() and _page() below:
    search_fn(query) -> [{"title", "url", "snippet"}, ...]
    open_fn(url)     -> {"title", "text"}   (a plain string is also accepted)
The partner's real shapes are accepted too (harness/search):
    engine.search(q)    -> [Result(title, url, domain, snippet), ...]
    tools.open_page(u)  -> (status_word, text); text is used only when status is "OK"
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date

from .judge import Verdict, judge
from .junk import blocked_page, looks_blocked
from .rephrase import rephrase


@dataclass
class Hit:
    title: str
    url: str
    snippet: str = ""


@dataclass
class Page:
    title: str
    text: str


@dataclass
class GatherResult:
    found: bool
    answer: str | None
    evidence: str | None
    source: Hit | None
    queries: list[str] = field(default_factory=list)
    opened: list[str] = field(default_factory=list)
    verdicts: list[Verdict] = field(default_factory=list)
    message: str = ""


# ---- adapter: the only place that knows the browser's shapes ----

def _hits(raw) -> list[Hit]:
    out = []
    for h in raw or []:
        if isinstance(h, Hit):
            out.append(h)
        elif isinstance(h, dict):
            if h.get("url"):
                out.append(Hit(str(h.get("title") or ""), str(h["url"]),
                               str(h.get("snippet") or "")))
        elif isinstance(h, (list, tuple)) and len(h) >= 2:
            out.append(Hit(str(h[0]), str(h[1]), str(h[2]) if len(h) > 2 else ""))
        elif getattr(h, "url", None):  # harness.search Result(title, url, domain, snippet)
            out.append(Hit(str(getattr(h, "title", "") or ""), str(h.url),
                           str(getattr(h, "snippet", "") or "")))
    return out


def _page(raw) -> Page:
    if isinstance(raw, Page):
        return raw
    if isinstance(raw, str):
        return Page("", raw)
    if isinstance(raw, dict):
        return Page(str(raw.get("title") or ""), str(raw.get("text") or ""))
    if isinstance(raw, (list, tuple)) and len(raw) == 2:  # harness open_page: (status, text)
        status, text = raw
        return Page("", str(text or "") if status == "OK" else "")
    return Page("", "")

# ----------------------------------------------------------------

_STOP = set("""a an the and or of to in on at for by with from is are was were be been do does
did can could will would should i me my you your we our it its this that these those what
when where which who whom why how there here any some about into than then so if not no yes
get got have has had am""".split())


def _content_words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) >= 3 and w not in _STOP}


def _order(question: str, hits: list[Hit]) -> list[Hit]:
    """Keep search order; hits sharing no content word with the question go last."""
    qw = _content_words(question)
    rel = [h for h in hits if _content_words(h.title + " " + h.snippet) & qw]
    return rel + [h for h in hits if h not in rel]


def gather(question: str, search_fn, open_fn, max_results: int = 10,
           max_rephrases: int = 2, today: date | str | None = None,
           max_seconds: float | None = 60) -> GatherResult:
    """Stops and returns not-found once max_seconds have passed (None = no limit)."""
    res = GatherResult(False, None, None, None)
    deadline = None if max_seconds is None else time.monotonic() + max_seconds
    timed_out = False

    def out_of_time() -> bool:
        nonlocal timed_out
        timed_out = timed_out or (deadline is not None and time.monotonic() >= deadline)
        return timed_out

    unreadable = 0
    query: str | None = question
    for round_ in range(max_rephrases + 1):
        if out_of_time():
            break
        res.queries.append(query)
        try:
            hits = _hits(search_fn(query))[:max_results]
        except Exception:
            hits = []
        for h in _order(question, hits):
            if h.url in res.opened:
                continue
            if out_of_time():
                break
            res.opened.append(h.url)
            try:
                page = _page(open_fn(h.url))
            except Exception:
                page = Page("", "")
            if not page.text.strip() or blocked_page(page.text):
                unreadable += 1  # empty, not OK (BLOCKED/LOGIN/ERR), or a bot-check page
                continue
            v = judge(question, page.text, url=h.url, today=today)
            res.verdicts.append(v)
            if v.enough and looks_blocked(f"{v.answer or ''}\n{v.evidence or ''}"):
                v.enough, v.reason = False, "blocked_page"
            if v.enough:
                res.found, res.answer, res.evidence, res.source = True, v.answer, v.evidence, h
                res.message = (f"Found on {h.url} after {len(res.queries)} search(es) "
                               f"and {len(res.opened)} page(s).")
                return res
        if round_ == max_rephrases or out_of_time():
            break
        query = rephrase(question, res.queries, today=today)
        if query is None:
            break
    tried = "; ".join(f'"{q}"' for q in res.queries)
    why = f"Ran out of time ({max_seconds:g}s). " if timed_out else ""
    res.message = why + (f"Not found after {len(res.queries)} search(es) and {len(res.opened)} "
                   f"page(s) ({unreadable} unreadable). Tried: {tried}.")
    return res
