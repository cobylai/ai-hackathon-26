"""S7: page text is cached for a day, and a second open never touches the browser."""

from __future__ import annotations

import re

import pytest

from harness import llm
from harness.browser import tools as browser_tools
from harness.search import cache, loop, tools
from harness.search.google import Result

ARTICLE = (
    "<html><head><title>The Lighthouse Keeper</title></head><body><article>"
    "<p>The lighthouse stood at the end of a long stone breakwater.</p>"
    "</article></body></html>"
)
CAPTCHA = (
    "<html><head><title>Just a moment...</title></head>"
    "<body><p>Verify you are human to continue.</p></body></html>"
)


class Clock:
    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value


@pytest.fixture()
def clock(monkeypatch):
    tick = Clock()
    monkeypatch.setattr(cache, "_now", tick)
    return tick


def test_missing_url_returns_none(clock):
    assert cache.get("https://example.org/nothing") is None


def test_put_then_get(clock):
    cache.put("https://example.org/a", "Some page text.")
    assert cache.get("https://example.org/a") == "Some page text."


def test_entries_expire_after_a_day(clock):
    cache.put("https://example.org/a", "Some page text.")
    clock.value += cache.TTL_SECONDS - 1
    assert cache.get("https://example.org/a") == "Some page text."
    clock.value += 2
    assert cache.get("https://example.org/a") is None


def test_put_replaces_the_old_copy(clock):
    cache.put("https://example.org/a", "old")
    clock.value += 60
    cache.put("https://example.org/a", "new")
    assert cache.get("https://example.org/a") == "new"


def test_empty_text_is_not_stored(clock):
    cache.put("https://example.org/a", "   ")
    assert cache.get("https://example.org/a") is None


def test_cache_lives_in_the_configured_file(clock):
    cache.put("https://example.org/a", "text")
    assert cache.db_path().is_file()
    assert cache.db_path().name == "cache.db"


class CountingPage:
    """Minimal Page that counts navigations."""

    def __init__(self, html: str) -> None:
        self.html = html
        self.goto_calls = 0
        self.url = ""

    def goto(self, url: str, wait_until=None, timeout=None):
        self.goto_calls += 1
        self.url = url
        return type("Response", (), {"status": 200})()

    def content(self) -> str:
        return self.html

    def title(self) -> str:
        match = re.search(r"<title>(.*?)</title>", self.html, re.S)
        return match.group(1) if match else ""

    def inner_text(self, selector: str) -> str:
        return re.sub(r"<[^>]+>", " ", self.html)


@pytest.fixture()
def counting_page(monkeypatch):
    page = CountingPage(ARTICLE)
    monkeypatch.setattr(browser_tools, "_page", lambda: page)
    return page


def test_second_open_does_not_hit_the_browser(clock, counting_page):
    first = tools.open_page("https://example.org/article")
    assert counting_page.goto_calls == 1
    second = tools.open_page("https://example.org/article")
    assert counting_page.goto_calls == 1  # served from the cache
    assert first == second
    assert "lighthouse stood at the end" in second[1]


def test_blocked_pages_are_not_cached(clock, monkeypatch):
    page = CountingPage(CAPTCHA)
    monkeypatch.setattr(browser_tools, "_page", lambda: page)
    word, text = tools.open_page("https://example.org/wall")
    assert word == "BLOCKED" and text == ""
    assert cache.get("https://example.org/wall") is None


def test_loop_reuses_the_cache_on_a_second_run(clock, counting_page, monkeypatch):
    results = [Result("Page", "https://example.org/article", "example.org", "snippet")]
    replies = ["1", "A useful note.", "YES", "Answer [1]."]

    def run():
        return loop.research(
            "how long was the breakwater?",
            ask=llm.FakeLLM(replies).ask,
            search=lambda query: results,
        )

    first = run()
    second = run()
    assert counting_page.goto_calls == 1  # the second run read the cache
    assert first.notes and second.notes
    assert first.answer.splitlines()[0] == second.answer.splitlines()[0]
