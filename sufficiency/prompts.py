"""Prompt text for judging and rephrasing. All calls go to local Bonsai via llm.client."""
from __future__ import annotations

from datetime import date

# Low temperature for judging and rephrasing; the other preset values stay.
JUDGE_SAMPLING = {"temperature": 0.2}
JUDGE_MAX_TOKENS = 300
REPHRASE_MAX_TOKENS = 40

JUDGE_SYSTEM = ("You answer questions using only the web page you are given. "
                "You never use outside knowledge and never guess.")

JUDGE_HINT = ('{"answer": "short answer, or null", '
              '"quote": "exact text copied from the page, or null"}')

REPHRASE_SYSTEM = "You write short web search queries."


def fmt_today(today: date | str | None) -> str:
    if today is None:
        today = date.today()
    if isinstance(today, date):
        return today.strftime("%A, %d %B %Y").replace(" 0", " ")
    return str(today)


def judge_prompt(question: str, page: str, url: str | None, today: str) -> str:
    # complete_json appends "Reply with only a JSON object ... matching this shape: JUDGE_HINT".
    return (f"Today is {today}.\n\nQUESTION: {question}\n\n"
            f"PAGE ({url or 'unknown url'}):\n{page}\n\n"
            "If the page answers the question, even in different words, give the answer "
            "and copy the exact line from the page that supports it. If the page does not "
            "answer it, set answer and quote to null.")


def rephrase_prompt(question: str, tried: list[str], today: str) -> str:
    tried_s = "\n".join(f"- {q}" for q in tried) or "- (none)"
    return (f"Today is {today}. We are searching the web to answer: {question}\n\n"
            f"Queries already tried (do not repeat them or reword them trivially):\n{tried_s}\n\n"
            "Write one new search query that is more likely to find a page with the answer. "
            "Reply with only the query.")
