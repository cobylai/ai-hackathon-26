"""Run every playbook's examples: python -m reason.playbook_check [--today YYYY-MM-DD] [--only NAME]

Each example in playbooks/<route>.md ("## Examples": question | route | answer contains)
goes through answer() (one Session per file, so follow-ups lean on the rows above) on a temporary copy of $FLUX_BANK_DIR, with the network blocked
(localhost stays open for Bonsai), so examples that save or forget things never change
the real bank. Prints RIGHT/WRONG per example and the total. Exit code 1 if any is wrong.
Keep rule (playbooks/RULES.md): keep a playbook or prompt change only if this still passes.
"""
from __future__ import annotations

import argparse
import shutil
import tempfile
from datetime import date
from pathlib import Path

from . import playbook


def run(today: date, only: str | None = None) -> tuple[int, int]:
    from bank import store
    from .answer import answer
    from .session import Session

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
                    a = answer(ex["question"], today=today, root=root, session=session)
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
    args = ap.parse_args(argv)
    from .live_check import block_network
    block_network()
    right, total = run(args.today, args.only)
    return 0 if right == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
