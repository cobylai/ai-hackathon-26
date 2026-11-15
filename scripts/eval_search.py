"""S8: live evaluation of the research loop.

Runs every question in ``tests/eval/questions.jsonl`` through
``loop.research`` and records pass/fail, rounds, pages opened, blocked pages,
model input characters and seconds. Prints a markdown table for the notes file.

    LLM_BASE_URL=http://127.0.0.1:1234/v1 LLM_MODEL=qwen/qwen3.5-9b \\
    LLM_REASONING_EFFORT=none uv run python scripts/eval_search.py

This is a live test: it uses the real browser profile and the real web. Bot
walls are recorded as BLOCKED, never worked around.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness import llm  # noqa: E402
from harness.browser.session import get_session  # noqa: E402
from harness.search import engine, loop, tools  # noqa: E402

QUESTIONS = ROOT / "tests" / "eval" / "questions.jsonl"


class CountingAsk:
    """`llm.ask` plus a count of how many characters the model was fed."""

    def __init__(self) -> None:
        self.chars = 0
        self.calls = 0
        self.prompt_tokens = 0

    def __call__(self, prompt: str, choices=None, max_tokens: int = 64) -> str:
        self.calls += 1
        self.chars += len(llm.SYSTEM) + len(prompt)
        reply = llm.ask(prompt, choices=choices, max_tokens=max_tokens)
        self.prompt_tokens += llm.last_usage.get("prompt_tokens", 0)
        return reply


def is_pass(answer: str, expect: str, notes: int) -> bool:
    """A question passes only if the loop found notes and the text is in the answer.

    Without the notes check, the "no useful results for <question>" message would
    pass every question whose expected string appears in its own question.
    """
    return notes > 0 and expect.lower() in (answer or "").lower()


def load_questions(path: Path, limit: int | None = None) -> list[dict]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items[:limit] if limit else items


def run_one(item: dict) -> dict:
    ask = CountingAsk()
    statuses: Counter = Counter()
    engines: list[str] = []

    def search(query: str) -> list:
        results = engine.search(query)
        engines.append(engine.last_engine or "?")
        return results

    def open_page(url: str) -> tuple[str, str]:
        word, text = tools.open_page(url)
        statuses[word] += 1
        return word, text

    engine.reset()
    started = time.monotonic()
    outcome = loop.research(
        item["question"], ask=ask, search=search, open_page=open_page
    )
    seconds = time.monotonic() - started

    answer = " ".join(outcome.answer.split())
    passed = is_pass(answer, item["expect"], len(outcome.notes))
    return {
        "id": item["id"],
        "kind": item["kind"],
        "question": item["question"],
        "expect": item["expect"],
        "pass": passed,
        "rounds": outcome.rounds,
        "pages": outcome.pages,
        "engines": list(dict.fromkeys(engines)),
        "blocked": statuses.get("BLOCKED", 0),
        "errors": statuses.get("ERR", 0) + statuses.get("LOGIN", 0),
        "notes": len(outcome.notes),
        "model_calls": ask.calls,
        "chars": ask.chars,
        "prompt_tokens": ask.prompt_tokens,
        "seconds": round(seconds, 1),
        "answer": answer[:300],
    }


def markdown(rows: list[dict]) -> str:
    lines = [
        "| # | kind | pass | engine | rounds | pages | blocked | model calls | input chars | prompt tokens | seconds |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['kind']} | {'yes' if row['pass'] else 'NO'} | "
            f"{', '.join(row['engines'])} | {row['rounds']} | {row['pages']} | "
            f"{row['blocked']} | {row['model_calls']} | "
            f"{row['chars']} | {row['prompt_tokens']} | {row['seconds']} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live evaluation of web research")
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ids", default=None, help="comma-separated question ids")
    parser.add_argument("--json", type=Path, default=None, help="write raw rows here")
    parser.add_argument(
        "--pause-seconds", type=float, default=0.0, help="wait between questions (pacing)"
    )
    args = parser.parse_args(argv)

    items = load_questions(args.questions, args.limit)
    if args.ids:
        wanted = {part.strip() for part in args.ids.split(",") if part.strip()}
        items = [item for item in items if item["id"] in wanted]
    rows: list[dict] = []

    def dump() -> None:
        # Written after every question: a crashed browser must not lose the run.
        if args.json:
            args.json.write_text(json.dumps(rows, indent=1), encoding="utf-8")

    try:
        for index, item in enumerate(items):
            if index and args.pause_seconds:
                time.sleep(args.pause_seconds)
            try:
                row = run_one(item)
            except Exception as exc:  # dead browser, dead model, or a wall we cannot pass
                rows.append(
                    {
                        "id": item["id"],
                        "kind": item["kind"],
                        "question": item["question"],
                        "expect": item["expect"],
                        "pass": False,
                        "rounds": 0,
                        "pages": 0,
                        "engines": [],
                        "blocked": 0,
                        "errors": 1,
                        "notes": 0,
                        "model_calls": 0,
                        "chars": 0,
                        "prompt_tokens": 0,
                        "seconds": 0.0,
                        "answer": f"ERROR {type(exc).__name__}",
                        "error": True,
                    }
                )
                dump()
                print(f"{item['id']} ERROR {type(exc).__name__}", file=sys.stderr, flush=True)
                break
            rows.append(row)
            dump()
            print(
                f"{row['id']} {'pass' if row['pass'] else 'FAIL'} "
                f"rounds={row['rounds']} pages={row['pages']} blocked={row['blocked']} "
                f"chars={row['chars']} {row['seconds']}s :: {row['answer'][:110]}",
                file=sys.stderr,
                flush=True,
            )
    finally:
        get_session().stop()

    if not rows:
        print("no questions", file=sys.stderr)
        return 1

    passes = sum(1 for row in rows if row["pass"])
    scored = [row for row in rows if not row.get("error")]
    seconds = statistics.median(row["seconds"] for row in scored) if scored else 0.0
    chars = statistics.median(row["chars"] for row in scored) if scored else 0.0
    tokens = statistics.median(row["prompt_tokens"] for row in scored) if scored else 0.0
    blocked = sum(row["blocked"] for row in rows)
    print(markdown(rows))
    print()
    print(f"pass {passes}/{len(rows)}  median {seconds:.1f} s  median {chars:.0f} chars  "
          f"median {tokens:.0f} prompt tokens  blocked pages {blocked}")
    print(f"target 9/12, <20 s, <8000 chars: "
          f"{'met' if passes >= 9 and seconds < 20 and chars < 8000 else 'missed'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
