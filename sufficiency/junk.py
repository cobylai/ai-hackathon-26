"""Bot-check and error pages: never an answer, never filed in the bank.

    from sufficiency.junk import looks_blocked
    looks_blocked("Prove your humanity")  -> True

The browser classifies most walls as BLOCKED (harness/browser/state.py), but a
new wall can still come back as OK (Reddit's "Prove your humanity" did). This is
the second net on our side: a page is skipped when it is short and reads like a
wall, and an answer or quote is refused whenever it contains one of these.
"""
from __future__ import annotations

import re

# Phrases that only appear on bot checks and error pages. Short on purpose.
PHRASES = (
    # bot checks
    "prove your humanity", "verify you are human", "verify that you are human",
    "are you a robot", "unusual traffic", "captcha",
    "checking your browser", "checking if the site connection is secure",
    "bots use duckduckgo too", "confirm this search was made by a human",
    "select all squares containing", "attention required",
    "cloudflare ray id", "please enable javascript and cookies",
    "you have been blocked", "request blocked", "access denied",
    # error pages
    "403 forbidden", "404 not found", "page not found", "too many requests",
    "502 bad gateway", "503 service unavailable", "internal server error",
    "enable javascript to", "javascript is disabled", "you need to enable javascript",
)
# Pages longer than this are real articles that merely mention a phrase.
SHORT_PAGE = 3000


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("’", "'").lower())


def looks_blocked(text: str) -> bool:
    """True when text contains a bot-check or error-page phrase."""
    t = _norm(text)
    return any(p in t for p in PHRASES)


def blocked_page(text: str) -> bool:
    """A short page that reads like a wall. Long pages that mention a phrase are kept."""
    return len((text or "").strip()) <= SHORT_PAGE and looks_blocked(text)
