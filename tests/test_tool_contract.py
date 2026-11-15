"""Every registered tool, called the way the reasoning layer calls it.

The registry entry is the product surface: `TOOLS[name].run(**args)` with the
args it declares. These tests go through that surface rather than the inner
functions, because two bugs (a paging hint pointing at another group's tool,
and a wall-stop that never fired behind the eval's wrapper) passed their
unit tests and only failed through the caller.
"""

from __future__ import annotations

import pytest

from harness import llm, registry
from harness.browser import tools as browser_tools
from harness.search import engine
from harness.search.google import Result

STATUS_WORDS = {"OK", "BLOCKED", "LOGIN", "ERR"}


def check(out: str) -> str:
    assert isinstance(out, str)
    assert len(out) <= 1500, f"{len(out)} chars"
    assert out.split()[0] in STATUS_WORDS, out[:80]
    return out


def call(name: str, **args) -> str:
    """Call a tool the way a model would: by name, with the declared args only."""
    tool = registry.TOOLS[name]
    assert set(args) == set(tool.args), f"{name} declares {tool.args}, got {set(args)}"
    return check(tool.run(**args))


def number_of(listing: str, needle: str) -> int:
    for line in listing.splitlines():
        if needle in line:
            return int(line.split(".")[0])
    raise AssertionError(f"{needle!r} not in listing:\n{listing}")


@pytest.fixture()
def site_wired(session, site, monkeypatch):
    """The shared browser pointed at the fixture server."""
    monkeypatch.setattr(browser_tools, "get_session", lambda: session)
    engine.reset()
    yield site
    engine.reset()


def test_browser_tools_through_the_registry(site_wired):
    assert "Lighthouse" in call("goto", url=site_wired.url("article.html"))
    assert call("read", page=1).startswith("OK")

    call("goto", url=site_wired.url("form.html"))
    listing = call("elements", filter="")
    field = number_of(listing, "Search terms")
    button = number_of(listing, "Submit")
    assert call("type", n=field, text="hello harness", enter=0).startswith("OK")
    assert call("click", n=button).startswith("OK")

    call("goto", url=site_wired.url("article.html"))
    call("goto", url=site_wired.url("hello.html"))
    assert "Lighthouse" in call("back")


def test_search_tools_through_the_registry(site_wired, monkeypatch):
    results = [Result("The Lighthouse Keeper", site_wired.url("article.html"), "127.0.0.1", "a story")]
    monkeypatch.setattr(engine, "search", lambda query: results)

    out = call("search", query="lighthouse keeper")
    assert out.startswith("OK search | 1 results")
    assert call("open_result", n=1, page=1).startswith("OK 127.0.0.1 | result 1 | page 1/")
    assert call("open_result", n=1, page=2).startswith("OK 127.0.0.1 | result 1 | page 2/")


def test_research_through_the_registry(site_wired, monkeypatch):
    results = [Result("The Lighthouse Keeper", site_wired.url("article.html"), "127.0.0.1", "")]
    monkeypatch.setattr(engine, "search", lambda query: results)
    replies = iter(
        ["1", "The keeper climbed one hundred and twelve steps.", "YES", "He climbed 112 [1]."]
    )
    monkeypatch.setattr(llm, "ask", lambda prompt, choices=None, max_tokens=64: next(replies))

    out = call("research", question="how many steps did the keeper climb?")
    assert out.startswith("OK research |")
    assert "Sources: 1. 127.0.0.1" in out


def test_every_tool_is_callable_with_its_declared_args():
    """Cheap structural guard: the declared args are the callable's parameters."""
    import inspect

    for name, tool in registry.TOOLS.items():
        params = inspect.signature(tool.run).parameters
        assert set(params) == set(tool.args), name
        assert all(value in (str, int) for value in tool.args.values()), name
