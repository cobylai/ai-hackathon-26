"""Network-layer ad blocking with Brave's adblock engine.

Every request is checked against EasyList/EasyPrivacy (when downloaded) and
non-text resources (images, media, fonts) are dropped outright.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import adblock
from playwright.sync_api import Page, Route

from harness import config

FILTER_FILES = ("easylist.txt", "easyprivacy.txt")

# Resource types the reader never needs.
BLOCKED_TYPES = frozenset({"image", "media", "font"})

# Playwright resource type -> adblock-rust request type.
REQUEST_TYPES = {
    "document": "document",
    "stylesheet": "stylesheet",
    "image": "image",
    "media": "media",
    "font": "font",
    "script": "script",
    "texttrack": "media",
    "xhr": "xmlhttprequest",
    "fetch": "xmlhttprequest",
    "eventsource": "xmlhttprequest",
    "websocket": "websocket",
    "manifest": "other",
    "other": "other",
}


@dataclass
class BlockStats:
    """What the route handler dropped for one page."""

    blocked: int = 0
    allowed: int = 0
    urls: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def load_engine(
    directory: str | Path | None = None,
    extra_lists: Iterable[str] = (),
) -> adblock.Engine:
    """Build an engine from the downloaded filter files plus any extra lists.

    Missing filter files are fine: the engine is then empty (or test-only).
    """
    filters = adblock.FilterSet()
    folder = Path(directory) if directory is not None else config.FILTER_DIR
    for name in FILTER_FILES:
        path = folder / name
        if path.is_file():
            filters.add_filter_list(path.read_text(encoding="utf-8", errors="ignore"))
    for text in extra_lists:
        filters.add_filter_list(text)
    return adblock.Engine(filters)


def _engine_match(engine: adblock.Engine, url: str, source_url: str, resource_type: str) -> bool:
    try:
        result = engine.check_network_urls(
            url, source_url, REQUEST_TYPES.get(resource_type, "other")
        )
    except Exception:  # malformed URL or engine hiccup: let it through
        return False
    return bool(result.matched)


def install(page: Page, engine: adblock.Engine | None = None) -> BlockStats:
    """Route every request on ``page`` through the block list.

    Returns the stats object, which keeps counting after ``install`` returns.
    """
    engine = load_engine() if engine is None else engine
    stats = BlockStats()

    def handler(route: Route) -> None:
        request = route.request
        resource_type = request.resource_type
        if resource_type in BLOCKED_TYPES:
            reason = resource_type
        elif _engine_match(engine, request.url, request.frame.url, resource_type):
            reason = "filter"
        else:
            stats.allowed += 1
            route.continue_()
            return
        stats.blocked += 1
        stats.urls.append(request.url)
        stats.reasons.append(reason)
        route.abort()

    page.route("**/*", handler)
    return stats
