"""Routing in code: which route a question takes, and the date range for due questions.

Pure functions, no model, no network, no bank reads (the sender list is passed in).
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from bank.dates import resolve_date

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_WD = {d: i for i, d in enumerate(WEEKDAYS)}
_WD_RE = r"(" + "|".join(WEEKDAYS) + r")"

_DUE = re.compile(r"\b(due|deadlines?)\b", re.I)

# Title words and automated-sender words never count as a person's name.
TITLES = set("prof professor dr mr mrs ms mx sir dean".split())
AUTOMATED = set("""office club clubs library department dept team university univ services service
center centre school college admin admissions registrar bursar dining news newsletter noreply
no-reply reply support info notifications notification alerts student students staff faculty
course courses class group hall housing career careers health system mail""".split())
# Common English words that are also first names; skipped unless the question uses capitals.
COMMON = set("""will may mark grant bill rose june art august frank ray sue pat joy hope faith
dawn rob jack bob summer april earl sky gene van iris lily chase drew lane miles bob jean
the and you your what who when where how did does was are for from with about ask asked
said say says tell told send sent email emails mail message messages today tomorrow week
lab class""".split())

_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def is_due(question: str) -> bool:
    return bool(_DUE.search(question or ""))


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def due_range(question: str, today: date) -> tuple[date, date, str]:
    """(start, end, label) for a due question. label is how the answer names the range."""
    q = " " + re.sub(r"\s+", " ", (question or "").lower()) + " "
    if re.search(r"\bnext week\b", q):
        s = _monday(today) + timedelta(days=7)
        return s, s + timedelta(days=6), "next week"
    if re.search(r"\bthis week\b|\bthe week\b|\bend of (the )?week\b", q):
        # On Sat/Sun "this week" means today through the coming Sunday (thinker ruling).
        extra = 7 if today.weekday() >= 5 else 0
        return today, _monday(today) + timedelta(days=6 + extra), "this week"
    if re.search(r"\b(this )?weekend\b", q):
        sat = _monday(today) + timedelta(days=5)
        s = max(sat, today)
        return s, sat + timedelta(days=1), "this weekend"
    if re.search(r"\bday after tomorrow\b", q):
        d = today + timedelta(days=2)
        return d, d, _day(d)
    if re.search(r"\b(tomorrow|tmrw|tmr)\b", q):
        d = today + timedelta(days=1)
        return d, d, _day(d)
    if re.search(r"\b(today|tonight)\b", q):
        return today, today, _day(today)
    m = re.search(r"\bnext " + _WD_RE + r"\b", q)
    if m:
        d = _monday(today) + timedelta(days=7 + _WD[m.group(1)])
        return d, d, _day(d)
    m = re.search(r"\b" + _WD_RE + r"\b", q)
    if m:
        d = today + timedelta(days=(_WD[m.group(1)] - today.weekday()) % 7)
        return d, d, _day(d)
    if re.search(r"\d|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.? \d", q):
        d = resolve_date(q, today)
        if d:
            return d, d, _day(d)
    return today, today + timedelta(days=6), "in the next 7 days"


def _day(d: date) -> str:
    return f"{d:%a} {d:%b} {d.day}"


def name_words(sender_name: str | None, sender_address: str | None) -> set[str]:
    """Lowercase name words for one sender: 3+ letters, no titles, nothing automated."""
    words = _WORD.findall(sender_name or "")
    local = (sender_address or "").split("@")[0]
    words += re.split(r"[._\-+0-9]+", local)
    if any(w.lower() in AUTOMATED for w in words):
        return set()
    return {w.lower() for w in words if len(w) >= 3 and w.lower() not in TITLES}


def person_in(question: str, names: set[str]) -> str | None:
    """The first question word that is a sender's name word, or None.

    If the question has a capitalized word other than its first, only capitalized
    words are tried and the COMMON stoplist does not apply ("what did Will say"); the
    first word is capitalized by habit, so it still goes through COMMON.
    Otherwise every word is tried except COMMON ("will it rain" does not match Will,
    "what did emily ask" matches Emily).
    """
    toks = [re.sub(r"'s$|'$", "", t) for t in _WORD.findall(question or "")]
    caps_mode = any(t[:1].isupper() for t in toks[1:])
    for i, t in enumerate(toks):
        w = t.lower()
        if len(w) < 3 or w not in names:
            continue
        if caps_mode and i > 0:
            if t[:1].isupper():
                return w
        elif w not in COMMON:  # lowercase mode, or the sentence-case first word
            return w
    return None
