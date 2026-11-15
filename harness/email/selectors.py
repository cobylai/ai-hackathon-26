"""Gmail's page structure in one place.

Each name maps to selectors, best first: ``role``, ``aria-label`` or another
semantic attribute before a Gmail class name, which changes more often.

``list_row``, ``thread_message``, ``reply_button`` and the ``compose_*`` names
are looked up from the page. ``row_*`` names are looked up inside one row and
``message_*`` (and ``quoted_text``) inside one message, because the same field
repeats per row.
"""

from __future__ import annotations

from typing import Protocol

SELECTORS: dict[str, tuple[str, ...]] = {
    # Inbox and search results.
    "list_row": ("table[role='grid'] tbody tr.zA", "tr.zA"),
    "row_sender": ("span[email]", "span.yP"),
    "row_subject": ("span[data-thread-id]", "span.bog"),
    "row_snippet": ("span.y2", "td.a4W span.y2"),
    "row_date": ("td.xW span[title]", ".xW span[title]"),
    # One opened thread; these are looked up inside each message container.
    "thread_message": ("div.adn.ads", "div[role='listitem']"),
    "message_sender": ("span.gD[email]", "span.gD"),
    "message_date": ("span.g3[title]", "span.g3"),
    "message_body": ("div.a3s", "div[role='listitem'] div.a3s"),
    "quoted_text": ("div.gmail_quote", "blockquote.gmail_quote"),
    # Compose and reply, from the page.
    "compose_button": (
        "div[role='button'][class~='T-I-KE']",
        "div[role='button']:has-text('Compose')",
    ),
    "compose_to": ("input[aria-label='To recipients']", "input[name='to']"),
    "compose_subject": ("input[name='subjectbox']", "input[aria-label='Subject']"),
    "compose_body": (
        "div[role='textbox'][aria-label='Message Body']",
        "textarea[aria-label='Message Body']",
    ),
    "compose_close": ("button[aria-label='Save & close']", "img[aria-label='Save & close']"),
    "draft_saved_label": ("h2:has-text('Draft saved')", "span:has-text('Draft saved')"),
    # One per message, but outside the message container in Gmail's page.
    "reply_button": ("div.nr.wR span[role='link'].bkH", "span.ams.bkH"),
}


class _Scope(Protocol):
    def locator(self, selector: str): ...


def _first_match(scope: _Scope, name: str):
    """Locator for the first selector of ``name`` that matches anything."""
    for selector in SELECTORS[name]:
        try:
            found = scope.locator(selector).first
            if found.count():
                return found
        except Exception:
            continue
    return scope.locator(SELECTORS[name][-1]).first


def locator(scope: _Scope, name: str):
    """One item called ``name`` (may match nothing)."""
    return _first_match(scope, name)


def all_in(scope: _Scope, name: str):
    """All items matching the first selector of ``name`` that matches anything."""
    for selector in SELECTORS[name]:
        try:
            items = scope.locator(selector)
            if items.count():
                return items
        except Exception:
            continue
    return scope.locator(SELECTORS[name][-1])


def matches(scope: _Scope, name: str) -> int:
    """How many items the winning selector for ``name`` found."""
    return all_in(scope, name).count()


def first_visible(scope: _Scope, name: str):
    """First match for ``name`` that is actually on screen.

    Gmail keeps hidden duplicates of rows (and of some cells) in the page, so
    the first match in the DOM is not always the one a user could click.
    """
    items = all_in(scope, name)
    for i in range(items.count()):
        try:
            item = items.nth(i)
            if item.is_visible():
                return item
        except Exception:
            continue
    return items.first


def wait_for(page, name: str, timeout_ms: int = 10000):
    """Poll until ``name`` appears, then return its locator.

    Needed for labels such as ``draft_saved_label`` that only exist after a
    save: choosing a selector once, before the element exists, picks a
    fallback that may never match.
    """
    waited = 0
    while True:
        found = locator(page, name)
        if found.count() or waited >= timeout_ms:
            return found
        page.wait_for_timeout(500)
        waited += 500
