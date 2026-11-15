"""Course codes, person-vs-automated senders, and which folder an entry goes in."""
from __future__ import annotations

import re

COURSE_RE = re.compile(r"\b([A-Z]{2,6}) ?(\d{4})\b")

_MONTHS = {"JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "SEPT", "OCT",
           "NOV", "DEC", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "JUNE", "JULY", "AUGUST",
           "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"}
_SEASONS = {"FALL", "SPRING", "SUMMER", "WINTER", "AUTUMN"}
_NEVER = {"ROOM", "PIN", "CODE", "ZOOM", "REF", "ID", "RM", "BOX", "UNIT", "APT", "SUITE",
          "EXT", "PHONE", "CLASS", "YEAR", "TERM"}
STOP = _MONTHS | _SEASONS | _NEVER

AUTOMATED_WORDS = {"noreply", "donotreply", "news", "newsletter", "notify", "notification",
                   "notifications", "notices", "info", "admin", "office", "bursar", "registrar",
                   "dining", "club", "clubs", "team", "support", "alert", "alerts", "library",
                   "mailer", "bounce", "postmaster", "help", "helpdesk", "updates"}


def automated_local(local: str) -> bool:
    """Whole-word match on the part before @, split on . - _ ('newsome' stays a person)."""
    words = [w for w in re.split(r"[._\-+]", local.lower()) if w]
    joined = {"".join(words[i:i + n]) for n in (2, 3) for i in range(len(words) - n + 1)}
    return bool(AUTOMATED_WORDS & (set(words) | joined))
AUTOMATED_NAME = re.compile(
    r"\b(office|club|dining|team|department|dept|services?|library|university|"
    r"registrar|bursar|newsletter|notifications?|support|admissions)\b", re.I)


def _ok(prefix: str, num: str) -> bool:
    if prefix in STOP:
        return False
    if prefix in _MONTHS | _SEASONS and 2020 <= int(num) <= 2030:
        return False
    return True


def find_course(*texts: str | None) -> str | None:
    """First course code found, searching each text in order. Normalised 'CS 3110'."""
    for t in texts:
        if not t:
            continue
        for m in COURSE_RE.finditer(t):
            if _ok(m.group(1), m.group(2)):
                return f"{m.group(1)} {m.group(2)}"
    return None


def is_person(name: str | None, address: str | None, model_says: bool | None) -> bool:
    if model_says is False:
        return False
    if not (name or address):
        return False
    local = (address or "").split("@")[0].lower()
    domain = (address or "").split("@")[-1].lower() if address else ""
    if local and automated_local(local):
        return False
    if domain.startswith(("clubs.", "lists.", "news.")):
        return False
    if name and AUTOMATED_NAME.search(name):
        return False
    return True


def folder_for(kind: str, course: str | None, person: bool) -> str:
    if course:
        return "course"
    if kind == "email" and person:
        return "person"
    return "other"
