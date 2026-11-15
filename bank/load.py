"""Load a folder of saved text files into the store (needs the Bonsai server).

    python -m bank.load saved_mail/ --kind email
    python -m bank.load saved_pages/ --kind page

Each .txt/.eml/.md file is one item; its path is the source. Already-ingested
files are skipped, so it is safe to re-run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ingest, store


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m bank.load")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--kind", choices=("email", "page"), default="email")
    args = ap.parse_args(argv)
    files = sorted(p for p in args.folder.rglob("*")
                   if p.is_file() and p.suffix.lower() in (".txt", ".eml", ".md"))
    if not files:
        print(f"No .txt/.eml/.md files in {args.folder}", file=sys.stderr)
        return 1
    added = dup = failed = 0
    for p in files:
        try:
            r = ingest(p.read_text(errors="replace"), source=str(p), kind=args.kind)
        except Exception as e:  # keep going; report at the end
            failed += 1
            print(f"FAIL {p}: {e}", file=sys.stderr)
            continue
        if r["status"] == "added":
            added += 1
        else:
            dup += 1
        print(f"{r['status']:<9} {p} -> {r['path']}", file=sys.stderr)
    print(f"added {added}, duplicate {dup}, failed {failed}; bank at {store.bank_dir()}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
