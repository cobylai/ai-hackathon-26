"""Tool registry shared with the reasoning layer.

``GROUPS`` maps a tool group to tool names; the decision tree picks a group and
the model only ever sees that group's tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from harness.browser import tools as browser_tools
from harness.search import tools as search_tools


@dataclass(frozen=True)
class Tool:
    name: str
    desc: str
    args: dict[str, type]
    run: Callable[..., str]


TOOLS: dict[str, Tool] = {
    "goto": Tool(
        "goto",
        "Open a URL and return its title and first page of text.",
        {"url": str},
        browser_tools.goto,
    ),
    "read": Tool(
        "read",
        "Read page N of the current page's text.",
        {"page": int},
        browser_tools.read,
    ),
    "elements": Tool(
        "elements",
        "List clickable and typeable items as numbers.",
        {"filter": str},
        browser_tools.elements,
    ),
    "click": Tool(
        "click",
        "Click item N from the last elements list.",
        {"n": int},
        browser_tools.click,
    ),
    "type": Tool(
        "type",
        "Type text into item N; enter=1 presses Enter.",
        {"n": int, "text": str, "enter": int},
        browser_tools.type,
    ),
    "back": Tool(
        "back",
        "Go back to the previous page.",
        {},
        browser_tools.back,
    ),
    "search": Tool(
        "search",
        "Search the web and list results as numbers.",
        {"query": str},
        search_tools.search,
    ),
    "open_result": Tool(
        "open_result",
        "Open numbered result N from the last search.",
        {"n": int},
        search_tools.open_result,
    ),
}

GROUPS: dict[str, list[str]] = {
    "web": ["goto", "read", "elements", "click", "type", "back"],
    # Kept apart from "web" so a model sees at most three tools at a time.
    "search": ["search", "open_result"],
    "email": [],
    "computer": [],
}
