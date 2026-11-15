"""Proactive nudges: Flux speaks first. Code only, no model call, no network (docs/agent/proactive.md)."""
from .rules import Nudge, DEFAULT_CONFIG, nudges
from .state import load, save, record_shown, dismiss, snooze, poll, enabled

__all__ = ["Nudge", "DEFAULT_CONFIG", "nudges", "load", "save", "record_shown", "dismiss", "snooze",
           "poll", "enabled"]
