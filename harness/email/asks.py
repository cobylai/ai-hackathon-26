"""``email_asks``: the questions and dated lines in a sender's recent mail.

``extract`` is pure text, so the rule is testable without a browser: a
sentence counts when it asks something or carries a date, a weekday, a clock
time, or a deadline word.
"""

from __future__ import annotations

import re

from harness import config
from harness.browser.session import get_session
from harness.email import query, read, search

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


def email_asks(sender: str | None = None, days: int | None = None) -> str:
    """Search, read the top three threads, and list their questions and dates."""
    page = get_session().start().page
    label = query.build(sender=sender, days=days) or "inbox"
    result = search.search(sender=sender, days=days)
    if not result.startswith("OK"):
        return result

    rows = search.last_rows()[:TOP_THREADS]
    lines: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not read.open_thread(page, row.thread_id):
            continue
        for _who, _date, body in read.read_messages(page):
            for sentence in extract(body):
                key = sentence.lower()
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"{row.n}. {sentence}")

    head = f"OK {len(lines)} asks | {label}"
    if not lines:
        return head
    text = "\n".join([head, *lines])
    if len(text) <= config.MAX_CHARS:
        return text
    room = config.MAX_CHARS - len(HINT) - 1
    kept = [head]
    used = len(head)
    for line in lines:
        if used + 1 + len(line) > room:
            break
        kept.append(line)
        used += 1 + len(line)
    return "\n".join(kept) + "\n" + HINT
