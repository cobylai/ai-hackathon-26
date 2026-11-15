"""Is the hidden browser still signed in to Gmail?

Every email tool calls ``signed_in`` first and returns ``LOGIN_LINE`` when it is
false, so the model never sees a sign-in page as if it were mail.
"""

from __future__ import annotations

from playwright.sync_api import Page

from harness.browser import state
from harness.browser.session import get_session
from harness.email import selectors

INBOX_URL = "https://mail.google.com/mail/u/0/#inbox"
LOGIN_LINE = "LOGIN mail.google.com | sign-in needed | run: harness login https://mail.google.com"
BROWSER_LINE = (
    "ERR mail.google.com | browser did not start | close the other Chromium window and retry"
)


def looks_signed_in(page: Page) -> bool:
    """True if this page is a usable Gmail screen (not the sign-in page)."""
    if state.classify(page) != "OK":
        return False
    return bool(selectors.matches(page, "list_row") or selectors.matches(page, "compose_button"))


def signed_in(page: Page | None = None, timeout_ms: int = 10000) -> bool:
    """Load the inbox headless and check for the mail list."""
    page = page or get_session().start().page
    try:
        page.goto(INBOX_URL, wait_until="domcontentloaded", timeout=60000)
    except Exception:
        return False
    waited = 0
    while True:
        if looks_signed_in(page):
            return True
        if waited >= timeout_ms:
            return False
        page.wait_for_timeout(500)
        waited += 500
