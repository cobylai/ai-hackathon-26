"""The email tools the model sees: short, status-led plain text."""

from __future__ import annotations

from harness.email import search as search_mod


def email_search(sender: str = "", text: str = "", days: int = 0) -> str:
    """Search Gmail; rows are numbered so email_read can open one."""
    return search_mod.search(
        sender=sender or None,
        text=text or None,
        days=days or None,
    )
