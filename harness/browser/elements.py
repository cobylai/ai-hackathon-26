"""Numbered list of things the model can click or type into."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

MAX_LINES = 40
_JS = Path(__file__).with_name("elements.js").read_text(encoding="utf-8")


def scan(page: Page) -> list[dict]:
    """Tag visible controls with ``data-hn`` and return ``{n, kind, label}``."""
    return page.evaluate(_JS)


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
    page.click(f'[data-hn="{int(n)}"]')


def type_into(page: Page, n: int, text: str, enter: int = 0) -> None:
    """Type ``text`` into element ``n``; press Enter when ``enter`` is true."""
    locator = page.locator(f'[data-hn="{int(n)}"]')
    locator.fill(text)
    if enter:
        locator.press("Enter")
