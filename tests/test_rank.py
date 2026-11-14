"""S4: BM25 chunk ranking picks the paragraph that answers the question."""

from __future__ import annotations

from pathlib import Path

from harness.browser.text import page_text
from harness.search.rank import CHUNK_CHARS, chunk_text, top_chunks

ANSWER = (
    "The spare mantle had been wrapped in oilcloth and stored in the room below the "
    "gallery, and the keeper carried it up the one hundred and twelve steps."
)

FILLER = [
    "The road along the coast was resurfaced twice that decade, and the council argued "
    "about the drainage for most of one summer before anything was actually dug.",
    "Fishing boats came in with the tide, and the harbour wall collected weed and rope "
    "ends and the occasional plastic bottle that nobody admitted to dropping.",
    "In the village school the children learned the names of the birds and the phases of "
    "the moon, and the teacher wrote both lists on the same blackboard in white chalk.",
    "The museum printed a pamphlet, the shop sold postcards, and a small cafe opened in "
    "the old boathouse with four tables and a hand-painted sign above the door.",
    "Every Thursday the mail boat brought letters, a newspaper two days old, and a crate "
    "of tinned food that the keeper stacked in the cupboard beside the stove.",
]


def long_article() -> str:
    """Forty paragraphs where only one mentions the mantle."""
    paragraphs = []
    for n in range(40):
        paragraphs.append(FILLER[n % len(FILLER)])
        if n == 27:
            paragraphs.append(ANSWER)
    return "\n\n".join(paragraphs)


def test_answer_chunk_is_in_the_top_two():
    text = long_article()
    picked = top_chunks(text, "What did the keeper do about the cracked mantle?")
    assert len(picked) == 2
    assert any(ANSWER in chunk for chunk in picked)


def test_chunks_come_back_in_page_order():
    filler = "Ordinary filler about the sea and the light. " * 6
    paragraphs = [f"Paragraph {n}. {filler}" for n in range(30)]
    paragraphs[5] = "The cracked mantle was replaced by the keeper at once. " * 4
    paragraphs[25] = "The spare mantle waited in the oilcloth store. " * 4
    picked = top_chunks("\n\n".join(paragraphs), "cracked spare mantle", k=2)
    assert len(picked) == 2
    assert "cracked" in picked[0]
    assert "spare" in picked[1]


def test_k_is_respected():
    text = long_article()
    assert len(top_chunks(text, "mantle", k=1)) == 1
    assert len(top_chunks(text, "mantle", k=3)) == 3


def test_chunks_are_about_the_requested_size():
    chunks = chunk_text(long_article(), size=400)
    assert len(chunks) > 5
    assert all(len(chunk) <= 400 for chunk in chunks)


def test_long_paragraph_is_split():
    text = "word " * 400
    chunks = chunk_text(text, size=200)
    assert len(chunks) >= 4
    assert all(len(chunk) <= 200 for chunk in chunks)
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_empty_text_and_bad_k():
    assert top_chunks("", "anything") == []
    assert top_chunks("some text here", "anything", k=0) == []
    assert chunk_text("   ") == []


def test_nonsense_question_falls_back_to_the_start():
    text = long_article()
    picked = top_chunks(text, "zzz qqq", k=2)
    assert picked == chunk_text(text)[:2]


def test_question_without_content_words():
    text = long_article()
    assert top_chunks(text, "what is it", k=1) == chunk_text(text)[:1]


def test_real_article_fixture():
    html = (Path(__file__).parent / "pages" / "article.html").read_text(encoding="utf-8")
    text = page_text(html)
    picked = top_chunks(text, "How many years did the keeper keep the light?")
    assert any("thirty-one years" in chunk for chunk in picked)


def test_default_chunk_size_is_sane():
    assert CHUNK_CHARS == 600
    assert all(len(chunk) <= CHUNK_CHARS for chunk in chunk_text(long_article()))
