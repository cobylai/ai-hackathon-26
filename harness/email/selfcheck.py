"""Report which Gmail selectors match nothing on the live mailbox.

Run ``uv run python -m harness.email.selfcheck`` after ``harness login``. It
opens the inbox and the first thread, prints a count per selector name, and
exits 1 if a selector changed shape. Nothing is typed and no draft is created.

``--compose`` also opens a blank compose window to check the compose selectors.
Gmail then saves your signature as a draft, so that step is opt-in.
"""

from __future__ import annotations

import argparse
import sys

from playwright.sync_api import Page

from harness.browser import state
from harness.browser.session import get_session
from harness.email import selectors
from harness.email.status import BROWSER_LINE

INBOX_URL = "https://mail.google.com/mail/u/0/#inbox"

ROW_FIELDS = ("row_sender", "row_subject", "row_snippet", "row_date")
MESSAGE_FIELDS = ("message_sender", "message_date", "message_body", "quoted_text")
COMPOSE_FIELDS = ("compose_to", "compose_subject", "compose_body", "compose_close")


def _wait_rows(page: Page, timeout_ms: int = 20000) -> int:
    """Gmail renders the list after its JS loads; give it a moment."""
    waited = 0
    while True:
        rows = selectors.matches(page, "list_row")
        if rows or waited >= timeout_ms:
            return rows
        page.wait_for_timeout(500)
        waited += 500


def _count_in(items, name: str) -> int:
    """How many of ``items`` contain at least one match for ``name``."""
    return sum(1 for i in range(items.count()) if selectors.matches(items.nth(i), name))


def _close_compose(page: Page) -> None:
    close = selectors.first_visible(page, "compose_close")
    if close.count():
        close.click()
    page.wait_for_timeout(600)
    discard = page.locator("div[role='button']").filter(has_text="Discard")
    if discard.count():
        discard.last.click()
        page.wait_for_timeout(400)


def collect(page: Page, compose: bool = False) -> tuple[list[tuple[str, str]], str]:
    """Return ``[(name, count text)]`` and a status line."""
    found: list[tuple[str, str]] = []
    page.goto(INBOX_URL, wait_until="domcontentloaded", timeout=60000)
    word = state.classify(page)
    if word != "OK":
        return found, f"{word} not signed in | run: harness login https://mail.google.com"
    rows = _wait_rows(page)
    if not rows:
        return found, "ERR inbox list did not render"

    items = selectors.all_in(page, "list_row")
    found.append(("list_row", str(rows)))
    for name in ROW_FIELDS:
        found.append((name, f"{_count_in(items, name)} of {rows} rows"))
    found.append(("compose_button", str(selectors.matches(page, "compose_button"))))

    subject = selectors.first_visible(page, "row_subject")
    if subject.count():
        subject.click()
        try:
            page.wait_for_selector("div.adn.ads", timeout=20000)
        except Exception:
            pass
        messages = selectors.all_in(page, "thread_message")
        count = messages.count()
        found.append(("thread_message", str(count)))
        for name in MESSAGE_FIELDS:
            found.append((name, f"{_count_in(messages, name)} of {count} messages"))
        replies = sum(
            1
            for i in range(selectors.matches(page, "reply_button"))
            if selectors.all_in(page, "reply_button").nth(i).is_visible()
        )
        found.append(("reply_button", f"{replies} of {count} messages"))

    compose_button = selectors.first_visible(page, "compose_button")
    if compose and compose_button.count():
        compose_button.click()
        selectors.wait_for(page, "compose_to", timeout_ms=10000)
        for name in COMPOSE_FIELDS:
            found.append((name, str(selectors.matches(page, name))))
        found.append(("draft_saved_label", "n/a (appears after a typed draft)"))
        _close_compose(page)
    else:
        for name in (*COMPOSE_FIELDS, "draft_saved_label"):
            found.append((name, "skipped (--compose)"))

    status = f"OK signed in | {page.title()[:60]} | {rows} rows"
    return found, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness.email.selfcheck", description=__doc__)
    parser.add_argument(
        "--compose",
        action="store_true",
        help="also open a blank compose (Gmail may save your signature as a draft)",
    )
    args = parser.parse_args(argv)
    try:
        page = get_session().start().page
    except Exception:
        print(BROWSER_LINE)
        return 2
    found, status = collect(page, compose=args.compose)
    print(status)
    missing = False
    if found:
        width = max(len(name) for name, _ in found)
        for name, shown in found:
            missing = missing or shown in ("0", "MISSING")
            print(f"{name.ljust(width)}  {shown}")
    return 1 if missing or not status.startswith("OK") else 0


if __name__ == "__main__":
    sys.exit(main())
