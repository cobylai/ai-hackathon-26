"""Typed check of the video's 12 lines (docs/demo-runsheet.md) against the reset state.

    uv run python scripts/demo/demo_check.py --today YYYY-MM-DD [--save answers.json]

Run scripts/demo/demo_reset.py first. Preflight: the status line would read "Demo data" and
"Offline" with the network blocked, the bank count, Thursday 3pm free on the "Flux demo"
calendar, and nothing in the bank about a chemistry exam. Then every line goes through
reason.answer in one conversation (follow-ups work), on a temporary copy of the demo bank,
network blocked for this process (localhost stays open for Bonsai), this Mac's "Flux demo"
calendar. Each answer (plus its Suggested lines) must contain every expected string.
Line 6 also takes Felix's suggestion and builds the draft the window shows (To, Subject,
body). Line 8 says "yes" with the openers stubbed: nothing opens, the check records what
would open and that the page is a file:// page on this Mac.
--save writes every answer's full text, so three resets can be compared word for word.
Exit code 1 if anything is wrong.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# (line, said, route, must contain). Keep in step with docs/demo-runsheet.md.
LINES = [
    ("1", "What is Flux?", "about", ["I'm Flux, a personal assistant that lives on your Mac.",
                                     "Nothing goes to the cloud, and I work with Wi-Fi off."]),
    ("2", "Do you need the internet?", None,
     ["No. I read your mail and coursework", "You're offline right now, and I still work."]),
    ("3", "Catch me up.", "catchup", ["Today on your calendar", "Due today through", "Asks in mail"]),
    ("4", "What's due this week?", "due", ["Due this week", "CHEM 1583 Kitchen Chemistry"]),
    ("5", "And tomorrow?", "due", ["Due Mon Nov 16"]),
    ("6", "What did Felix ask me?", "person",
     ["Felix Ambrose", "You're free Thursday, Nov 19 at 3pm. Draft a yes to Felix?"]),
    ("7", "Will you send that?", None, ["No. I write the draft and you send it. I never send anything myself."]),
    ("8", "Set me up for the lab report.", "act",
     ["To set you up for the lab report, I'll open:", 'the page "Lab Report 3"', "Jonah Pike"]),
    ("9", "When is my chemistry exam?", None,
     ["I have nothing saved about a chemistry exam, and I won't guess."]),
    ("10", "Remember that my lab is Tuesdays at 2.", "remember", ["I'll remember: my lab is Tuesdays at 2."]),
    ("11", "What do you know about me?", "about_me", ["my lab is Tuesdays at 2"]),
    ("12", "What model are you running?", None, ["Bonsai 2, the 4B model, running on this Mac."]),
]
DRAFT = {"to": "fambrose@example.edu", "subject": "Re: Free Thursday at 3?", "body": "Thursday, Nov 19 at 3pm"}


def preflight(today: date, root: Path) -> list[tuple[str, bool, str]]:
    from bank import mode, store
    from reason.answer import online
    out = [("status reads Demo data", mode.label() == "Demo data", mode.label()),
           ("status reads Offline (network blocked)", not online(), "offline" if not online() else "online")]
    n = len(store.all_entries(root))
    home = Path.home()
    want = sum(len(json.loads((home / f).read_text())[k]) for f, k in
               (("flux-demo-video-threads/truth.json", "mail"), ("flux-demo-canvas/truth.json", "assignments")))
    out.append(("bank count", n == want, f"{n} items, staged {want}"))
    import applecal
    thu = today + timedelta(days=2)
    thu += timedelta(days=(3 - thu.weekday()) % 7)
    lo, hi = datetime.combine(thu, time(15)), datetime.combine(thu, time(16))
    clash = [e["title"] for e in applecal.events(thu, thu)
             if not e.get("all_day") and e["start"] < hi and e["end"] > lo]
    out.append((f"{thu:%a %b %d} 3pm free", not clash, ", ".join(clash) or "free"))
    exam = [e.get("subject") for e in store.all_entries(root)
            if re.search(r"\bexam", " ".join(str(e.get(k) or "") for k in ("subject", "body", "ask")), re.I)
            and re.search(r"chem", " ".join(str(e.get(k) or "") for k in ("subject", "body", "ask", "sender_name", "course")), re.I)]
    out.append(("nothing about a chemistry exam", not exam, "; ".join(exam) or "none"))
    return out


def run(today: date) -> tuple[int, int, dict]:
    from bank import store
    from reason import act, compose
    from reason.answer import answer
    from reason.live_check import block_network
    from reason.session import Session

    block_network()
    right = total = 0
    saved: dict = {}
    with tempfile.TemporaryDirectory(prefix="flux-demo-check-") as tmp:
        root = Path(tmp) / "bank"
        shutil.copytree(store.bank_dir(), root)
        for name, ok, got in preflight(today, root):
            total += 1
            right += ok
            print(f"[{'RIGHT' if ok else 'WRONG'}] pre  {name}: {got}")
        opened: list[str] = []
        act.open_page = lambda url: opened.append(url) or f"Opened {url}."
        act.open_email = lambda e: opened.append(f"mail:{e.get('subject')}") or f"Opened the email \"{e.get('subject')}\"."
        session = Session()
        for n, q, route, contains in LINES:
            total += 1
            problems: list[str] = []
            try:
                a = answer(q, today=today, root=root, session=session)
                text = a.text + ("\nSuggested: " + " | ".join(x["line"] for x in a.suggestions)
                                 if a.suggestions else "")
                problems = [f"missing {c!r}" for c in contains if c.lower() not in text.lower()]
                if route and a.route != route:
                    problems.insert(0, f"route {a.route}, want {route}")
                if n == "6":
                    s = next((x for x in a.suggestions or [] if x.get("kind") == "meeting"), None)
                    if not s:
                        problems.append("no meeting suggestion")
                    else:
                        d = compose.reply_draft(s["entry"])
                        text += f"\nDraft: To {d.get('to')} | Subject {d.get('subject')} | {d.get('body')}"
                        problems += [f"draft {k} lacks {v!r}" for k, v in DRAFT.items() if v not in str(d.get(k))]
                if n == "8":
                    y = answer("yes", today=today, root=root, session=session)
                    text += "\nYes: " + y.text
                    pages = [u for u in opened if u.startswith("file://")]
                    if not pages or not all(Path(u.removeprefix("file://")).exists() for u in pages):
                        problems.append(f"page not opened as an existing file:// page ({opened})")
                    if not any("Lab Report 3" in u or u.endswith("50025.html") for u in pages):
                        problems.append("Lab Report 3 page not opened")
                    if len([u for u in opened if u.startswith("mail:")]) != 2:
                        problems.append(f"want 2 emails opened, got {opened}")
            except Exception as e:
                text, problems = f"{type(e).__name__}: {e}", ["error"]
            ok = not problems
            right += ok
            saved[n] = text
            print(f"[{'RIGHT' if ok else 'WRONG'}] {n:>3}  {q}")
            if not ok:
                print("     " + "; ".join(problems))
            print("     got: " + text.replace("\n", " | ")[:600], flush=True)
    return right, total, saved


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts/demo/demo_check.py")
    ap.add_argument("--today", type=date.fromisoformat, required=True)
    ap.add_argument("--save", type=Path, help="write every answer's full text here (JSON)")
    a = ap.parse_args(argv)
    right, total, saved = run(a.today)
    if a.save:
        a.save.write_text(json.dumps(saved, indent=1))
    print(f"\n{right}/{total} right")
    return 0 if right == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
