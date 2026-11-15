"""The two search tools the model sees: `search` and `open_result`.

Both return plain text that starts with a status word and stays under the
1500-character cap. Search results are numbered and kept for the session so
the model can answer with a number instead of a URL.
"""

from __future__ import annotations

from harness import config
from harness.browser import state
from harness.browser import tools as browser_tools
from harness.browser.session import get_session
from harness.browser.text import page_text, paginate
from harness.search import cache, engine, loop
from harness.search.google import Result

MAX_RESULTS = 10
TITLE_CHARS = 90
# Leave room for the status line and hint inside the hard answer cap.
TEXT_CHARS = max(200, config.MAX_CHARS - 160)

_last: list[Result] = []


def reset() -> None:
    """Forget the stored results (tests and new sessions)."""
    _last.clear()


def _cap(text: str, hint: str = "[more: open_result(1)]") -> str:
    text = text.strip()
    if len(text) <= config.MAX_CHARS:
        return text
    room = config.MAX_CHARS - len(hint) - 1
    body = text[:room].rstrip()
    if "\n" in body:
        body = body.rsplit("\n", 1)[0]
    return f"{body}\n{hint}"


def _line(n: int, item: Result) -> str:
    title = item.title if len(item.title) <= TITLE_CHARS else item.title[: TITLE_CHARS - 3] + "..."
    parts = [f"{n}. {title}", f"({item.domain})"]
    if item.snippet:
        parts.append(item.snippet)
    return " ".join(parts)


@browser_tools.browser_tool
def search(query: str) -> str:
    """Search the web; list up to ten results as numbered lines."""
    global _last
    results = engine.search(query)[:MAX_RESULTS]
    _last = results
    if not results:
        word = engine.last_status
        if word not in ("BLOCKED", "LOGIN", "ERR"):
            word = "OK"
        advice = {
            "BLOCKED": "the engine is showing a bot check; do not retry now",
            "LOGIN": "the engine wants a sign-in",
            "ERR": "the search failed",
        }.get(word, "try fewer words")
        shown = " ".join((query or "").split())[:60]
        return _cap(f'{word} search | no results for "{shown}" | {advice}', "[end]")

    head = f"OK search | {len(results)} results"
    lines: list[str] = []
    used = len(head) + 1
    budget = config.MAX_CHARS - 40  # room for the trailing hint
    for n, item in enumerate(results, 1):
        line = _line(n, item)
        if used + len(line) + 1 > budget:
            break
        lines.append(line)
        used += len(line) + 1
    _last = results[: len(lines)]
    text = f"{head}\n" + "\n".join(lines)
    if len(results) > len(lines):
        text += "\n[more: search a narrower query]"
    return _cap(text, "[end]")


def open_page(url: str) -> tuple[str, str]:
    """Open a URL in the shared browser; return (status word, full page text).

    A page read in the last 24 hours comes back from the SQLite cache instead.
    If the browser died mid-session, it is restarted once and the read retried.
    """
    cached = cache.get(url)
    if cached is not None:
        return "OK", cached
    try:
        return _load(url)
    except browser_tools.TargetClosedError:
        get_session().restart()
        try:
            return _load(url)
        except browser_tools.BrowserStartError:
            raise
        except Exception:
            return "ERR", ""
    except browser_tools.BrowserStartError:
        raise  # a locked or missing browser is the caller's to report, not a bad page
    except Exception:
        return "ERR", ""


def _load(url: str) -> tuple[str, str]:
    page = browser_tools._page()
    response = page.goto(url, wait_until="domcontentloaded", timeout=20_000)
    status = response.status if response is not None else None
    word = state.classify(page, status=status)
    if word != "OK":
        return word, ""
    text = page_text(page.content())
    cache.put(url, text)
    return "OK", text


@browser_tools.browser_tool
def open_result(n: int, page: int = 1) -> str:
    """Open result N from the last search; page=2 reads the next part of it."""
    n = int(n)
    page = max(1, int(page))
    if not 1 <= n <= len(_last):
        return _cap(f"ERR search | no result {n} | call search first", "[end]")

    item = _last[n - 1]
    word, text = open_page(item.url)
    if word != "OK":
        message = {
            "BLOCKED": "bot check, try another result",
            "LOGIN": "sign-in needed, try another result",
            "ERR": "page not usable, try another result",
        }[word]
        return _cap(f"{word} {item.domain} | result {n} | {message}", "[end]")

    chunk, total = paginate(text, page, max_chars=TEXT_CHARS)
    head = f"OK {item.domain} | result {n} | page {page}/{total}"
    if not chunk:
        return _cap(f"{head}\n(no text on that page)", "[end]")
    # Paging stays inside the search group: `read` belongs to the browser group.
    body = f"{head}\n{chunk}"
    if page < total:
        body += f"\n[more: call open_result({n}, page={page + 1})]"
    return _cap(body, "[end of text]")


@browser_tools.browser_tool
def research(question: str) -> str:
    """Answer a question from the web: search, read, take notes, retry."""
    outcome = loop.research(question)
    word = "OK"
    if not outcome.notes and engine.last_status in ("BLOCKED", "LOGIN", "ERR"):
        word = engine.last_status
    head = f"{word} research | {outcome.rounds} rounds | {outcome.pages} pages"
    return _cap(f"{head}\n{outcome.answer}", "[end]")
