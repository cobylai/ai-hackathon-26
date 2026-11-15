"""The email tools the model sees: short, status-led plain text."""

from __future__ import annotations

from harness.email import asks as asks_mod
from harness.email import draft as draft_mod
from harness.email import read as read_mod
from harness.email import search as search_mod


def email_search(sender: str = "", text: str = "", days: int = 0) -> str:
    """Search Gmail; rows are numbered so email_read can open one."""
    return search_mod.search(
        sender=sender or None,
        text=text or None,
        days=days or None,
    )


def email_read(n: int, page: int = 1) -> str:
    """Read thread n from the last search; newest message first."""
    return read_mod.read(n, page)


def email_asks(sender: str = "", days: int = 0) -> str:
    """Questions and dated lines from the sender's top threads."""
    return asks_mod.email_asks(sender=sender or None, days=days or None)


def email_draft(to: str, subject: str, body: str) -> str:
    """Save a new draft; it is never sent."""
    return draft_mod.new(to, subject, body)


def email_reply_draft(n: int, body: str) -> str:
    """Save a reply draft in thread n; it is never sent."""
    return draft_mod.reply(n, body)
