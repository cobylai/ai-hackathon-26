"""E9: time one email flow and count what each step returns to the model.

Run: ``uv run python scripts/eval_email.py --sender me --days 7 --draft-to you@example.edu``

Uses the live signed-in Gmail profile. The draft step is skipped unless
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
    args = parser.parse_args(argv)

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


if __name__ == "__main__":
    sys.exit(main())
