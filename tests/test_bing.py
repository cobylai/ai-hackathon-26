"""Bing parser (integration fallback after Google and DuckDuckGo)."""

from __future__ import annotations

import base64
from pathlib import Path

from harness.search import bing

HTML = (Path(__file__).parent / "pages" / "bing_results.html").read_text(encoding="utf-8")


def test_fixture_yields_results():
    results = bing.parse(HTML)
    assert len(results) >= 8
    assert results[0].url == "https://www.python.org/"
    assert results[0].domain == "python.org"
    for item in results:
        assert item.title and item.url.startswith("http") and len(item.snippet) <= 120
    assert [r.domain for r in results].count("python.org") <= 2


def test_ck_links_are_unwrapped():
    target = "https://example.org/a?b=1"
    enc = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
    html = (f'<ol><li class="b_algo"><h2><a href="https://www.bing.com/ck/a?!&p=x&u=a1{enc}&ntb=1">'
            f'Example</a></h2><div class="b_caption"><p>Snip</p></div></li></ol>')
    out = bing.parse(html)
    assert out[0].url == target and out[0].snippet == "Snip"


def test_empty_and_bad_input():
    assert bing.parse("") == []
    assert bing.parse("<html><body>no results</body></html>") == []
