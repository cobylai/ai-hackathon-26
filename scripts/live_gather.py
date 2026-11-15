"""Live check: typed questions through sufficiency.gather with the partner's browser.

    uv run python scripts/live_gather.py "question one" "question two" ...

search_fn is sufficiency.websearch.search (the partner's Google/DuckDuckGo
search, then Bing if that is walled); pages are opened with the partner's
harness.search.tools.open_page. Every model call goes to local Bonsai.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.browser.session import get_session  # noqa: E402
from harness.search import tools  # noqa: E402
from sufficiency import websearch  # noqa: E402
from sufficiency.gather import gather  # noqa: E402


def main(questions: list[str]) -> None:
    for q in questions:
        t0 = time.monotonic()
        r = gather(q, websearch.search, tools.open_page, max_seconds=60)
        dt = time.monotonic() - t0
        print(f"\nQ: {q}\n  seconds: {dt:.1f}   search: {websearch.last_engine}")
        if r.found:
            print(f"  answer: {r.answer}\n  source: {r.source.url}\n  evidence: {r.evidence}")
        else:
            print(f"  not found: {r.message}")
        print(f"  queries: {r.queries}\n  opened: {r.opened}")
    get_session().stop()


if __name__ == "__main__":
    main(sys.argv[1:])
