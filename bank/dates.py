"""Turn deadline phrases into dates, relative to the sent date. No model involved.

    resolve("by 5pm Friday", date(2026, 11, 9)) -> (date(2026, 11, 13), "17:00")

Unmatched phrases give (None, time-or-None). The caller keeps the phrase.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_WD = {d: i for i, d in enumerate(WEEKDAYS)}
_WD.update({d[:3]: i for i, d in enumerate(WEEKDAYS)})
_WD.update({"tues": 1, "weds": 2, "thur": 3, "thurs": 3})
WD_RE = r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues|tue|weds|wed|thurs|thur|thu|fri|sat|sun)"

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"])}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9
MON_RE = r"(january|february|march|april|may|june|july|august|september|october|november|december|sept|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)"

_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)(?![a-z])")
_TIME24 = re.compile(r"\b(1[3-9]|2[0-3]):([0-5]\d)\b")  # 24h only when unambiguous


def _year_for(month: int, day: int, sent: date) -> date | None:
    try:
        d = date(sent.year, month, day)
    except ValueError:
        return None
    if (sent - d).days > 60:
        try:
            d = date(sent.year + 1, month, day)
        except ValueError:
            return None
    return d


def resolve_time(phrase: str) -> str | None:
    p = phrase.lower()
    m = _TIME.search(p)
    if m:
        h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)[0]
        if not (1 <= h <= 12 and mi < 60):
            return None
        h = h % 12 + (12 if ap == "p" else 0)
        return f"{h:02d}:{mi:02d}"
    if re.search(r"\bnoon\b|\bmidday\b", p):
        return "12:00"
    if re.search(r"\bmidnight\b", p):
        return "23:59"
    m = _TIME24.search(p)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def _next_weekday(wd: int, after: date) -> date:
    """First day strictly after `after` with weekday wd."""
    delta = (wd - after.weekday()) % 7
    return after + timedelta(days=delta or 7)


def resolve_date(phrase: str, sent: date, prev: date | None = None) -> date | None:
    p = " " + re.sub(r"\s+", " ", phrase.lower()) + " "

    # ISO 2026-11-20
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", p)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    # Nov 20 / November 20th
    m = re.search(MON_RE + r"\.? (\d{1,2})(?:st|nd|rd|th)?\b", p)
    if m:
        return _year_for(MONTHS[m.group(1)], int(m.group(2)), sent)
    # 20 Nov / 20th of November
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)? (?:of )?" + MON_RE + r"\b", p)
    if m:
        return _year_for(MONTHS[m.group(2)], int(m.group(1)), sent)
    # 11/20 or 11/20/2026 (US order); not times like 3/4pm handled oddly, acceptable
    m = re.search(r"(?<![\d:])(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?![\d:])", p)
    if m:
        mo, dy = int(m.group(1)), int(m.group(2))
        if m.group(3):
            y = int(m.group(3))
            y = y + 2000 if y < 100 else y
            try:
                return date(y, mo, dy)
            except ValueError:
                return None
        return _year_for(mo, dy, sent)
    # in N days / weeks
    m = re.search(r"\bin (\d+|a|one|two|three) (day|days|week|weeks)\b", p)
    if m:
        n = {"a": 1, "one": 1, "two": 2, "three": 3}.get(m.group(1)) or int(m.group(1))
        return sent + timedelta(days=n * (7 if m.group(2).startswith("week") else 1))
    # the Friday after
    m = re.search(r"\bthe " + WD_RE + r" after\b", p)
    if m:
        return _next_weekday(_WD[m.group(1)], prev or sent)
    # next Friday: that weekday in the week (Mon-Sun) after S's week
    m = re.search(r"\bnext " + WD_RE + r"\b", p)
    if m:
        next_monday = sent - timedelta(days=sent.weekday()) + timedelta(days=7)
        return next_monday + timedelta(days=_WD[m.group(1)])
    # bare / this / by / before weekday
    m = re.search(r"\b" + WD_RE + r"\b", p)
    if m:
        return _next_weekday(_WD[m.group(1)], sent)
    if re.search(r"\b(day after tomorrow)\b", p):
        return sent + timedelta(days=2)
    if re.search(r"\btomorrow\b|\btmrw\b|\btmr\b", p):
        return sent + timedelta(days=1)
    if re.search(r"\bend of (the )?week\b|\bthis week\b|\beow\b", p):
        return sent + timedelta(days=(4 - sent.weekday()) % 7)
    if re.search(r"\bnext week\b", p):
        return sent - timedelta(days=sent.weekday()) + timedelta(days=7)
    # the 25th / on the 20th
    m = re.search(r"\b(?:the|on) (\d{1,2})(?:st|nd|rd|th)\b", p)
    if m:
        dy = int(m.group(1))
        y, mo = sent.year, sent.month
        if dy < sent.day:
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
        try:
            return date(y, mo, dy)
        except ValueError:
            return None
    if re.search(r"\b(today|tonight|this (morning|afternoon|evening)|end of (the )?day|eod)\b", p):
        return sent
    return None


def resolve(phrase: str, sent: date, prev: date | None = None) -> tuple[date | None, str | None]:
    return resolve_date(phrase, sent, prev), resolve_time(phrase)


_FIND = re.compile(
    r"\b(?:(?:by|before|on|until|due)\s+)?(?:"
    r"(?:next |this )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(?:morning|afternoon|evening|night))?"
    r"|tomorrow(?:\s+(?:morning|afternoon|evening|night))?|tonight|today|end of (?:the )?day"
    r"|" + MON_RE + r"\.? \d{1,2}(?:st|nd|rd|th)?"
    r"|the \d{1,2}(?:st|nd|rd|th)"
    r")(?:\s+(?:at\s+)?(?:\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?|noon|midnight))?\b",
    re.I)


def find_phrases(text: str) -> list[str]:
    """Deadline-like phrases inside free text, e.g. an ask sentence."""
    return [m.group(0).strip() for m in _FIND.finditer(text or "")]
