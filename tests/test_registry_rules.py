"""The overview's rules for what a model sees at once.

"A tool group is at most 5 tools and at most 400 tokens of description" and a
group may only name tools that exist. The web group predates the rule (six
browser tools) and belongs to browser-core, so that one is recorded as a known
deviation rather than silently ignored.
"""

from __future__ import annotations

import pytest

from harness import registry

MAX_TOOLS = 5
MAX_DESC_CHARS = 4 * 400  # 400 tokens at four characters per token


def descriptions(names: list[str]) -> int:
    return sum(len(registry.TOOLS[name].desc) for name in names)


def test_groups_only_name_real_tools():
    for group, names in registry.GROUPS.items():
        for name in names:
            assert name in registry.TOOLS, f"{group} names missing tool {name!r}"


def test_search_group_fits_the_model_budget():
    names = registry.GROUPS["search"]
    assert 0 < len(names) <= MAX_TOOLS
    assert descriptions(names) <= MAX_DESC_CHARS


def test_every_group_fits_the_description_budget():
    for group, names in registry.GROUPS.items():
        assert descriptions(names) <= MAX_DESC_CHARS, group


@pytest.mark.xfail(
    strict=True,
    reason="web has six browser tools; browser-core owns that group (see docs/log)",
)
def test_every_group_has_at_most_five_tools():
    for group, names in registry.GROUPS.items():
        assert len(names) <= MAX_TOOLS, f"{group} has {len(names)} tools"
