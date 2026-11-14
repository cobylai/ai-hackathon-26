"""B9: bot-wall rate, live.

Visits 15 common sites with plain Playwright, then with the patchright fork,
and records status, HTTP code and time per site. It never tries to solve or
bypass a challenge; a wall is just recorded as BLOCKED.

Run both engines:
    uv run --with patchright python scripts/live_check.py

Run one engine:
    uv run python scripts/live_check.py --engine playwright
    uv run --with patchright python scripts/live_check.py --engine patchright

patchright needs its own browser build: ``uv run --with patchright patchright install chromium``.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.browser.state import classify  # noqa: E402

SITES = (
    ("reddit", "https://www.reddit.com/"),
    ("wikipedia", "https://en.wikipedia.org/wiki/Main_Page"),
    ("bbc-news", "https://www.bbc.com/news"),
    ("weather.com", "https://weather.com/"),
    ("stackoverflow", "https://stackoverflow.com/"),
    ("github", "https://github.com/"),
    ("youtube", "https://www.youtube.com/"),
    ("amazon", "https://www.amazon.com/"),
    ("google", "https://www.google.com/"),
    ("x", "https://x.com/"),
    ("linkedin", "https://www.linkedin.com/"),
    ("instagram", "https://www.instagram.com/"),
    ("hacker-news", "https://news.ycombinator.com/"),
    ("nytimes", "https://www.nytimes.com/"),
    ("craigslist", "https://www.craigslist.org/"),
)

TIMEOUT_MS = 20000
SETTLE_S = 1.2


def _driver(engine: str):
    if engine == "patchright":
        from patchright.sync_api import sync_playwright
    else:
        from playwright.sync_api import sync_playwright
    return sync_playwright


def run_engine(engine: str) -> list[dict]:
    sync_playwright = _driver(engine)
    results: list[dict] = []
    profile = tempfile.mkdtemp(prefix=f"live-{engine}-")
    launched = time.perf_counter()
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            profile,
            headless=True,
            channel="chromium",
        )
        launch_s = time.perf_counter() - launched
        print(f"# {engine}: launched in {launch_s:.1f}s", flush=True)
        try:
            for name, url in SITES:
                page = context.new_page()
                status = None
                started = time.perf_counter()
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
                    elapsed = time.perf_counter() - started
                    status = response.status if response is not None else None
                    time.sleep(SETTLE_S)
                    word = classify(page, status=status)
                    title = " ".join(page.title().split())[:60]
                except Exception as exc:  # navigation failure, timeout
                    elapsed = time.perf_counter() - started
                    word = "ERR"
                    title = " ".join(str(exc).split())[:60]
                finally:
                    page.close()
                row = {
                    "engine": engine,
                    "site": name,
                    "url": url,
                    "status": word,
                    "http": status,
                    "seconds": round(elapsed, 2),
                    "title": title,
                }
                results.append(row)
                print(
                    f"{name:<14} {word:<8} http={str(status):<4} {elapsed:5.2f}s  {title}",
                    flush=True,
                )
        finally:
            context.close()
    shutil.rmtree(profile, ignore_errors=True)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bot-wall rate check")
    parser.add_argument("--engine", choices=("playwright", "patchright", "both"), default="both")
    args = parser.parse_args(argv)

    engines = ["playwright", "patchright"] if args.engine == "both" else [args.engine]
    results: dict[str, dict[str, dict]] = {}
    for engine in engines:
        try:
            rows = run_engine(engine)
        except ImportError:
            print(f"# {engine} is not installed; run with uv --with patchright", file=sys.stderr)
            return 2
        results[engine] = {row["site"]: row for row in rows}

    print("\n| site | playwright | http | s | patchright | http | s |")
    print("|---|---|---|---|---|---|---|")
    for name, _ in SITES:
        cells = [name]
        for engine in engines:
            row = results.get(engine, {}).get(name)
            if row is None:
                cells.extend(["n/a", "", ""])
            else:
                cells.extend([row["status"], str(row["http"] or ""), f"{row['seconds']:.2f}"])
        print("| " + " | ".join(cells) + " |")

    for engine in engines:
        rows = results.get(engine, {})
        blocked = sum(1 for row in rows.values() if row["status"] == "BLOCKED")
        errors = sum(1 for row in rows.values() if row["status"] == "ERR")
        times = [row["seconds"] for row in rows.values()]
        print(
            f"\n{engine}: {blocked}/{len(rows)} BLOCKED, {errors} ERR, "
            f"median {sorted(times)[len(times) // 2]:.2f}s"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
