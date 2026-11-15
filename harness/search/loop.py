"""The research loop: search, open, note, decide, retry — at most three rounds.

Every step the model takes is a small question from `prompts`; every decision
code can make (caps, dedupe, skipping walled pages, ranking chunks) is made
here. The loop always ends: rounds, pages per round and results are capped, and
a repeated query stops it early.
"""

from __future__ import annotations

import os
import time
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


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Experiment (docs/plan/notes-search-eval.md): end a round that added this many
# notes instead of spending a model call asking whether they are enough.
# 0 keeps the measured behaviour; HARNESS_STOP_AFTER_NOTES=2 turns it on.
STOP_AFTER_NOTES = _env_int("HARNESS_STOP_AFTER_NOTES")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Wall-clock ceiling for one question. The step caps bound how many things happen;
# a hung page plus slow model calls can still stall for minutes without this.
MAX_SECONDS = _env_float("HARNESS_RESEARCH_SECONDS", 120.0)

Note = tuple[int, str, str]


class BudgetSpent(Exception):
    """Raised inside the loop when a question runs past `MAX_SECONDS`."""


def _now() -> float:
    """Monotonic clock, separate so tests can drive it."""
    return time.monotonic()


@dataclass
class Outcome:
    """What the loop produced, plus the numbers S8's evaluation needs."""

    answer: str
    rounds: int
    pages: int
    notes: list[Note] = field(default_factory=list)
    # Non-empty when the harness could not do the work (a silent model, for one).
    error: str = ""


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
        return _notes_answer(notes)
    return f"{_words(text, MAX_ANSWER_WORDS)}\n{_sources(notes)}"


def _notes_answer(notes: Sequence[Note]) -> str:
    """The answer without asking the model: the notes themselves, plus sources."""
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
    error = ""
    started = _now()

    def spent() -> bool:
        return _now() - started > MAX_SECONDS

    for round_no in range(1, MAX_ROUNDS + 1):
        if spent():
            break
        rounds = round_no
        tried.add(query.lower())
        results = list(find(query))[:MAX_RESULTS]
        # `last_query` proves the status came from this query; an identity check
        # misses the case where the caller wraps `engine.search` (the evaluation
        # does exactly that to record the engine per question).
        fresh = engine.last_query == " ".join(query.split())
        if not results and fresh and engine.last_status in ("BLOCKED", "LOGIN", "ERR"):
            # A wall, a sign-in or a dead engine is not a query problem: rewriting
            # hits the same thing, and Run 4 spent three searches per question proving it.
            break
        if results:
            picks = prompts.pick(question, results, ask)
            if picks is None:
                error = "the model returned nothing; check LLM_BASE_URL and LLM_MODEL"
                break
            picks = picks[:MAX_PAGES_PER_ROUND]
        else:
            picks = []
        first_new_note = len(notes)

        for number in picks:
            if spent():
                break
            item = results[number - 1]
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            pages += 1
            try:
                word, text = open_page(item.url)
            except Exception:
                # One unreachable page must not throw away the notes already collected.
                continue
            if word != "OK" or not (text or "").strip():
                continue
            for chunk in top_chunks(text, question, k=MAX_CHUNKS):
                written = prompts.note(question, chunk, ask)
                if written:
                    # Number notes in the order they are collected, so [1], [2] in the
                    # answer always match the numbered Sources list.
                    notes.append((len(notes) + 1, item.domain, written))
                    break

        # Optional stop rule, off by default: two independent notes from one round
        # are usually enough, and this saves the `enough` call and a later round.
        if STOP_AFTER_NOTES and len(notes) - first_new_note >= STOP_AFTER_NOTES:
            break

        # Nothing after the last round can change the answer, so do not spend a
        # model call asking whether the notes are enough.
        if round_no >= MAX_ROUNDS:
            break
        if notes and prompts.enough(question, notes, ask):
            break

        if spent():
            break
        # The rewrite only needs to know what this round added.
        new_query = prompts.rewrite(question, query, notes[first_new_note:], ask)
        if not new_query or new_query.lower() in tried:
            break
        query = new_query

    if error:
        answer = "The model did not answer, so the question could not be researched."
    elif not rounds:
        answer = f'Ran out of time before searching for "{question}".'
    elif not notes:
        answer = (
            f'No useful results were found for "{question}" after '
            f"{rounds} search round{'s' if rounds != 1 else ''}."
        )
    elif spent():
        # Out of time: report what the notes already say instead of calling the model.
        answer = _notes_answer(notes)
    else:
        answer = _answer(question, notes, ask)
    return Outcome(answer, rounds, pages, notes, error)
