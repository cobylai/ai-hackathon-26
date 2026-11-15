"""Prompt text for judging and rephrasing. All calls go to local Bonsai via llm.client."""
from __future__ import annotations

from datetime import date

# Low temperature for judging and rephrasing; the other preset values stay.
JUDGE_SAMPLING = {"temperature": 0.2}
JUDGE_MAX_TOKENS = 300
REPHRASE_MAX_TOKENS = 40

JUDGE_SYSTEM = ("You answer questions using only the web page you are given. "
                "You never use outside knowledge and never guess.")

ORIGINAL_HINT = ('{"answer": "short answer, or null", '
                 '"quote": "exact text copied from the page, or null"}')
EVERY_LINE_HINT = ('{"answer": "short answer listing every item, or null", '
                   '"quote": ["each exact line copied from the page"] or null}')

# Variant switches (see docs/sufficiency-check.md for which one won and why).
EVERY_LINE = False         # True: "copy every line the answer uses"; False: original "the exact line"
USE_POINTER_RULE = False   # one extra sentence in the judge prompt
CHECK_ANSWER = False       # second short yes/no call after a quote passes

ORIGINAL_ASK = ("If the page answers the question, even in different words, give the answer "
                "and copy the exact line from the page that supports it. ")
EVERY_LINE_ASK = ("If the page answers the question, even in different words, give the full "
                  "answer, including every item if there are several, and copy every line "
                  "from the page that the answer uses, exactly as written. ")

POINTER_RULE = ("A line that only says where the answer can be found (another site, a "
                "calendar, an email to come) is not an answer. ")

CHECK_SYSTEM = "You check whether an answer really answers a question."
CHECK_MAX_TOKENS = 5

REPHRASE_SYSTEM = "You write short web search queries."


def fmt_today(today: date | str | None) -> str:
    if today is None:
        today = date.today()
    if isinstance(today, date):
        return today.strftime("%A, %d %B %Y").replace(" 0", " ")
    return str(today)


def judge_hint() -> str:
    return EVERY_LINE_HINT if EVERY_LINE else ORIGINAL_HINT


def judge_prompt(question: str, page: str, url: str | None, today: str) -> str:
    # complete_json appends "Reply with only a JSON object ... matching this shape: JUDGE_HINT".
    return (f"Today is {today}.\n\nQUESTION: {question}\n\n"
            f"PAGE ({url or 'unknown url'}):\n{page}\n\n"
            + (EVERY_LINE_ASK if EVERY_LINE else ORIGINAL_ASK)
            + (POINTER_RULE if USE_POINTER_RULE else "")
            + "If the page does not answer it, set answer and quote to null.")


def check_prompt(question: str, answer: str, quote: str, today: str) -> str:
    # A/B, not yes/no: with yes/no the model answered the question itself
    # ("Is the gym open?" -> "no") instead of judging the answer.
    return (f"Today is {today}.\n\nQUESTION: {question}\nPROPOSED ANSWER: {answer}\n"
            f"QUOTED FROM THE PAGE: {quote}\n\n"
            "Which is true?\n"
            "A) The proposed answer gives the information the question asks for.\n"
            "B) It only says where the information can be found (another site, a calendar, "
            "a document, an email to come), or it is about a different course, term, date "
            "or thing.\n"
            "Reply with only the letter A or B.")


def rephrase_prompt(question: str, tried: list[str], today: str) -> str:
    tried_s = "\n".join(f"- {q}" for q in tried) or "- (none)"
    return (f"Today is {today}. We are searching the web to answer: {question}\n\n"
            f"Queries already tried (do not repeat them or reword them trivially):\n{tried_s}\n\n"
            "Write one new search query that is more likely to find a page with the answer. "
            "Reply with only the query.")
