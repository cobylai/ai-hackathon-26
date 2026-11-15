"""Typed check of the video's run sheet (docs/demo-runsheet.md) against the reset state.

    uv run python scripts/demo/demo_check.py --today YYYY-MM-DD

Run scripts/demo/demo_reset.py first. Each beat's line goes through reason.answer in one
conversation (follow-ups work), on a temporary copy of the demo bank, with the network
blocked for this process (localhost stays open for Bonsai). It reads this Mac's "Flux demo"
calendar, like the app. Each answer (plus its Suggested lines) must contain every
expected string. "set me up" is checked up to the preview: no yes is sent, nothing is
opened; instead every page it lists must be a file:// page that exists on this Mac.
Prints RIGHT/WRONG per line and the total; exit code 1 if any is wrong.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# (beat, line said, route, must contain). Keep in step with docs/demo-runsheet.md.
STEPS = [
    ("0:27 catch me up", "catch me up", "catchup",
     ["Calendar", "Lab Report 3", "Felix", "You're free Thursday, Nov 19 at 3pm. Draft a yes to Felix?"]),
    ("1:05 due this week", "What's due this week?", "due",
     ["Due this week", "Lab Report 3", "CHEM 1583 Kitchen Chemistry", "$48.20"]),
    ("1:05 and tomorrow", "and tomorrow?", "due", ["Due Mon Nov 16"]),
    ("1:05 set me up", "set me up for the lab report", "act",
     ["To set you up for the lab report, I'll open:", 'the page "Lab Report 3"', "Jonah Pike"]),
    ("1:25 remember", "Remember that my lab is Tuesdays at 2", "remember",
     ["I'll remember: my lab is Tuesdays at 2."]),
    ("1:25 about me", "what do you know about me?", "about_me",
     ["my lab is Tuesdays at 2", "Source: your notes"]),
]
# Data the brief asks for that no beat says out loud (checked the same way, separate chat).
EXTRA = [
    ("data: Nina clash", "What did Nina Valdez ask me?", "person", ["You have CHEM 1583 Lab then"]),
    ("data: newsletter", "What did Campus Rec ask me?", "person", ["Campus Rec"]),
]


def pages_ok(a, root: Path) -> list[str]:
    """Problems with the pages a set-me-up preview would open (file:// and present)."""
    from bank import store
    bad = []
    titles = re.findall(r'the page "([^"]+)"', a.text)
    by_subject = {e.get("subject"): e for e in store.all_entries(root)}
    for t in titles:
        src = (by_subject.get(t) or {}).get("source") or ""
        if not src.startswith("file://"):
            bad.append(f"{t}: source is not a file:// page ({src or 'none'})")
        elif not Path(src.removeprefix("file://")).exists():
            bad.append(f"{t}: {src} does not exist")
    return bad if titles else ["no page listed"]


def run(today: date) -> tuple[int, int]:
    from bank import store
    from reason.answer import answer
    from reason.live_check import block_network
    from reason.session import Session

    block_network()
    src = store.bank_dir()
    right = total = 0
    with tempfile.TemporaryDirectory(prefix="flux-demo-check-") as tmp:
        root = Path(tmp) / "bank"
        shutil.copytree(src, root)
        for steps in (STEPS, EXTRA):
            session = Session()
            for beat, q, route, contains in steps:
                total += 1
                try:
                    a = answer(q, today=today, root=root, session=session)
                    text = a.text + ("\nSuggested: " + " | ".join(x["line"] for x in a.suggestions)
                                     if a.suggestions else "")
                    problems = [f"missing {c!r}" for c in contains if c.lower() not in text.lower()]
                    if a.route != route:
                        problems.insert(0, f"route {a.route}, want {route}")
                    if "set me up" in q:
                        problems += pages_ok(a, root)
                except Exception as e:  # report, keep going
                    text, problems = f"{type(e).__name__}: {e}", ["error"]
                ok = not problems
                right += ok
                print(f"[{'RIGHT' if ok else 'WRONG'}] {beat:<22} {q}")
                if not ok:
                    print("   " + "; ".join(problems))
                print("   got: " + text.replace("\n", " | ")[:400], flush=True)
    return right, total


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts/demo/demo_check.py")
    ap.add_argument("--today", type=date.fromisoformat, required=True)
    a = ap.parse_args(argv)
    right, total = run(a.today)
    print(f"\n{right}/{total} right")
    return 0 if right == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
