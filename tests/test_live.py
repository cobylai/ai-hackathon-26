"""Opt-in live checks against real sites.

Skipped unless ``HARNESS_LIVE=1`` is set, so CI stays offline and deterministic:

    HARNESS_LIVE=1 uv run pytest -q tests/test_live.py

These cover the things fixtures cannot: index-page text extraction, paging on a
real long article, and the bot-wall phrase list. They are advisory: a site that
changes its markup or stops walling bots makes them fail, not the harness.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from harness.browser import tools
from harness.browser.session import Session

pytestmark = pytest.mark.skipif(
    os.environ.get("HARNESS_LIVE") != "1", reason="set HARNESS_LIVE=1 to run live checks"
)

STATUS_WORDS = {"OK", "BLOCKED", "LOGIN", "ERR"}


def check(result: str) -> str:
    assert isinstance(result, str)
    assert len(result) <= 1500, f"{len(result)} chars"
    assert result.split()[0] in STATUS_WORDS, result[:80]
    return result


@pytest.fixture(scope="module")
def live():
    """One temp-profile session shared by the live checks."""
    monkeypatch = pytest.MonkeyPatch()
    session = Session(tempfile.mkdtemp(prefix="live-"))
    session.start()
    monkeypatch.setattr(tools, "get_session", lambda: session)
    try:
        yield tools
    finally:
        session.stop()
        monkeypatch.undo()


def test_example_domain(live):
    out = check(live.goto("https://example.com"))
    assert out.startswith("OK")
    assert "Example Domain" in out


def test_wikipedia_article_pages(live):
    first = check(live.goto("https://en.wikipedia.org/wiki/Lighthouse"))
    assert first.startswith("OK")
    assert "page 1/" in first
    assert "lighthouse" in first.lower()

    second = check(live.read(2))
    assert "page 2/" in second
    # Page 2 continues the article rather than repeating page 1.
    assert second.split("\n", 1)[1][:80] != first.split("\n", 1)[1][:80]


def test_index_page_text_is_usable(live):
    """BBC has no article to extract; the body fallback must still return text."""
    out = check(live.goto("https://www.bbc.com/news"))
    assert out.startswith("OK")
    body = out.split("\n", 1)[1] if "\n" in out else ""
    assert len(body) > 600, f"only {len(body)} chars of text"


def test_article_about_captcha_is_not_blocked(live):
    out = check(live.goto("https://en.wikipedia.org/wiki/CAPTCHA"))
    assert out.startswith("OK"), out.splitlines()[0]
