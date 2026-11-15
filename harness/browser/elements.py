"""Numbered list of things the model can click or type into."""

from __future__ import annotations

import weakref
from pathlib import Path

from playwright.sync_api import Page

MAX_LINES = 40
_JS = Path(__file__).with_name("elements.js").read_text(encoding="utf-8")

# page -> (weak page ref, URL at listing time), so a number cannot be reused
# after the page navigated to somewhere else.
_listed: dict[int, tuple[weakref.ReferenceType[Page], str]] = {}


def scan(page: Page) -> list[dict]:
    """Tag visible controls with ``data-hn`` and return ``{n, kind, label}``."""
    items = page.evaluate(_JS)
    _listed[id(page)] = (weakref.ref(page), page.url)
    return items


def _require_fresh_listing(page: Page) -> None:
    """Refuse to act on numbers taken before a navigation."""
    entry = _listed.get(id(page))
    if entry is None or entry[0]() is not page:
        raise RuntimeError("no element list for this page; call elements first")
    if entry[1] != page.url:
        raise RuntimeError("page changed since the last element list; call elements again")


def list_elements(page: Page, filter: str | None = None) -> str:
    """Return numbered lines like ``3. button "Sign in"`` (at most 40)."""
    items = scan(page)
    if filter:
        needle = filter.strip().lower()
        items = [
            item
            for item in items
            if needle in item["label"].lower() or needle in item["kind"].lower()
        ]
    return "\n".join(
        f'{item["n"]}. {item["kind"]} "{item["label"]}"' for item in items[:MAX_LINES]
    )


def click(page: Page, n: int) -> None:
    """Click the element last numbered ``n`` by :func:`list_elements`."""
    _require_fresh_listing(page)
    page.click(f'[data-hn="{int(n)}"]')


def type_into(page: Page, n: int, text: str, enter: int = 0) -> None:
    """Type ``text`` into element ``n``; press Enter when ``enter`` is true."""
    _require_fresh_listing(page)
    locator = page.locator(f'[data-hn="{int(n)}"]')
    locator.fill(text)
    if enter:
        locator.press("Enter")
