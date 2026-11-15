"""judge(): ask Bonsai to answer from the page and quote its evidence; code checks the quote."""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date

from llm import client, tokens

from . import prompts

PAGE_BUDGET = 6000      # tokens of page text per judge call
MIN_PIECE = 8           # quote pieces shorter than this (normalised) are not checked

_TRANS = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'",
                        "“": '"', "”": '"', "„": '"', "′": "'",
                        "‐": "-", "‑": "-", "‒": "-", "–": "-",
                        "—": "-", "―": "-", "−": "-", " ": " "})
_SPLIT = re.compile(r"\.\.\.|…|\n")
_EDGE = " \t.,;:!?\"'`*-•()[]"


@dataclass
class Verdict:
    enough: bool
    answer: str | None
    evidence: str | None    # the quote, only when it passed the check
    reason: str             # answered | no_answer | quote_not_in_page | not_this_question | bad_json | blocked_page
    url: str | None = None
    chunk: int = 0          # index of the chunk that answered (or the last one judged)
    chunks: int = 1
    seconds: float = 0.0    # model time for this judge call, all chunks


def normalise(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_TRANS).lower()
    return re.sub(r"\s+", " ", s).strip()


def quote_in_page(quote: str, page: str) -> bool:
    """True when every piece of 8+ chars of the quote appears in the page, and one exists.

    Ignores case, whitespace runs, curly vs straight quotes, dash types and
    punctuation at the ends of each piece. Pieces are split on "...", "…" and newlines.
    """
    if not quote:
        return False
    pg = normalise(page)
    pieces = [normalise(p).strip(_EDGE) for p in _SPLIT.split(quote)]
    long = [p for p in pieces if len(p) >= MIN_PIECE]
    return bool(long) and all(p in pg for p in long)


def _empty(x) -> bool:
    if x is None:
        return True
    if isinstance(x, (list, tuple)):
        return all(_empty(i) for i in x)
    return str(x).strip().lower().strip(".") in ("", "null", "none", "n/a", "unknown")


def _as_text(x) -> str:
    if isinstance(x, (list, tuple)):
        return "\n".join(str(i) for i in x if i is not None)
    return str(x)


def _judge_one(question: str, page: str, url: str | None, today: str) -> tuple[Verdict, float]:
    t0 = time.monotonic()
    try:
        got = client.complete_json(
            prompts.judge_prompt(question, page, url, today), system=prompts.JUDGE_SYSTEM,
            json_schema_hint=prompts.judge_hint(), max_tokens=prompts.JUDGE_MAX_TOKENS,
            sampling=prompts.JUDGE_SAMPLING)
    except client.JSONReplyError:
        return Verdict(False, None, None, "bad_json", url), time.monotonic() - t0
    dt = time.monotonic() - t0
    if not isinstance(got, dict):
        return Verdict(False, None, None, "bad_json", url), dt
    answer, quote = got.get("answer"), got.get("quote")
    if _empty(answer) or _empty(quote):
        return Verdict(False, None, None, "no_answer", url), dt
    quote = _as_text(quote)
    if not quote_in_page(quote, page):
        return Verdict(False, None, None, "quote_not_in_page", url), dt
    answer = _as_text(answer).strip()
    if prompts.CHECK_ANSWER:
        t1 = time.monotonic()
        r = client.chat([{"role": "system", "content": prompts.CHECK_SYSTEM},
                         {"role": "user", "content": prompts.check_prompt(
                             question, answer, quote, today)}],
                        max_tokens=prompts.CHECK_MAX_TOKENS, sampling=prompts.JUDGE_SAMPLING)
        dt += time.monotonic() - t1
        if not r.text.strip().lstrip("\"'*`( ").upper().startswith("A"):
            return Verdict(False, None, None, "not_this_question", url), dt
    return Verdict(True, answer, quote.strip(), "answered", url), dt


def judge(question: str, page_text: str, url: str | None = None,
          today: date | str | None = None) -> Verdict:
    """Does page_text answer question? Long pages are judged chunk by chunk."""
    today_s = prompts.fmt_today(today)
    chunks = tokens.split_to_budget(page_text, PAGE_BUDGET) if page_text.strip() else [""]
    total = 0.0
    v = Verdict(False, None, None, "no_answer", url)
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        v, dt = _judge_one(question, chunk, url, today_s)
        total += dt
        v.chunk, v.chunks = i, len(chunks)
        if v.enough:
            break
    v.chunks, v.seconds = len(chunks), total
    return v
