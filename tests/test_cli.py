"""CLI: the search tools are usable by hand, one command per call.

`python -m harness research "when did the Berlin Wall fall?"` should work
without the decision tree, which is how a person (or the partner-testing
harness) can exercise the loop directly.
"""

from __future__ import annotations

from harness import __main__
from harness.registry import TOOLS, Tool


def fake_tool(monkeypatch, name: str, args: dict[str, type], output: str) -> None:
    monkeypatch.setitem(
        TOOLS,
        name,
        Tool(name, f"Fake {name}.", args, lambda **kwargs: output),
    )


def test_search_command_prints_numbered_results(monkeypatch, capsys):
    fake_tool(monkeypatch, "search", {"query": str}, "OK search | 1 results\n1. Otters (example.org)")
    assert __main__.main(["search", "otters"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("OK search")
    assert "Otters" in out


def test_research_command_exits_nonzero_when_blocked(monkeypatch, capsys):
    fake_tool(
        monkeypatch,
        "research",
        {"question": str},
        "BLOCKED research | 3 rounds | 0 pages\nno useful results",
    )
    assert __main__.main(["research", "anything"]) == 1
    assert capsys.readouterr().out.startswith("BLOCKED research")


def test_research_passes_the_question_through(monkeypatch, capsys):
    seen: list[dict] = []
    monkeypatch.setitem(
        TOOLS,
        "research",
        Tool("research", "Fake research.", {"question": str}, lambda **kwargs: seen.append(kwargs) or "OK"),
    )
    assert __main__.main(["research", "who wrote Emma?"]) == 0
    assert seen == [{"question": "who wrote Emma?"}]


def test_help_lists_the_search_commands():
    help_text = __main__._parser().format_help()
    assert "search" in help_text
    assert "research" in help_text
