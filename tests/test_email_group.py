"""The email group stays small and cannot browse (prompt-injection guard)."""

from __future__ import annotations

from harness import registry

BROWSING = {"goto", "read", "elements", "click", "type", "back"}


def test_email_group_has_no_browsing_tools():
    """A message must not be able to steer the model to a link or a click."""
    assert not (set(registry.GROUPS["email"]) & BROWSING)


def test_email_group_is_at_most_five_tools():
    assert 0 < len(registry.GROUPS["email"]) <= 5


def test_every_email_tool_fits_the_overview_rules():
    for name in registry.GROUPS["email"]:
        tool = registry.TOOLS[name]
        assert tool.name == name
        assert tool.desc and "\n" not in tool.desc and len(tool.desc) <= 100
        assert len(tool.args) <= 3
        assert set(tool.args.values()) <= {str, int}
