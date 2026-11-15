"""Tool registry shared with the reasoning layer.

``GROUPS`` maps a tool group to tool names; the decision tree picks a group and
the model only ever sees that group's tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from harness.browser import tools as browser_tools
from harness.search import tools as search_tools
from harness.email import tools as email_tools
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
    "research": Tool(
        "research",
        "Answer a question from the web with sources.",
        {"question": str},
        search_tools.research,
    ),
    "email_search": Tool(
        "email_search",
        "Search Gmail; returns numbered rows.",
        {"sender": str, "text": str, "days": int},
        email_tools.email_search,
    ),
    "email_read": Tool(
        "email_read",
        "Read thread N from the last search, newest message first.",
        {"n": int, "page": int},
        email_tools.email_read,
    ),
    "email_asks": Tool(
        "email_asks",
        "Questions and dated lines from a sender's recent threads.",
        {"sender": str, "days": int},
        email_tools.email_asks,
    ),
    "email_draft": Tool(
        "email_draft",
        "Save a new draft; never sends.",
        {"to": str, "subject": str, "body": str},
        email_tools.email_draft,
    ),
    "email_reply_draft": Tool(
        "email_reply_draft",
        "Save a reply draft in thread N; never sends.",
        {"n": int, "body": str},
        email_tools.email_reply_draft,
    ),
}

COMPUTER_TOOLS: dict[str, Tool] = {
    "app_open": Tool(
        "app_open",
        "Open a Mac app by name.",
        {"name": str, "token": str},
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
        {"n": int, "token": str},
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
        {"n": int, "token": str},
        computer_ui.ui_click,
    ),
    "ui_type": Tool(
        "ui_type",
        "Type text into control N from the last ui list.",
        {"n": int, "text": str, "token": str},
        computer_ui.ui_type,
    ),
}

TOOLS.update(COMPUTER_TOOLS)

GROUPS: dict[str, list[str]] = {
    "web": ["goto", "read", "elements", "click", "type", "back"],
    # Kept apart from "web" so a model sees at most three tools at a time.
    "search": ["search", "open_result", "research"],
    "email": [
        "email_search",
        "email_read",
        "email_asks",
        "email_draft",
        "email_reply_draft",
    ],
    "computer": list(COMPUTER_TOOLS),
}
