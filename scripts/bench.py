"""B10: cold start, warm goto+read, Chromium memory, install size.

Run: ``uv run python scripts/bench.py``. Uses temp profiles and the local
fixture pages, so it works offline (blocking uses ~/.harness/filters if present).
"""

from __future__ import annotations

import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.browser import tools  # noqa: E402
from harness.browser.session import Session  # noqa: E402

PAGES = ("hello.html", "article.html", "form.html", "ads.html", "captcha.html")
RUNS = 3


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(ROOT / "tests" / "pages")))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def cold_start() -> list[float]:
    times = []
    for _ in range(RUNS):
        profile = tempfile.mkdtemp(prefix="bench-cold-")
        session = Session(profile)
        started = time.perf_counter()
        session.start()
        times.append(time.perf_counter() - started)
        session.stop()
        shutil.rmtree(profile, ignore_errors=True)
    return times


def warm(site: str) -> dict[str, list[float]]:
    profile = tempfile.mkdtemp(prefix="bench-warm-")
    session = Session(profile)
    session.start()
    tools.get_session = lambda: session
    try:
        tools.goto(f"{site}/hello.html")  # warm-up: engine build + first navigate
        tools.read(1)
        results: dict[str, list[float]] = {}
        for _ in range(RUNS):
            for page in PAGES:
                started = time.perf_counter()
                out = tools.goto(f"{site}/{page}")
                tools.read(1)
                elapsed = time.perf_counter() - started
                assert out.split()[0] in {"OK", "BLOCKED", "LOGIN", "ERR"}, out[:80]
                results.setdefault(page, []).append(elapsed)
        return results
    finally:
        session.stop()
        shutil.rmtree(profile, ignore_errors=True)


def _ps() -> list[tuple[int, int, int, str]]:
    raw = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,rss=,command="], capture_output=True, text=True, check=True
    ).stdout
    rows = []
    for line in raw.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4:
            rows.append((int(parts[0]), int(parts[1]), int(parts[2]), parts[3]))
    return rows


def tree_memory(profile: str) -> tuple[int, int]:
    rows = _ps()
    roots = [pid for pid, _, _, cmd in rows if profile in cmd and "--user-data-dir" in cmd]
    if not roots:
        return 0, 0
    children: dict[int, list[int]] = {}
    rss = {}
    for pid, ppid, kb, _ in rows:
        children.setdefault(ppid, []).append(pid)
        rss[pid] = kb
    seen, stack = set(), list(roots)
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        stack.extend(children.get(pid, []))
    return sum(rss.get(pid, 0) for pid in seen), len(seen)


def measure_memory(site: str) -> tuple[int, int]:
    profile = tempfile.mkdtemp(prefix="bench-mem-")
    session = Session(profile)
    session.start()
    try:
        session.page.goto(f"{site}/article.html")
        time.sleep(2)  # let renderers settle
        return tree_memory(profile)
    finally:
        session.stop()
        shutil.rmtree(profile, ignore_errors=True)


def size_mb(path: Path) -> float:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def main() -> int:
    server, site = serve()
    try:
        cold = cold_start()
        warm_times = warm(site)
        rss_kb, processes = measure_memory(site)
    finally:
        server.shutdown()

    playwright_cache = Path.home() / "Library" / "Caches" / "ms-playwright"
    chromium = sorted(playwright_cache.glob("chromium-*"))
    sizes = {
        "repo .venv": ROOT / ".venv",
        "Chromium build": chromium[-1] if chromium else playwright_cache,
        "playwright cache (all)": playwright_cache,
        "~/.harness (profile+filters+ubol)": Path.home() / ".harness",
    }

    print(f"cold start (s, n={RUNS}): " + ", ".join(f"{t:.2f}" for t in cold)
          + f" | median {statistics.median(cold):.2f}")
    print(f"warm goto+read (s, n={RUNS} each):")
    everything = []
    for page in PAGES:
        values = warm_times[page]
        everything.extend(values)
        print(f"  {page:<14} " + ", ".join(f"{t:.2f}" for t in values)
              + f" | median {statistics.median(values):.2f}")
    print(f"  overall median {statistics.median(everything):.2f}, "
          f"max {max(everything):.2f}")
    print(f"memory: {processes} processes, {rss_kb / 1024:.0f} MB RSS (article page)")
    for label, path in sizes.items():
        print(f"disk: {label}: {size_mb(path):.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
