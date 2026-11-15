"""S3: `search` and `open_result` stay numbered, status-led and under the cap."""

from __future__ import annotations

import pytest

from harness import registry
from harness.search import engine, tools
from harness.search.google import Result

STATUS_WORDS = {"OK", "BLOCKED", "LOGIN", "ERR"}


def check(result: str) -> str:
    assert isinstance(result, str)
    assert len(result) <= 1500, f"{len(result)} chars"
    assert result.split()[0] in STATUS_WORDS, result[:80]
    return result


@pytest.fixture()
def stool(session, site, monkeypatch):
    from harness.browser import tools as browser_tools

    monkeypatch.setattr(browser_tools, "_page", lambda: session.page)
    engine.reset()
    tools.reset()
    yield tools
    tools.reset()


def stub_results(monkeypatch, results: list[Result]) -> None:
    monkeypatch.setattr(tools.engine, "search", lambda query: list(results))


def two_results(site) -> list[Result]:
    return [
        Result(
            "The Lighthouse Keeper",
            site.url("article.html"),
            "127.0.0.1",
            "A story about a lighthouse.",
        ),
        Result("Hello Harness", site.url("hello.html"), "127.0.0.1", "A greeting page."),
    ]


def test_search_lists_numbered_results(stool, monkeypatch, site):
    stub_results(monkeypatch, two_results(site))
    out = check(stool.search("lighthouse keeper"))
    lines = out.splitlines()
    assert lines[0] == "OK search | 2 results"
    assert lines[1].startswith("1. The Lighthouse Keeper (127.0.0.1) A story about a lighthouse.")
    assert lines[2].startswith("2. Hello Harness (127.0.0.1) A greeting page.")


def test_long_result_lists_are_cut_to_the_cap(stool, monkeypatch):
    many = [
        Result(f"Result number {n} " + "x" * 80, f"https://d{n % 7}.example/{n}",
               f"d{n % 7}.example", "snippet " * 15)
        for n in range(1, 31)
    ]
    stub_results(monkeypatch, many)
    out = check(stool.search("anything"))
    lines = out.splitlines()
    assert len(lines) < 31
    assert lines[-1].startswith("[more:")
    shown = [line for line in lines if line[:1].isdigit()]
    assert [int(line.split(".")[0]) for line in shown] == list(range(1, len(shown) + 1))
    # Only the results the model can see stay openable.
    assert len(tools._last) == len(shown)


def test_open_result_reads_the_page(stool, monkeypatch, site):
    stub_results(monkeypatch, two_results(site))
    stool.search("lighthouse")
    out = check(stool.open_result(1))
    assert out.startswith("OK 127.0.0.1 | result 1 | page 1/")
    assert "lighthouse stood at the end" in out


def test_open_result_rejects_unknown_numbers(stool, monkeypatch, site):
    stub_results(monkeypatch, two_results(site))
    before = check(stool.open_result(1))
    assert before.startswith("ERR search | no result 1")

    stool.search("lighthouse")
    assert check(stool.open_result(0)).startswith("ERR")
    assert check(stool.open_result(3)).startswith("ERR")


def test_open_result_reports_a_blocked_page(stool, monkeypatch, site):
    stub_results(
        monkeypatch,
        two_results(site) + [Result("Wall", site.url("captcha.html"), "127.0.0.1", "")],
    )
    stool.search("lighthouse")
    out = check(stool.open_result(3))
    assert out.startswith("BLOCKED 127.0.0.1 | result 3")


def test_empty_search_says_so(stool, monkeypatch):
    stub_results(monkeypatch, [])
    out = check(stool.search("no such thing"))
    assert out.startswith('OK search | no results for "no such thing"')

    engine.last_status = "BLOCKED"
    out = check(stool.search("no such thing"))
    assert out.startswith("BLOCKED search | no results")


def test_registry_exposes_the_search_group(stool, monkeypatch, site):
    assert registry.GROUPS["search"] == ["search", "open_result", "research"]
    entry = registry.TOOLS["search"]
    assert entry.args == {"query": str}
    assert entry.desc and "\n" not in entry.desc and len(entry.desc) <= 100
    assert registry.TOOLS["open_result"].args == {"n": int}

    stub_results(monkeypatch, two_results(site))
    assert check(entry.run(query="lighthouse")).startswith("OK search | 2 results")
    assert check(registry.TOOLS["open_result"].run(n=1)).startswith("OK 127.0.0.1")
