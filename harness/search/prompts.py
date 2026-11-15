"""The four small questions the research loop asks the model.

Every function takes an `ask` callable defaulting to `harness.llm.ask`, so
tests can pass a `FakeLLM.ask`. Bad replies are handled here, not by callers:
out-of-range numbers are dropped, empty answers become "no answer".
"""

from __future__ import annotations

import re
from typing import Callable, Iterable, Sequence

from harness import llm

Ask = Callable[..., str]

MAX_PICKS = 3
MAX_NOTE_CHARS = 300
MAX_QUERY_CHARS = 120


def _ask(ask: Ask | None) -> Ask:
    return ask if ask is not None else llm.ask


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _result_line(n: int, item) -> str:
    title = _clean(getattr(item, "title", str(item)))
    domain = _clean(getattr(item, "domain", ""))
    snippet = _clean(getattr(item, "snippet", ""))
    return f"{n}. {title} ({domain}) {snippet}".strip()


def _notes_text(notes: Iterable) -> str:
    if isinstance(notes, str):
        return _clean(notes)
    lines = []
    for note in notes:
        if isinstance(note, (tuple, list)):
            source, domain, text = (list(note) + ["", "", ""])[:3]
            lines.append(f"- [{source}] {domain}: {_clean(str(text))}")
        else:
            lines.append(f"- {_clean(str(note))}")
    return "\n".join(lines) or "(none)"


def _numbers(reply: str, count: int, limit: int = MAX_PICKS) -> list[int]:
    picked: list[int] = []
    for token in re.findall(r"\d+", reply or ""):
        number = int(token)
        if 1 <= number <= count and number not in picked:
            picked.append(number)
    return picked[:limit]


def pick(question: str, results: Sequence, ask: Ask | None = None) -> list[int]:
    """Result numbers worth opening, best first; [] when nothing looks useful."""
    ask = _ask(ask)
    listing = "\n".join(_result_line(n, item) for n, item in enumerate(results, 1))
    prompt = (
        f"Question: {question}\n\n"
        f"Search results:\n{listing}\n\n"
        "Choose up to 3 results worth opening to answer the question, best first. "
        "Reply with their numbers, separated by commas. Use only numbers from the list. "
        "Reply NONE if none of them look useful."
    )
    return _numbers(ask(prompt, max_tokens=24), len(results))


def note(question: str, chunk: str, ask: Ask | None = None) -> str | None:
    """One or two sentences from ``chunk`` that help, or None."""
    ask = _ask(ask)
    prompt = (
        f"Question: {question}\n\n"
        f"Page chunk:\n{chunk}\n\n"
        "Write one or two short sentences from the chunk that help answer the question. "
        "Do not add anything the chunk does not say. Reply NONE if the chunk does not help."
    )
    text = _clean(ask(prompt, max_tokens=90))
    if not text or text.upper().startswith("NONE"):
        return None
    return text[:MAX_NOTE_CHARS]


def enough(question: str, notes, ask: Ask | None = None) -> bool:
    """True when the notes answer the question completely."""
    ask = _ask(ask)
    prompt = (
        f"Question: {question}\n\n"
        f"Notes from pages already read:\n{_notes_text(notes)}\n\n"
        "Do these notes contain everything needed to answer the question? "
        "Reply YES or NO."
    )
    return ask(prompt, choices=["YES", "NO"], max_tokens=4) == "YES"


def rewrite(question: str, query: str, notes, ask: Ask | None = None) -> str:
    """A better search query; the old one when the model has nothing to add."""
    ask = _ask(ask)
    prompt = (
        f"Question: {question}\n\n"
        f"Search query already tried: {query}\n"
        f"What the notes say so far:\n{_notes_text(notes)}\n\n"
        "Write one better search query, at most 8 words, that is likely to fill the gap. "
        "No quotes, no explanation. Reply with the query only."
    )
    reply = ask(prompt, max_tokens=32)
    for line in (reply or "").splitlines():
        line = _clean(line).strip("\"'`*# ")
        if line:
            return line[:MAX_QUERY_CHARS]
    return query
