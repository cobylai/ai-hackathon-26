"""The research loop: search, open, note, decide, retry — at most three rounds.

Every step the model takes is a small question from `prompts`; every decision
code can make (caps, dedupe, skipping walled pages, ranking chunks) is made
here. The loop always ends: rounds, pages per round and results are capped, and
a repeated query stops it early.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

from harness import llm
from harness.search import engine, prompts
from harness.search.rank import top_chunks

MAX_ROUNDS = 3
# Two pages per round: the third page rarely changed the answer in the S8 run and
# it dominated the model input (q05 spent 14 calls and 15.6k chars on one answer).
MAX_PAGES_PER_ROUND = 2
MAX_RESULTS = 10
MAX_CHUNKS = 2
MAX_ANSWER_WORDS = 120

Note = tuple[int, str, str]


@dataclass
class Outcome:
    """What the loop produced, plus the numbers S8's evaluation needs."""

    answer: str
    rounds: int
    pages: int
    notes: list[Note] = field(default_factory=list)


def _words(text: str, limit: int) -> str:
    words = text.split()
    return " ".join(words[:limit])


def _sources(notes: Sequence[Note]) -> str:
    seen: list[int] = []
    parts: list[str] = []
    for number, domain, _ in notes:
        if number not in seen:
            seen.append(number)
            parts.append(f"{number}. {domain}")
    return "Sources: " + ", ".join(parts)


def _answer(question: str, notes: Sequence[Note], ask: Callable[..., str]) -> str:
    listing = "\n".join(f"[{number}] {domain}: {text}" for number, domain, text in notes)
    prompt = (
        f"Question: {question}\n\n"
        f"Notes:\n{listing}\n\n"
        f"Answer in at most {MAX_ANSWER_WORDS} words using only these notes, citing [1], "
        "[2]. If they do not cover it, say what is missing."
    )
    text = " ".join((ask(prompt, max_tokens=260) or "").split())
    if not text:
        text = " ".join(note for _, _, note in notes)
    return f"{_words(text, MAX_ANSWER_WORDS)}\n{_sources(notes)}"


def research(
    question: str,
    ask: Callable[..., str] | None = None,
    search: Callable[[str], list] | None = None,
    open_page: Callable[[str], tuple[str, str]] | None = None,
) -> Outcome:
    """Run the whole loop for ``question`` and return an answer plus stats."""
    ask = ask or llm.ask
    find = search or engine.search
    if open_page is None:
        # Imported here: `search.tools` adds `research`, which calls back into this module.
        from harness.search import tools as tool_module

        open_page = tool_module.open_page

    question = " ".join((question or "").split())
    if not question:
        return Outcome("No question given.", 0, 0)

    notes: list[Note] = []
    seen_urls: set[str] = set()
    tried: set[str] = set()
    query = question
    rounds = 0
    pages = 0

    for round_no in range(1, MAX_ROUNDS + 1):
        rounds = round_no
        tried.add(query.lower())
        results = list(find(query))[:MAX_RESULTS]
        picks = prompts.pick(question, results, ask)[:MAX_PAGES_PER_ROUND] if results else []
        first_new_note = len(notes)

        for number in picks:
            item = results[number - 1]
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            word, text = open_page(item.url)
            pages += 1
            if word != "OK" or not (text or "").strip():
                continue
            for chunk in top_chunks(text, question, k=MAX_CHUNKS):
                written = prompts.note(question, chunk, ask)
                if written:
                    # Number notes in the order they are collected, so [1], [2] in the
                    # answer always match the numbered Sources list.
                    notes.append((len(notes) + 1, item.domain, written))
                    break

        # Nothing after the last round can change the answer, so do not spend a
        # model call asking whether the notes are enough.
        if round_no >= MAX_ROUNDS:
            break
        if notes and prompts.enough(question, notes, ask):
            break

        # The rewrite only needs to know what this round added.
        new_query = prompts.rewrite(question, query, notes[first_new_note:], ask)
        if not new_query or new_query.lower() in tried:
            break
        query = new_query

    if not notes:
        answer = (
            f'No useful results were found for "{question}" after '
            f"{rounds} search round{'s' if rounds != 1 else ''}."
        )
    else:
        answer = _answer(question, notes, ask)
    return Outcome(answer, rounds, pages, notes)
