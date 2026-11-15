"""One-time move from the old name to Flux, on this Mac.

    uv run python scripts/migrate_to_flux.py              # dry run: shows what it would do
    uv run python scripts/migrate_to_flux.py --apply      # back up, then move folders and fix links
    uv run python scripts/migrate_to_flux.py --calendar   # rename the "Muse demo" calendar and Reminders list

--apply:
  1. Backs up every ~/muse-* folder into ~/flux-migration-backup-<time>.tgz.
  2. Renames ~/muse-<x> to ~/flux-<x> (banks, -chats, demo threads, canvas pages, .bak copies).
     Stops if a ~/flux-<x> already exists, or if a Flux window server is running (stop it first).
  3. In the moved text files, rewrites links and paths to the old folders (file:///…/muse-…,
     ~/muse-…) and "Muse demo" to the new names.
  4. Rebuilds the bank index in every moved folder that has one.
--calendar: AppleScript renames the calendar and the Reminders list "Muse demo" to "Flux demo"
  (macOS asks once to let this terminal control Calendar and Reminders).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HOME = Path.home()
OLD, NEW = "muse-", "flux-"
TEXT = {".md", ".json", ".jsonl", ".html", ".htm", ".txt", ".csv"}


def pairs() -> list[tuple[Path, Path]]:
    return [(p, HOME / (NEW + p.name[len(OLD):])) for p in sorted(HOME.glob(OLD + "*")) if p.is_dir()]


def fix_text(root: Path) -> int:
    """Rewrite paths to the old folders inside one moved folder. Returns files changed."""
    reps = [("Muse demo", "Flux demo")]
    n = 0
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in TEXT:
            continue
        try:
            t = f.read_text()
        except UnicodeDecodeError:
            continue
        u = t
        u = re.sub(r"(?<=/)muse-", NEW, u)   # any path segment: file:///…/muse-x, ~/muse-x
        for a, b in reps:
            u = u.replace(a, b)
        if u != t:
            f.write_text(u)
            n += 1
    return n


def server_running() -> bool:
    r = subprocess.run(["lsof", "-nP", "-iTCP:8765", "-sTCP:LISTEN"], capture_output=True, text=True)
    return "LISTEN" in r.stdout


def apply(todo: list[tuple[Path, Path]]) -> None:
    clash = [n for _, n in todo if n.exists()]
    if clash:
        sys.exit("Already there, not overwriting: " + ", ".join(map(str, clash)))
    if server_running():
        sys.exit("A window server is listening on :8765 and may be using these folders. Quit Flux (or stop it), then run again.")
    backup = HOME / f"flux-migration-backup-{time.strftime('%Y%m%d-%H%M%S')}.tgz"
    with tarfile.open(backup, "w:gz") as tar:
        for old, _ in todo:
            tar.add(old, arcname=old.name)
    print(f"backup: {backup}")
    for old, new in todo:
        old.rename(new)
        print(f"moved: {old} -> {new}  ({fix_text(new)} file(s) relinked)")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import os
    for _, new in todo:
        if (new / "index.md").exists():
            os.environ["FLUX_BANK_DIR"] = str(new)
            from bank import rebuild_index
            print(f"index: {rebuild_index()}")


def calendar() -> None:
    for app, kind in (("Calendar", "calendar"), ("Reminders", "list")):
        script = (f'tell application "{app}"\n'
                  f'  if exists {kind} "Flux demo" then return "already Flux demo"\n'
                  f'  if not (exists {kind} "Muse demo") then return "no Muse demo"\n'
                  f'  set name of {kind} "Muse demo" to "Flux demo"\n'
                  f'  return "renamed"\nend tell')
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
        print(f"{app}: {(r.stdout or r.stderr).strip()}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="back up, move and relink (else a dry run)")
    ap.add_argument("--calendar", action="store_true", help='rename the "Muse demo" calendar and Reminders list')
    a = ap.parse_args()
    todo = pairs()
    if a.calendar:
        calendar()
    if not todo:
        print("No ~/muse-* folders left.")
        return
    for old, new in todo:
        print(f"{'move' if a.apply else 'would move'}: {old} -> {new}")
    if a.apply:
        apply(todo)
    elif not a.calendar:
        print("Dry run. Add --apply to do it.")


if __name__ == "__main__":
    main()
