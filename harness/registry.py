"""Tool registry shared with the reasoning layer.

``GROUPS`` maps a tool group to tool names; the decision tree picks a group and
the model only ever sees that group's tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from harness.browser import tools as browser_tools
from harness.computer import tools as computer_tools
from harness.computer import ui as computer_ui


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
}

COMPUTER_TOOLS: dict[str, Tool] = {
    "app_open": Tool(
        "app_open",
        "Open a Mac app by name.",
        {"name": str},
        computer_tools.app_open,
    ),
    "file_find": Tool(
        "file_find",
        "Find files by name in the home folder; returns numbered paths.",
        {"query": str},
        computer_tools.file_find,
    ),
    "file_open": Tool(
        "file_open",
        "Open file N from the last file_find list.",
        {"n": int},
        computer_tools.file_open,
    ),
    "ui": Tool(
        "ui",
        "List the front window's controls as numbers; optional filter word.",
        {"filter": str},
        computer_ui.list_controls,
    ),
    "ui_click": Tool(
        "ui_click",
        "Click control N from the last ui list.",
        {"n": int},
        computer_ui.ui_click,
    ),
    "ui_type": Tool(
        "ui_type",
        "Type text into control N from the last ui list.",
        {"n": int, "text": str},
        computer_ui.ui_type,
    ),
}

TOOLS.update(COMPUTER_TOOLS)

GROUPS: dict[str, list[str]] = {
    "web": ["goto", "read", "elements", "click", "type", "back"],
    "email": [],
    "computer": list(COMPUTER_TOOLS),
}
