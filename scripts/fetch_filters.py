"""Download EasyList and EasyPrivacy into ~/.harness/filters/.

Run once after install: ``uv run python scripts/fetch_filters.py``.
The browser still works without it; the ad filter engine is just empty.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import config  # noqa: E402

FILTERS = {
    "easylist.txt": "https://easylist.to/easylist/easylist.txt",
    "easyprivacy.txt": "https://easylist.to/easylist/easyprivacy.txt",
}


def main(directory: Path | None = None) -> int:
    folder = directory if directory is not None else config.FILTER_DIR
    folder.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for name, url in FILTERS.items():
            target = folder / name
            try:
                response = client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                print(f"skip {name}: {exc}", file=sys.stderr)
                continue
            target.write_text(response.text, encoding="utf-8")
            print(f"{name}: {len(response.text):,} chars -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
