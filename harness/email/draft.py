"""Create Gmail drafts. There is deliberately no send function here.

``new`` starts a fresh compose; ``reply`` answers thread ``n`` from the last
search. Both save with Gmail's "Save & close" button and report whether Gmail
confirmed the save with its "Draft saved" label.
"""

from __future__ import annotations

from playwright.sync_api import Page

from harness.browser.session import get_session
from harness.email import read, search, selectors
from harness.email.status import LOGIN_LINE, signed_in

DRAFT_SAVED = "OK draft saved"


def _short(exc: Exception) -> str:
    return " ".join(str(exc).split())[:100]


def _wait_visible(page: Page, name: str, timeout_ms: int = 15000):
    """First visible match for ``name``, polling; Gmail pre-renders hidden copies."""
    waited = 0
    while waited < timeout_ms:
        found = selectors.first_visible(page, name)
        try:
            if found.count() and found.is_visible():
                return found
        except Exception:
            pass
        page.wait_for_timeout(400)
        waited += 400
    return selectors.first_visible(page, name)


def open_compose(page: Page) -> None:
    button = selectors.first_visible(page, "compose_button")
    if not button.count():
        raise RuntimeError("no Compose button")
    button.click()
    if not _wait_visible(page, "compose_to", timeout_ms=10000).count():
        raise RuntimeError("compose did not open")


def wait_saved(page: Page, timeout_ms: int = 20000) -> bool:
    label = _wait_visible(page, "draft_saved_label", timeout_ms=timeout_ms)
    try:
        return bool(label.count() and label.is_visible())
    except Exception:
        return False


def close_compose(page: Page) -> None:
    close = _wait_visible(page, "compose_close", timeout_ms=3000)
    if close.count():
        close.click()
        page.wait_for_timeout(500)


def new(to: str, subject: str, body: str) -> str:
    """Compose and save a new draft; returns ``OK draft saved`` or ``ERR ...``."""
    if not (to or "").strip():
        return "ERR mail.google.com | no recipient | give a to address"
    page = get_session().start().page
    if not signed_in(page):
        return LOGIN_LINE
    try:
        open_compose(page)
        _wait_visible(page, "compose_to", timeout_ms=10000).fill(to.strip())
        page.keyboard.press("Enter")  # turn the typed address into a chip
        _wait_visible(page, "compose_subject").fill(subject or "")
        _wait_visible(page, "compose_body").fill(body or "")
        if not wait_saved(page):
            close_compose(page)
            return "ERR mail.google.com | draft did not save | Gmail showed no 'Draft saved'"
        close_compose(page)
        return DRAFT_SAVED
    except Exception as exc:
        return f"ERR mail.google.com | draft failed | {_short(exc)}"


def reply(n: int, body: str) -> str:
    """Save a reply draft in thread ``n`` from the last search."""
    rows = search.last_rows()
    if not rows:
        return "ERR mail.google.com | no search results | call email_search first"
    try:
        index = int(n)
    except (TypeError, ValueError):
        index = 0
    if index < 1 or index > len(rows):
        return f"ERR mail.google.com | no row {n} | results are 1 to {len(rows)}"

    page = get_session().start().page
    if not signed_in(page):
        return LOGIN_LINE
    row = rows[index - 1]
    if not read.open_thread(page, row.thread_id):
        return "ERR mail.google.com | thread did not open | try email_search again"

    try:
        buttons = selectors.all_in(page, "reply_button")
        target = None
        for i in range(buttons.count()):
            try:
                if buttons.nth(i).is_visible():
                    target = buttons.nth(i)
            except Exception:
                continue
        if target is None:
            return "ERR mail.google.com | no Reply button | thread has no reply box"
        target.click()
        box = _wait_visible(page, "compose_body", timeout_ms=10000)
        if not box.count():
            return "ERR mail.google.com | reply box did not open"
        box.fill(body or "")
        if not wait_saved(page):
            close_compose(page)
            return "ERR mail.google.com | draft did not save | Gmail showed no 'Draft saved'"
        close_compose(page)
        return DRAFT_SAVED
    except Exception as exc:
        return f"ERR mail.google.com | reply draft failed | {_short(exc)}"
