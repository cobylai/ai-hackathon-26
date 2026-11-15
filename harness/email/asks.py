"""``email_asks``: the questions and dated lines in a sender's recent mail.

``extract`` is pure text, so the rule is testable without a browser: a
sentence counts when it asks something or carries a date, a weekday, a clock
time, or a deadline word.
"""

from __future__ import annotations

import re

from harness import config
from harness.browser.session import get_session
from harness.email import query, read, search, selectors

TOP_THREADS = 3
LINE_CHARS = 220
HINT = "[more: narrow the sender or days]"

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
TRIGGERS = ("due", "deadline", "can you", "could you", "please", "by")

WEEKDAY_RE = re.compile(r"\b(?:" + "|".join(WEEKDAYS) + r")\b", re.I)
MONTH_DAY_RE = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?"
    r"|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\.?\s+\d{1,2}\b",
    re.I,
)
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s?(?:am|pm)?\b|\b\d{1,2}\s?(?:am|pm)\b", re.I)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def is_ask(sentence: str) -> bool:
    low = sentence.lower()
    if "?" in sentence:
        return True
    if WEEKDAY_RE.search(sentence) or MONTH_DAY_RE.search(sentence) or TIME_RE.search(sentence):
        return True
    return any(re.search(rf"\b{re.escape(word)}\b", low) for word in TRIGGERS)


def extract(text: str) -> list[str]:
    """Sentences worth showing the model, in order, deduplicated."""
    found: list[str] = []
    seen: set[str] = set()
    for raw in SENTENCE_SPLIT.split(text or ""):
        sentence = " ".join(raw.split()).lstrip("-*\u2022 ").strip()
        if len(sentence) < 3 or not is_ask(sentence):
            continue
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(sentence[:LINE_CHARS])
    return found


def _row_locator(page, row):
    """The result row for ``row`` on the current page, matched by thread id."""
    items = search.visible_rows(page)
    for i in range(len(items)):
        try:
            if selectors.locator(items[i], "row_subject").get_attribute("data-legacy-thread-id") == row.thread_id:
                return items[i]
        except Exception:
            continue
    return None


def _is_draft(row) -> bool:
    """Draft rows open a compose, not a thread; they are not asks either."""
    return row.sender.strip().lower() == "draft"


def _title_matches(page, subject: str) -> bool:
    """Gmail's tab title starts with the thread subject; guards the click path."""
    try:
        title = " ".join(page.title().split(" - ")[0].split()).lower()
    except Exception:
        return False
    wanted = " ".join(subject.split()).lower()
    return bool(title and wanted) and title[:15] == wanted[:15]


def _open_row(page, row) -> bool:
    """Open a thread by clicking its row: an in-app render, no page reload."""
    if _is_draft(row):
        return False
    item = _row_locator(page, row)
    if item is not None:
        try:
            item.click(timeout=4000)
            if read.wait_for_thread(page, timeout_ms=5000) and _title_matches(page, row.subject):
                return True
        except Exception:
            pass
    return read.open_thread(page, row.thread_id)


def _back_to_results(page) -> None:
    """Return to the result list, re-running the search if history lost it."""
    try:
        page.go_back(wait_until="domcontentloaded", timeout=15000)
    except Exception:
        pass
    if search.visible_rows(page):
        return
    query_text = search.last_query()
    if not query_text:
        return
    try:
        page.goto(query.search_url(query_text), wait_until="domcontentloaded", timeout=60000)
    except Exception:
        return
    search.wait_results(page, timeout_ms=8000)


def scan(
    sender: str | None = None,
    days: int | None = None,
    threads: int = TOP_THREADS,
) -> tuple[str, list[tuple[search.Row, list[str]]]]:
    """Search, then return ``(status, [(row, sentences)])`` for the top threads.

    Shared by ``email_asks`` and the digest: one place that opens threads the
    fast way and extracts the lines worth showing.
    """
    page = get_session().start().page
    result = search.search(sender=sender, days=days)
    if not result.startswith("OK"):
        return result, []

    rows = [row for row in search.last_rows() if not _is_draft(row)][:threads]
    entries: list[tuple[search.Row, list[str]]] = []
    for position, row in enumerate(rows):
        if not _open_row(page, row):
            continue
        sentences = [
            sentence
            for _who, _date, body in read.read_messages(page)
            for sentence in extract(body)
        ]
        entries.append((row, sentences))
        if position < len(rows) - 1:
            _back_to_results(page)
    return result, entries


def cap_lines(head: str, lines: list[str], hint: str = HINT) -> str:
    """Join ``head`` and ``lines`` under the 1500-character cap."""
    if not lines:
        return head
    text = "\n".join([head, *lines])
    if len(text) <= config.MAX_CHARS:
        return text
    room = config.MAX_CHARS - len(hint) - 1
    kept = [head]
    used = len(head)
    for line in lines:
        if used + 1 + len(line) > room:
            break
        kept.append(line)
        used += 1 + len(line)
    return "\n".join(kept) + "\n" + hint


def email_asks(sender: str | None = None, days: int | None = None) -> str:
    """Search, read the top three threads, and list their questions and dates."""
    label = query.build(sender=sender, days=days) or "inbox"
    result, entries = scan(sender=sender, days=days)
    if not result.startswith("OK"):
        return result

    lines: list[str] = []
    seen: set[str] = set()
    for row, sentences in entries:
        for sentence in sentences:
            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"{row.n}. {sentence}")
    return cap_lines(f"OK {len(lines)} asks | {label}", lines)
