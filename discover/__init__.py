"""Discovery mode: Muse proposes facts about the user from the bank and the calendar,
and keeps only what the user confirms. See playbooks/discover.md and docs/INTERFACES.md §6.

    from discover import handle, waiting
"""
from .session import handle, reset, waiting  # noqa: F401
