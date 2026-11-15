"""S2: DuckDuckGo parsing and the Google-then-DDG engine switch."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness.search import ddg, engine

PAGES = Path(__file__).parent / "pages"
DDG_HTML = (PAGES / "ddg_results.html").read_text(encoding="utf-8", errors="replace")
CAPTCHA_HTML = (PAGES / "captcha.html").read_text(encoding="utf-8", errors="replace")
DDG_CHALLENGE = (
    "<html><head><title>DuckDuckGo</title></head><body><p>Unfortunately, bots use "
    "DuckDuckGo too. Please complete the following challenge to confirm this search was "
    "made by a human. Select all squares containing a duck:</p></body></html>"
)


# --- DuckDuckGo parser -----------------------------------------------------


def result(href: str, title: str, snippet: str = "", wrapper_class: str = "") -> str:
    return (
        f'<div class="result results_links web-result {wrapper_class}">'
        f'<div class="links_main result__body">'
        f'<h2 class="result__title"><a class="result__a" href="{href}">{title}</a></h2>'
        f'<a class="result__snippet" href="{href}">{snippet}</a>'
        f"</div></div>"
    )


def page(*blocks: str) -> str:
    return '<html><body><div class="results">' + "".join(blocks) + "</div></body></html>"


def test_fixture_yields_results():
    results = ddg.parse(DDG_HTML)
    assert len(results) >= 8
    for item in results:
        assert item.title
        assert item.url.startswith("http")
        assert item.domain
        assert len(item.snippet) <= 120


def test_fixture_first_result_and_domain_cap():
    results = ddg.parse(DDG_HTML)
    assert results[0].title.startswith("The official home of the Python")
    assert results[0].url.startswith("https://www.python.org/")
    domains = [item.domain for item in results]
    assert domains.count("python.org") == 2  # capped, not four


def test_redirect_links_are_unwrapped():
    href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fa%3Fb%3D1&rut=abc"
    out = ddg.parse(page(result(href, "Example")))
    assert out[0].url == "https://example.org/a?b=1"
    assert out[0].domain == "example.org"


def test_ads_are_dropped():
    html = page(
        result("https://ad.example/", "Sponsored", wrapper_class="result--ad"),
        result("https://keep.example/", "Keep me", "A real result."),
    )
    assert [item.domain for item in ddg.parse(html)] == ["keep.example"]


def test_only_two_results_per_domain():
    blocks = [result(f"https://same.example/{n}", f"Page {n}") for n in range(4)]
    out = ddg.parse(page(*blocks, result("https://other.example/", "Other")))
    assert [item.domain for item in out] == ["same.example", "same.example", "other.example"]


def test_bad_input_is_empty_not_fatal():
    assert ddg.parse("") == []
    assert ddg.parse("<html><body>nothing</body></html>") == []


# --- Engine switch ---------------------------------------------------------


class FakeResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status


class FakePage:
    """Just enough Page for `state.classify` and `engine.search`."""

    def __init__(self, routes: dict[str, str], status: int = 200) -> None:
        self.routes = routes
        self.status = status
        self.visited: list[str] = []
        self.url = ""
        self._html = ""

    def goto(self, url: str, wait_until=None, timeout=None):
        self.visited.append(url)
        self.url = url
        for key, html in self.routes.items():
            if key in url:
                self._html = html
                return FakeResponse(self.status)
        self._html = '<html><head><title>empty</title></head><body>no results</body></html>'
        return FakeResponse(self.status)

    def content(self) -> str:
        return self._html

    def title(self) -> str:
        match = re.search(r"<title>(.*?)</title>", self._html, re.S)
        return match.group(1) if match else ""

    def evaluate(self, script: str):
        return None

    def inner_text(self, selector: str) -> str:
        return re.sub(r"<[^>]+>", " ", self._html)

    def query_selector(self, selector: str):
        return None

    def locator(self, selector: str):
        class _Count:
            def count(self) -> int:
                return 0

        return _Count()


class Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value


@pytest.fixture(autouse=True)
def fresh_engine(monkeypatch):
    engine.reset()
    clock = Clock()
    monkeypatch.setattr(engine, "_now", clock)
    yield clock
    engine.reset()


def fake_site(google_html: str = CAPTCHA_HTML) -> FakePage:
    return FakePage({"google.com/search": google_html, "html.duckduckgo.com": DDG_HTML})


def test_blocked_google_falls_back_to_ddg():
    page_ = fake_site()
    results = engine.search("python", page=page_)
    assert len(results) >= 8
    assert engine.last_engine == "duckduckgo"
    assert len(page_.visited) == 2
    assert "google.com/search" in page_.visited[0]
    assert "html.duckduckgo.com" in page_.visited[1]
    assert "q=python" in page_.visited[1]
    assert engine.in_fallback()
    assert engine.last_status == "OK"


def test_empty_google_falls_back_to_ddg():
    page_ = fake_site(google_html='<html><body><div id="rso"></div></body></html>')
    assert engine.search("python", page=page_)
    assert len(page_.visited) == 2


def test_fallback_is_remembered_for_ten_minutes():
    clock = engine._now  # the Clock fixture
    page_ = fake_site()
    engine.search("python", page=page_)
    first = len(page_.visited)
    engine.search("python asyncio", page=page_)
    assert len(page_.visited) == first + 1  # DuckDuckGo only
    assert "duckduckgo" in page_.visited[-1]

    clock.value += engine.FALLBACK_SECONDS + 1
    assert not engine.in_fallback()
    before = len(page_.visited)
    engine.search("python", page=page_)
    # Google is tried again and is still walled, so it falls back once more.
    assert "google.com/search" in page_.visited[before]
    assert "duckduckgo" in page_.visited[before + 1]


def test_walled_ddg_fallback_is_reported_as_blocked():
    page_ = FakePage({"google.com/search": CAPTCHA_HTML, "html.duckduckgo.com": DDG_CHALLENGE})
    assert engine.search("python", page=page_) == []
    assert engine.last_status == "BLOCKED"
    # Both engines failed, so nothing is remembered: the next query tries Google again.
    assert not engine.in_fallback()
    assert len(page_.visited) == 2
    engine.search("python", page=page_)
    assert "google.com/search" in page_.visited[2]


def test_fallback_is_dropped_when_ddg_stops_working():
    page_ = fake_site()
    engine.search("python", page=page_)  # Google walled, DDG answers
    assert engine.in_fallback()
    page_.routes["html.duckduckgo.com"] = DDG_CHALLENGE
    assert engine.search("python", page=page_) == []
    assert not engine.in_fallback()


def test_google_success_does_not_set_fallback():
    google_html = (PAGES / "google_results.html").read_text(encoding="utf-8", errors="replace")
    page_ = fake_site(google_html=google_html)
    results = engine.search("test", page=page_)
    assert results and results[0].domain == "speedtest.net"
    assert len(page_.visited) == 1
    assert not engine.in_fallback()
    assert engine.last_engine == "google"


def test_blank_query_does_not_open_a_page():
    page_ = fake_site()
    assert engine.search("   ", page=page_) == []
    assert page_.visited == []
    assert engine.last_engine == ""
