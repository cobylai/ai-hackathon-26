"""B4: main text without chrome, split into word-safe pages."""

from pathlib import Path

from harness.browser import text as text_mod
from harness.browser.text import page_text, paginate

ARTICLE = (Path(__file__).parent / "pages" / "article.html").read_text(encoding="utf-8")


def test_nav_and_footer_are_dropped():
    text = page_text(ARTICLE)
    assert "lighthouse stood at the end" in text
    assert "NAVLINK" not in text
    assert "FOOTER-MARKER" not in text


def test_short_page_falls_back_to_body_text():
    text = page_text("<html><body><p>Just a sentence.</p></body></html>")
    assert text == "Just a sentence."


def test_pages_join_back_into_full_text():
    full = page_text(ARTICLE)
    chunk, total = paginate(full, 1)
    assert total >= 3
    pages = []
    for number in range(1, total + 1):
        chunk, seen_total = paginate(full, number)
        assert seen_total == total
        assert len(chunk) <= 1500
        assert chunk
        pages.append(chunk)
    assert "".join(pages) == full


def test_no_split_words_or_mid_word_breaks():
    full = page_text(ARTICLE)
    _, total = paginate(full, 1)
    pages = [paginate(full, number)[0] for number in range(1, total + 1)]
    for left, right in zip(pages, pages[1:]):
        assert not (left[-1].isalnum() and right[0].isalnum())


def test_edge_cases():
    assert paginate("", 1) == ("", 1)
    assert paginate("one two three", 5) == ("", 1)
    chunk, total = paginate("word " * 400, 1, max_chars=100)
    assert total > 1 and len(chunk) <= 100
    long_word = "x" * 250
    chunk, total = paginate(long_word, 1, max_chars=100)
    assert total == 3 and len(chunk) == 100


def test_sliver_extraction_falls_back_to_body():
    body = "A headline long enough to keep\n" * 100
    assert text_mod._pick_text("tiny", body) == body.strip()


def test_real_article_extraction_wins_over_body():
    full = page_text(ARTICLE)
    body = text_mod._fallback_text(ARTICLE)
    assert len(full) > 0.2 * len(body)
    assert text_mod._pick_text(full, body) == full


def test_fallback_text_drops_scripts_and_keeps_spacing():
    html = "<html><body><script>var x = 1;</script><p>Real words</p><p>Second line</p></body></html>"
    assert text_mod._fallback_text(html) == "Real words\nSecond line"


def test_body_text_is_used_when_extraction_is_empty():
    assert page_text("<html><body><p></p></body></html>", "Visible words") == "Visible words"


def test_body_fallback_drops_menu_labels():
    body = "Home\nNews\nSport\nA real headline that is long enough to keep\n"
    assert text_mod._clean_body(body) == "A real headline that is long enough to keep"
