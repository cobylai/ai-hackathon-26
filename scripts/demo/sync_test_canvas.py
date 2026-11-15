"""File generated Canvas pages into a test or demo bank, then check them. No network.

    FLUX_BANK_DIR=data/bank-canvas-test uv run python scripts/demo/sync_test_canvas.py [data/test-canvas]

Each course's assignments.html (from make_test_canvas.py) is read with
canvas.read, each assignment page is opened for its description, and the
assignment is filed with bank.ingest(kind="canvas"):
  sender_name = course, subject = title, source = the page's file:// link,
  sent_date = truth.json's "today", deadlines = [the due date and time from the page].
Bonsai (localhost) writes the summary and ask; the due date never goes through it.
Then each entry's course, title, due date/time and link are checked against
truth.json. It refuses any bank folder without "test" or "demo" in its name.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def entry_text(a: dict, phrase: str | None) -> str:
    return "\n".join(x for x in (a["title"], f"Course: {a['course']}", phrase and phrase + ".",
                                 "", a["description"]) if x is not None).strip() + "\n"


def file_assignment(a: dict, today: str, ingest) -> dict:
    from canvas.read import due_phrase
    phrase = due_phrase(a["due_date"], a["due_time"])
    dl = [{"phrase": phrase, "date": a["due_date"], "time": a["due_time"]}] if phrase else []
    return ingest(entry_text(a, phrase), source=a["url"], kind="canvas", sender_name=a["course"],
                  subject=a["title"], sent_date=today, deadlines=dl)


def main(argv=None) -> int:
    from bank import bank_dir, ingest
    from canvas.read import course_folders, read_assignment, read_assignment_list

    folder = Path((argv or sys.argv[1:] or [str(ROOT / "data" / "test-canvas")])[0]).resolve()
    truth = json.loads((folder / "truth.json").read_text())
    want = {t["url"]: t for t in truth["assignments"]}
    root = bank_dir()
    if not ("test" in root.name or "demo" in root.name):
        raise SystemExit(f"FLUX_BANK_DIR is {root}; point it at a test or demo bank")
    print(f"bank: {root}")
    t0 = time.monotonic()
    n = added = match = 0
    for course in course_folders(folder):
        for row in read_assignment_list(course / "assignments.html"):
            a = read_assignment(Path(row["url"].removeprefix("file://")))
            r = file_assignment(a, truth["today"], ingest)
            e, t = r["entry"], want.get(a["url"], {})
            d = (e.get("deadlines") or [{}])[0]
            got = (e.get("sender_name"), e.get("subject"), d.get("date"), d.get("time"), e.get("source"))
            exp = (t.get("course"), t.get("title"), t.get("due_date"), t.get("due_time"), t.get("url"))
            ok = got == exp
            n += 1
            added += r["status"] == "added"
            match += ok
            print(f"  {course.name}/{Path(a['url']).name} {r['status']:<9} "
                  f"{'MATCH' if ok else 'DIFF ' + repr(got) + ' want ' + repr(exp)}")
    print(f"{n} filed ({added} new), {match}/{len(want)} match course/title/due date/time/link, "
          f"{time.monotonic() - t0:.1f}s")
    return 0 if match == len(want) else 1


if __name__ == "__main__":
    raise SystemExit(main())
