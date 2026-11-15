"""Typed chat loop with push-to-talk: python -m reason [--today YYYY-MM-DD] [--no-voice]

Type a question and press Enter. Press Enter on an empty line to start talking, and
Enter again to stop; the words heard are shown and answered like a typed question.
Ctrl-D (or "quit") exits. If voice can't start, typing still works.
A thin wrapper: answer() does the work.
"""
from __future__ import annotations

import argparse

from . import answer
from .speech import start_voice


def ask(q: str, today) -> None:
    try:
        a = answer(q, today=today)
    except Exception as e:  # keep the loop alive; show what broke
        print(f"muse> Error: {type(e).__name__}: {e}\n")
        return
    print(f"muse> {a.text}\n[{a.route}, {a.seconds:.1f}s]\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m reason")
    ap.add_argument("--today", help="pretend today is this date (YYYY-MM-DD)")
    ap.add_argument("--no-voice", action="store_true", help="typing only")
    args = ap.parse_args(argv)

    voice, why = (None, "turned off") if args.no_voice else start_voice()
    if voice:
        print("Type a question, or press Enter on an empty line to talk (Enter again to stop).")
    else:
        print(f"Voice is unavailable ({why}). Type your questions.")
    try:
        while True:
            try:
                q = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if q.lower() in ("quit", "exit"):
                return 0
            if not q:
                if not voice:
                    continue
                try:
                    q = voice.listen(wait_for_stop=lambda: input("  (recording… Enter to stop) ")).strip()
                except Exception as e:
                    print(f"  voice error: {e}\n")
                    continue
                print(f"you (spoken)> {q}")
                if not q:
                    continue
            ask(q, args.today)
    finally:
        if voice:
            voice.close()


if __name__ == "__main__":
    raise SystemExit(main())
