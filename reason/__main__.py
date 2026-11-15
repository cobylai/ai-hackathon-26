"""Typed chat loop: python -m reason [--today YYYY-MM-DD]

Reads a question, prints the answer, its source and [route, seconds], repeats.
An empty line or Ctrl-D quits. A thin wrapper: voice input calls answer() the same way.
"""
from __future__ import annotations

import argparse

from . import answer


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m reason")
    ap.add_argument("--today", help="pretend today is this date (YYYY-MM-DD)")
    args = ap.parse_args(argv)
    while True:
        try:
            q = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not q:
            return 0
        try:
            a = answer(q, today=args.today)
        except Exception as e:  # keep the loop alive; show what broke
            print(f"muse> Error: {type(e).__name__}: {e}\n")
            continue
        print(f"muse> {a.text}\n[{a.route}, {a.seconds:.1f}s]\n")


if __name__ == "__main__":
    raise SystemExit(main())
