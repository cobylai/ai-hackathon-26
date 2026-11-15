"""``email_search``: open a Gmail search and return numbered rows.

Gmail's own search URL does the work, so nothing is typed into the search box.
The row order is kept in module state so ``email_read(n)`` can open row ``n``.
"""

from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Page

from harness import config
from harness.browser.session import get_session
from harness.email import query, selectors
from harness.email.status import BROWSER_LINE, LOGIN_LINE, signed_in

MAX_ROWS = 10
SNIPPET_CHARS = 80
NO_RESULTS = "No messages matched your search"
HINT = "[more: call email_search with a narrower sender or text]"


@dataclass(frozen=True)
class Row:
    n: int
    sender: str
    subject: str
    date: str
    snippet: str
    thread_id: str


_last: list[Row] = []
_last_query: str = ""


def last_rows() -> list[Row]:
    """Rows from the most recent search, in the order the model saw them."""
    return list(_last)


def last_query() -> str:
    """The query behind the most recent search, so a caller can re-run it."""
    return _last_query


def row_problem(row: "Row", index: int) -> str:
    """Why this row cannot be opened as a thread ("" when it can).

    A draft row opens a compose rather than a conversation, and a row without a
    thread id would send the browser to an empty URL.
    """
    if row.sender.strip().lower() == "draft":
        return f"row {index} is a draft, not a thread"
    if not row.thread_id:
        return f"row {index} has no thread id"
    return ""


def _text(locator) -> str:
    try:
        if not locator.count():
            return ""
        return " ".join(locator.inner_text().split())
    except Exception:
        return ""


def _attr(locator, name: str) -> str:
    try:
        if not locator.count():
            return ""
        return locator.get_attribute(name) or ""
    except Exception:
        return ""


def _short_date(raw: str) -> str:
    """``Sat, Nov 14, 2026, 3:53 PM`` becomes ``Nov 14, 3:53 PM``."""
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) >= 4:
        return f"{parts[1]}, {parts[3]}"
    if len(parts) == 3:
        return f"{parts[0]}, {parts[2]}"
    return raw


def visible_rows(page: Page) -> list:
    rows = selectors.all_in(page, "list_row")
    found = []
    for i in range(rows.count()):
        try:
            item = rows.nth(i)
            if item.is_visible():
                found.append(item)
        except Exception:
            continue
    return found


def parse_row(item, n: int) -> Row:
    subject_loc = selectors.locator(item, "row_subject")
    date_loc = selectors.locator(item, "row_date")
    snippet = _text(selectors.locator(item, "row_snippet"))
    if snippet.startswith("- "):
        snippet = snippet[2:]
    return Row(
        n=n,
        sender=_text(selectors.locator(item, "row_sender")),
        subject=_text(subject_loc),
        date=_short_date(_attr(date_loc, "title") or _text(date_loc)),
        snippet=snippet[:SNIPPET_CHARS],
        thread_id=_attr(subject_loc, "data-legacy-thread-id"),
    )


def no_results(page: Page) -> bool:
    try:
        return page.locator(f"text={NO_RESULTS}").count() > 0
    except Exception:
        return False


def wait_results(page: Page, timeout_ms: int = 20000) -> int:
    """Wait for a settled list or Gmail's "no messages" note; return the count.

    A search URL is only a hash change, so the inbox rows are still on screen
    for a moment and Gmail then re-renders the result list. Requiring the same
    count twice, after the URL says ``search``, avoids reading the old list.
    """
    waited = 0
    last = -1
    stable = 0
    empty = 0
    while waited <= timeout_ms:
        rows = len(visible_rows(page))
        if rows:
            stable = stable + 1 if rows == last else 0
            empty = 0
            if stable >= 2:
                return rows
        else:
            stable = 0
            # Gmail flashes its "no messages" note while a query renders, so
            # only believe it once it has persisted for a few samples.
            empty = empty + 1 if no_results(page) else 0
            if empty >= 3:
                return 0
        last = rows
        page.wait_for_timeout(400)
        waited += 400
    return max(last, 0)


def format_rows(label: str, rows: list[Row], total: int) -> str:
    if not total:
        return f"OK 0 results | {label}"
    head = f"OK {total} results | {label}"
    body = [f"{r.n}. {r.sender} | {r.subject} | {r.date} | {r.snippet}" for r in rows]
    text = "\n".join([head, *body])
    if len(text) <= config.MAX_CHARS:
        return text
    room = config.MAX_CHARS - len(HINT) - 1
    kept = [head]
    used = len(head)
    for line in body:
        if used + 1 + len(line) > room:
            break
        kept.append(line)
        used += 1 + len(line)
    return "\n".join(kept) + "\n" + HINT


def search(sender: str | None = None, text: str | None = None, days: int | None = None) -> str:
    """Search Gmail and return up to ten numbered rows."""
    try:
        page = get_session().start().page
    except Exception:
        return BROWSER_LINE
    if not signed_in(page):
        return LOGIN_LINE

    global _last_query
    query_text = query.build(sender=sender, text=text, days=days)
    _last_query = query_text
    page.goto(query.search_url(query_text), wait_until="domcontentloaded", timeout=60000)
    wait_results(page)

    if no_results(page):
        _last[:] = []
        return format_rows(query_text or "inbox", [], 0)

    items = visible_rows(page)[:MAX_ROWS]
    if not items:
        return "ERR mail.google.com | results did not render | try again"

    rows = [parse_row(item, n) for n, item in enumerate(items, start=1)]
    _last[:] = rows
    return format_rows(query_text or "inbox", rows, len(visible_rows(page)))
