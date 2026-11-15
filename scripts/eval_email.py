"""E9: time email requests and count what each step returns to the model.

One flow:

    uv run python scripts/eval_email.py --sender me --days 7 --draft-to you@example.edu

The five-request table from the notes (read-only, writes nothing):

    uv run python scripts/eval_email.py --suite --sender me --text "ECE 4760" --days 7

Uses the live signed-in Gmail profile. The draft step only runs when
``--draft-to`` is given, and nothing is ever sent.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.email import tools  # noqa: E402


def timed(name: str, run, **kwargs) -> dict:
    started = time.perf_counter()
    output = run(**kwargs)
    seconds = time.perf_counter() - started
    first = output.splitlines()[0][:90] if output else ""
    return {
        "step": name,
        "seconds": seconds,
        "chars": len(output),
        "status": output.split(" ", 1)[0] if output else "ERR",
        "first": first,
    }


def one_flow(args: argparse.Namespace) -> int:
    steps = [
        timed(
            "email_search",
            tools.email_search,
            sender=args.sender,
            text=args.text,
            days=args.days,
        ),
        timed("email_read", tools.email_read, n=1),
        timed("email_asks", tools.email_asks, sender=args.sender, days=args.days),
    ]
    if args.draft_to:
        steps.append(
            timed(
                "email_draft",
                tools.email_draft,
                to=args.draft_to,
                subject="[harness test] eval run",
                body="Draft created by the E9 timing run; safe to delete.",
            )
        )

    print("| step | seconds | chars returned | status | first line |")
    print("|---|---|---|---|---|")
    for step in steps:
        print(
            f"| {step['step']} | {step['seconds']:.1f} | {step['chars']} | "
            f"{step['status']} | {step['first']} |"
        )
    total_seconds = sum(step["seconds"] for step in steps)
    total_chars = sum(step["chars"] for step in steps)
    print(f"\ntotal {total_seconds:.1f} s, {total_chars} characters returned")

    failed = [step["step"] for step in steps if step["status"] != "OK"]
    if failed:
        print(f"failed steps: {', '.join(failed)}")
    return 1 if failed else 0


def suite(args: argparse.Namespace) -> int:
    """The five read-only requests from docs/plan/notes-email-eval.md."""
    rows: list[tuple[str, str, float, int, str]] = []
    print("| # | request | steps | total s | chars | status |")
    print("|---|---|---|---|---|---|")

    def record(label: str, note: str, *results: dict) -> None:
        seconds = sum(result["seconds"] for result in results)
        chars = sum(result["chars"] for result in results)
        status = results[-1]["status"]
        rows.append((label, note, seconds, chars, status))
        print(
            f"| {len(rows)} | {label} | {note} | {seconds:.1f} | {chars} | {status} |",
            flush=True,
        )

    query_bits = f"newer_than:{args.days}d" if args.days else "all mail"
    search = timed("email_search", tools.email_search, sender=args.sender, days=args.days)
    record(f"sender search `from:{args.sender}` {query_bits}", f"email_search {search['seconds']:.1f}s", search)

    text = timed("email_search", tools.email_search, text=args.text, days=args.days)
    record(f'text search `"{args.text}"` {query_bits}', f"email_search {text['seconds']:.1f}s", text)

    recent = timed("email_search", tools.email_search, days=1)
    record("date-bounded search `newer_than:1d`", f"email_search {recent['seconds']:.1f}s", recent)

    found = timed("email_search", tools.email_search, text=args.text, days=args.days)
    read = timed("email_read", tools.email_read, n=1)
    record(
        f'read `{args.text}` thread 1',
        f"search {found['seconds']:.1f}s + read {read['seconds']:.1f}s",
        found,
        read,
    )

    asks = timed("email_asks", tools.email_asks, sender=args.sender, days=args.days)
    record(f"asks `from:{args.sender}` {query_bits}", f"email_asks {asks['seconds']:.1f}s", asks)

    total_seconds = sum(row[2] for row in rows)
    total_chars = sum(row[3] for row in rows)
    slowest = max(row[2] for row in rows)
    print(f"\ntotal {total_seconds:.1f} s, {total_chars} chars, slowest request {slowest:.1f} s")

    failed = [row[0] for row in rows if row[4] != "OK"]
    if failed:
        print(f"failed requests: {', '.join(failed)}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sender", default="", help="Gmail from: field")
    parser.add_argument("--text", default="", help="words to search for")
    parser.add_argument("--days", type=int, default=0, help="newer_than:N days")
    parser.add_argument(
        "--draft-to",
        default="",
        help="save one test draft to this address (omit to skip the draft step)",
    )
    parser.add_argument(
        "--suite",
        action="store_true",
        help="run the five-request table; needs --sender and --text, writes nothing",
    )
    args = parser.parse_args(argv)

    if args.suite:
        if not args.sender or not args.text:
            parser.error("--suite needs --sender and --text")
        return suite(args)
    return one_flow(args)


if __name__ == "__main__":
    sys.exit(main())
