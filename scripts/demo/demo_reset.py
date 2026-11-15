"""Put the Mac into the video's starting state (brief DEMO). Sample data only.

    uv run python scripts/demo/demo_reset.py --today YYYY-MM-DD [--full]

Every take starts identical:
  - the demo bank ($FLUX_BANK_DIR, default ~/flux-demo-bank): your notes (me/) and person
    pages (people/) cleared, so the remember beat is real;
  - the "Flux demo" calendar wiped and rewritten with the demo week (scripts/demo/demo_calendar.py),
    and the "Flux demo" Reminders list emptied;
  - saved chats (<bank>-chats) deleted.
With --full (or when the bank was built for another day, or doesn't exist) the bank is also
rebuilt in <bank>.building, then swapped in (the old one kept as <bank>.bak-<time>): brief M's 23 emails plus the 7 optional demo
emails (make_test_threads --extra), then the mock Canvas (4 courses, 25 assignments). That
needs Bonsai on localhost and takes a few minutes; it works offline.

It refuses a bank whose folder name lacks "demo" or that is ~/flux-bank, and any calendar
or Reminders list not named "Flux demo". Last, it turns demo mode on (scripts/flux-mode
demo, or ~/.flux/mode = "demo"); relaunch Flux after it.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HOME = Path.home()
THREADS = HOME / "flux-demo-threads"           # template.html (real, never committed) + pages
CANVAS_TEMPLATES = HOME / "flux-demo-canvas-templates"
CANVAS = HOME / "flux-demo-canvas"
MARK = ".demo-day"


def _sh(*args: str, env: dict | None = None) -> None:
    print("$", " ".join(args), flush=True)
    subprocess.run(["uv", "run", "python", *args], cwd=ROOT, check=True, env=env)


def check_bank(bank: Path) -> None:
    if "demo" not in bank.name or bank.resolve() == (HOME / "flux-bank").resolve():
        raise SystemExit(f"refusing: {bank} is not a demo bank (name must contain 'demo')")


def rebuild(bank: Path, day: date) -> None:
    """Build into <bank>.building, then swap: the live bank is never half-built."""
    tmp = bank.with_name(bank.name + ".building")
    if tmp.exists():
        shutil.rmtree(tmp)
    env = {**os.environ, "FLUX_BANK_DIR": str(tmp)}
    d = day.isoformat()
    _sh("scripts/demo/make_test_threads.py", "99", "--extra", "--today", d,
        "--template", str(THREADS / "template.html"), "--out", str(THREADS))
    _sh("scripts/demo/sync_test_threads.py", str(THREADS), env=env)
    _sh("scripts/demo/make_test_canvas.py", "--today", d, "--templates", str(CANVAS_TEMPLATES), "--out", str(CANVAS))
    _sh("scripts/demo/sync_test_canvas.py", str(CANVAS), env=env)
    (tmp / MARK).write_text(d + "\n")
    if bank.exists():
        bak = bank.with_name(f"{bank.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        bank.rename(bak)
        print(f"backed up {bank} -> {bak}")
    tmp.rename(bank)


def clear_state(bank: Path) -> None:
    for sub in ("me", "people"):
        p = bank / sub
        if p.exists():
            shutil.rmtree(p)
    chats = bank.with_name(bank.name + "-chats")
    if chats.exists():
        shutil.rmtree(chats)
    from bank import rebuild_index
    rebuild_index(bank)


def set_demo_mode() -> str:
    """Demo mode on (worker 20's switch): scripts/flux-mode demo, else ~/.flux/mode = demo."""
    fm = ROOT / "scripts" / "flux-mode"
    if fm.exists():
        subprocess.run([str(fm), "demo"], cwd=ROOT, check=True)
    else:
        (HOME / ".flux").mkdir(exist_ok=True)
        (HOME / ".flux" / "mode").write_text("demo\n")
    return "demo mode on (relaunch Flux)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts/demo/demo_reset.py")
    ap.add_argument("--today", type=date.fromisoformat, required=True, help="the recording day")
    ap.add_argument("--full", action="store_true", help="also back up and rebuild the bank")
    a = ap.parse_args(argv)
    bank = Path(os.environ.get("FLUX_BANK_DIR") or HOME / "flux-demo-bank").expanduser()
    check_bank(bank)
    os.environ["FLUX_BANK_DIR"] = str(bank)
    t0 = time.monotonic()
    built = (bank / MARK).read_text().strip() if (bank / MARK).exists() else None
    if a.full or built != a.today.isoformat():
        rebuild(bank, a.today)
    clear_state(bank)
    sys.path.insert(0, str(ROOT / "scripts" / "demo"))
    import demo_calendar
    n = demo_calendar.reset(a.today)
    print(set_demo_mode())
    print(f"demo reset for {a.today}: bank {bank} (notes and chats cleared), "
          f'"Flux demo" calendar {n} events, reminders emptied, {time.monotonic() - t0:.0f}s')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
