"""Rank page chunks against the question with BM25, so the model reads 2 chunks.

`top_chunks` splits the page into ~600-character chunks on paragraph
boundaries, scores them against the question's words and returns the best few
in page order. Pure Python, no model.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

CHUNK_CHARS = 600

STOP_WORDS = frozenset(
    """
    a about above after again against all am an and any are as at be because been before
    being below between both but by can could did do does doing down during each few for
    from further had has have having he her here hers herself him himself his how i if in
    into is it its itself just me more most my myself no nor not now of off on once only
    or other our ours ourselves out over own same she should so some such than that the
    their theirs them themselves then there these they this those through to too under
    until up very was we were what when where which while who whom why will with would you
    your yours yourself yourselves
    """.split()
)

TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
SENTENCE_RE = re.compile(r"[.!?](?=\s)")


def _tokens(text: str) -> list[str]:
    return [word for word in TOKEN_RE.findall(text.lower()) if word not in STOP_WORDS]


def _split_point(text: str, limit: int) -> int:
    """Cut at a sentence end before ``limit`` if there is one, else at a word."""
    window = text[:limit]
    best = None
    for match in SENTENCE_RE.finditer(window):
        best = match.end()
    if best and best >= limit // 2:
        return best
    space = window.rfind(" ")
    if space >= limit // 2:
        return space
    return limit


def chunk_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Paragraph-aware chunks of about ``size`` characters, in page order."""
    text = (text or "").strip()
    if not text or size < 50:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        while len(paragraph) > size:
            cut = _split_point(paragraph, size)
            piece = paragraph[:cut].strip()
            if current:
                chunks.append(current)
                current = ""
            if piece:
                chunks.append(piece)
            paragraph = paragraph[cut:].strip()
        if not paragraph:
            continue
        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 2 <= size:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def top_chunks(text: str, question: str, k: int = 2, size: int = CHUNK_CHARS) -> list[str]:
    """The ``k`` chunks that best answer ``question``, returned in page order."""
    chunks = chunk_text(text, size=size)
    if not chunks or k <= 0:
        return []

    docs = [_tokens(chunk) for chunk in chunks]
    query = _tokens(question)
    if not query or not any(docs):
        return chunks[:k]

    try:
        scores = BM25Okapi(docs).get_scores(query)
    except Exception:  # empty documents or a BM25 edge case: fall back to page order
        return chunks[:k]

    ranked = sorted(range(len(chunks)), key=lambda i: (-scores[i], i))
    chosen = ranked[: min(k, len(chunks))]
    if scores[chosen[0]] <= 0:
        # Nothing in the page matches the question: keep the opening chunks.
        return chunks[: min(k, len(chunks))]
    if k >= 2 and 0 not in chosen:
        # Definitions, dates and summaries live in the opening chunk, and BM25
        # can miss them when the question words are spread over a long page.
        # Keep one slot for it and let BM25 fill the rest.
        chosen = [0, *ranked[: k - 1]]
    return [chunks[i] for i in sorted(chosen)]
