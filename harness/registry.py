"""Tool registry shared with the reasoning layer.

``GROUPS`` maps a tool group to tool names; the decision tree picks a group and
the model only ever sees that group's tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from harness.browser import tools as browser_tools
from harness.email import tools as email_tools


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

GROUPS: dict[str, list[str]] = {
    "web": ["goto", "read", "elements", "click", "type", "back"],
    "email": [
        "email_search",
        "email_read",
        "email_asks",
        "email_draft",
        "email_reply_draft",
    ],
    "computer": [],
}
