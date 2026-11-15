"""rephrase(): one new search query that is not a repeat of the ones tried."""
from __future__ import annotations

import re
from datetime import date

from llm import client

from . import prompts


def _words(q: str) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", q.lower()).split()


def is_repeat(query: str, tried: list[str]) -> bool:
    w = _words(query)
    if not w:
        return True
    return any(w == _words(t) or set(w) == set(_words(t)) for t in tried)


def _clean(text: str) -> str:
    line = next((l for l in text.strip().splitlines() if l.strip()), "")
    line = re.sub(r"^\s*(new\s+)?(search\s+)?query\s*:\s*", "", line, flags=re.I)
    return line.strip().strip("\"'`").strip()


def rephrase(question: str, tried_queries: list[str],
             today: date | str | None = None) -> str | None:
    """Return one new query, or None if the model repeats itself twice."""
    today_s = prompts.fmt_today(today)
    msgs = [{"role": "system", "content": prompts.REPHRASE_SYSTEM},
            {"role": "user", "content": prompts.rephrase_prompt(question, tried_queries, today_s)}]
    for attempt in range(2):
        q = _clean(client.chat(msgs, max_tokens=prompts.REPHRASE_MAX_TOKENS,
                               sampling=prompts.JUDGE_SAMPLING).text)
        if not is_repeat(q, tried_queries):
            return q
        msgs += [{"role": "assistant", "content": q},
                 {"role": "user", "content": f'"{q}" repeats a query already tried. '
                  "Write a different one. Reply with only the query."}]
    return None
