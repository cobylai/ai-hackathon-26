"""Print the questions and dated lines from the last N days of mail.

Run: ``uv run python scripts/daily_digest.py --days 1 --limit 8``
Add ``--output digest.txt`` to also write it somewhere (for a scheduler).

Read-only and safe to run unattended: it opens threads, never drafts or sends.
If another process holds the browser profile it prints one ``ERR`` line instead
of a traceback, and exits 2 so a wrapper can retry later.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.email import digest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=1, help="how far back to look")
    parser.add_argument("--limit", type=int, default=8, help="how many threads to open")
    parser.add_argument("--output", default="", help="also write the digest to this file")
    args = parser.parse_args(argv)

    try:
        output = digest.build(days=max(1, args.days), limit=max(1, args.limit))
    except Exception as exc:  # a locked profile, a crashed browser, a timeout
        message = " ".join(str(exc).split())[:120]
        print(f"ERR gmail | digest failed | {message}")
        return 2

    print(output)
    if args.output:
        try:
            Path(args.output).expanduser().write_text(output + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"ERR could not write {args.output} | {exc}")
            return 2
    return 0 if output.startswith("OK") else 1


if __name__ == "__main__":
    sys.exit(main())
