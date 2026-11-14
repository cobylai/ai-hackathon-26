"""S1: Google results pages parse into short, clean organic results."""

from __future__ import annotations

from pathlib import Path

from harness.search.google import SNIPPET_CHARS, Result, parse

FIXTURE = Path(__file__).parent / "pages" / "google_results.html"


def fixture_results() -> list[Result]:
    return parse(FIXTURE.read_text(encoding="utf-8", errors="replace"))


def result(href: str, title: str, snippet: str = "", extra: str = "") -> str:
    return (
        f'<div class="g"{extra}><div class="rc"><div class="r">'
        f'<a href="{href}"><h3 class="LC20lb">{title}</h3></a>'
        f'<div class="s"><span class="st">{snippet}</span></div>'
        f"</div></div></div>"
    )


def page(*blocks: str) -> str:
    return '<html><body><div id="rso">' + "".join(blocks) + "</div></body></html>"


def test_fixture_yields_eight_to_ten_results():
    results = fixture_results()
    assert 8 <= len(results) <= 10
    for item in results:
        assert item.title
        assert item.url.startswith("http")
        assert item.domain
        assert len(item.snippet) <= SNIPPET_CHARS


def test_fixture_first_result_is_organic():
    first = fixture_results()[0]
    assert "Speedtest by Ookla" in first.title
    assert first.url == "https://www.speedtest.net/"
    assert first.domain == "speedtest.net"
    assert "bandwidth" in first.snippet


def test_google_redirect_links_are_unwrapped():
    html = page(
        result(
            "/url?q=https://example.org/a%3Fb%3D1&amp;sa=U&amp;ved=xyz",
            "Example",
        )
    )
    out = parse(html)
    assert len(out) == 1
    assert out[0].url == "https://example.org/a?b=1"
    assert out[0].domain == "example.org"


def test_ads_and_question_cards_are_dropped():
    ad = f'<div class="uEierd">{result("https://ad.example/", "Buy now")}</div>'
    text_ad = result("https://ads.example/", "Sponsored thing", extra=' data-text-ad="1"')
    paa = (
        '<div class="related-question-pair">'
        '<a href="https://questions.example/"><h3>What is speed?</h3></a>'
        "</div>"
    )
    organic = result("https://keep.example/", "Keep me", "A real result.")
    out = parse(page(ad, text_ad, paa, organic))
    assert [item.domain for item in out] == ["keep.example"]


def test_only_two_results_per_domain():
    blocks = [result(f"https://same.example/{n}", f"Page {n}") for n in range(4)]
    other = result("https://other.example/", "Other")
    out = parse(page(*blocks, other))
    assert [item.domain for item in out] == ["same.example", "same.example", "other.example"]


def test_snippets_are_cut_to_the_cap():
    out = parse(page(result("https://long.example/", "T", "word " * 100)))
    assert len(out[0].snippet) <= SNIPPET_CHARS
    assert out[0].snippet.endswith("...")


def test_titles_are_whitespace_normalized():
    out = parse(page(result("https://ws.example/", "  Many\n   spaces\t here ")))
    assert out[0].title == "Many spaces here"


def test_bad_input_is_empty_not_fatal():
    assert parse("") == []
    assert parse("<html><body>no results</body></html>") == []
