"""Print the questions and dated lines from the last N days of mail.

Run: ``uv run python scripts/daily_digest.py --days 1 --limit 8``

Read-only and safe to run unattended: it opens threads, never drafts or sends.
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
    args = parser.parse_args(argv)

    output = digest.build(days=max(1, args.days), limit=max(1, args.limit))
    print(output)
    return 0 if output.startswith("OK") else 1


if __name__ == "__main__":
    sys.exit(main())
