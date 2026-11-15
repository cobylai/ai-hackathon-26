"""Run every playbook's examples: python -m reason.playbook_check [--today YYYY-MM-DD] [--only NAME] [--live-calendar]

Each example in playbooks/<route>.md ("## Examples": question | route | answer contains)
goes through answer() (one Session per file, so follow-ups lean on the rows above) on a temporary copy of $FLUX_BANK_DIR, with the network blocked
(localhost stays open for Bonsai), so examples that save or forget things never change
the real bank. Prints RIGHT/WRONG per example and the total. Exit code 1 if any is wrong.
Keep rule (playbooks/RULES.md): keep a playbook or prompt change only if this still passes.

The calendar is the six-event demo calendar the examples were written against (see
FIXTURE), not the Mac's live one, so a tester who has run Q10 and left its "Band practice
Thursday" event in place still sees the expected answers; --live-calendar reads FLUX_CALENDAR.
"""
from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path

from . import playbook

# docs/PARTNER-TESTING-FULL.md's "Flux demo" calendar before Q10: nothing on Thursday at 7pm,
# Lab on Wednesday afternoon (the compose and suggest examples depend on both).
FIXTURE = [
    ("Study group", datetime(2026, 11, 16, 16, 0), datetime(2026, 11, 16, 17, 0), "Uris Library"),
    ("Dinner with Sam", datetime(2026, 11, 17, 18, 0), datetime(2026, 11, 17, 19, 30), "Collegetown"),
    ("Lab", datetime(2026, 11, 18, 13, 30), datetime(2026, 11, 18, 15, 30), "Olin Hall 255"),
    ("Office hours", datetime(2026, 11, 19, 11, 0), datetime(2026, 11, 19, 12, 0), "Phillips 213"),
    ("Dentist", datetime(2026, 11, 20, 10, 0), datetime(2026, 11, 20, 11, 0), "Ithaca Dental"),
    ("Gym", datetime(2026, 11, 20, 17, 0), datetime(2026, 11, 20, 18, 0), "Helen Newman"),
]


def fixture_events(day_start: date, day_end: date) -> list[dict]:
    """The fixed demo days, in the shape applecal.events() returns."""
    return [{"title": title, "start": start, "end": end, "location": where, "all_day": False}
            for title, start, end, where in FIXTURE if day_start <= start.date() <= day_end]


def run(today: date, only: str | None = None, events_fn=fixture_events) -> tuple[int, int]:
    # The check is a demo scenario: the demo bank and the fixed demo calendar fixture below, whose
    # examples name the "Flux demo" calendar. Live is the default when this Mac has no ~/.flux/mode
    # yet (bank/mode.py), and live names no calendar until one is chosen, so read as demo unless a
    # mode was chosen on purpose (FLUX_MODE or the file).
    from bank import mode, store
    if not os.environ.get("FLUX_MODE") and not mode.mode_file().exists():
        os.environ["FLUX_MODE"] = "demo"
    from .answer import answer
    from .session import Session

    print("calendar: " + ("this Mac's FLUX_CALENDAR" if events_fn is None
                          else "fixed demo fixture (six events, nothing Thursday 7pm)"), flush=True)
    src = store.bank_dir()
    with tempfile.TemporaryDirectory(prefix="flux-check-") as tmp:
        root = Path(tmp) / "bank"
        if src.exists():
            shutil.copytree(src, root)
        else:
            root.mkdir()
        right = total = 0
        for name in playbook.names():
            if only and name != only:
                continue
            session = Session()  # each file's examples are one conversation (follow-ups)
            for ex in playbook.load(name).examples:
                total += 1
                try:
                    a = answer(ex["question"], today=today, root=root, session=session,
                               _events=events_fn)
                    route, text = a.route, a.text
                    if a.suggestions:  # playbooks/suggest.md: the Suggested lines count too
                        text += "\nSuggested: " + " | ".join(x["line"] for x in a.suggestions)
                except Exception as e:
                    route, text = "error", f"{type(e).__name__}: {e}"
                missing = [c for c in ex["contains"] if c.lower() not in text.lower()]
                ok = route == ex["route"] and not missing
                right += ok
                print(f"[{'RIGHT' if ok else 'WRONG'}] {name:<9} {ex['question']}")
                if not ok:
                    print(f"   want: route {ex['route']}" + (f", contains {ex['contains']}" if ex["contains"] else ""))
                print(f"   got ({route}): {text.replace(chr(10), ' | ')[:240]}", flush=True)
        print(f"\n{right}/{total} right (bank copied from {src})")
        return right, total


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m reason.playbook_check")
    ap.add_argument("--today", type=date.fromisoformat, default=date(2026, 11, 15),
                    help="the day the examples are written for (default 2026-11-15, the demo bank's day)")
    ap.add_argument("--only", help="run one playbook's examples (for example: due)")
    ap.add_argument("--live-calendar", action="store_true",
                    help="read this Mac's FLUX_CALENDAR instead of the fixed demo fixture")
    args = ap.parse_args(argv)
    from .live_check import block_network
    block_network()
    right, total = run(args.today, args.only, None if args.live_calendar else fixture_events)
    return 0 if right == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
