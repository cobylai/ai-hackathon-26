"""Save three Canvas pages from a visible sign-in, as templates for make_test_canvas.py.

    uv run python scripts/demo/save_canvas_pages.py https://<canvas host>/ [--out data/canvas-templates]
                                               [--course ID] [--assignment ID]

It opens a visible Chromium (Playwright, scratch profile data/canvas-profile),
waits up to 5 minutes for you to finish signing in (use a Duo push or code, not
Touch ID), then saves the rendered HTML of:
  dashboard.html    the dashboard (with its to-do list)
  assignments.html  one course's Assignments list
  assignment.html   one assignment page
The output holds real names and courses: keep it under data/ (gitignored).
make_test_canvas.py turns these into fake pages.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _settle(page, ms: int = 4000) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts/demo/save_canvas_pages.py")
    ap.add_argument("url")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "canvas-templates")
    ap.add_argument("--course", help="course id to use (default: first course with assignments)")
    ap.add_argument("--assignment", help="assignment id to use (default: first in the list)")
    a = ap.parse_args(argv)
    from urllib.parse import urlparse

    from playwright.sync_api import sync_playwright

    base = a.url.rstrip("/")
    host = urlparse(base).netloc
    a.out.mkdir(parents=True, exist_ok=True)
    pw = sync_playwright().start()
    ctx = pw.chromium.launch_persistent_context(str(ROOT / "data" / "canvas-profile"), headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        page.goto(base + "/", wait_until="domcontentloaded")
        print("sign in in the window; waiting up to 5 minutes")
        for _ in range(300):
            if urlparse(page.url).netloc == host and "login" not in page.url:
                break
            page.wait_for_timeout(1000)
        else:
            raise SystemExit(f"not signed in after 5 minutes (at {page.url})")
        _settle(page)
        (a.out / "dashboard.html").write_text(page.content(), encoding="utf-8")
        print("saved dashboard.html")

        courses = [a.course] if a.course else []
        if not courses:
            page.goto(base + "/courses", wait_until="domcontentloaded")
            _settle(page, 2000)
            hrefs = page.eval_on_selector_all("a[href*='/courses/']", "els => els.map(e => e.href)")
            courses = list(dict.fromkeys(m.group(1) for h in hrefs
                                         if (m := re.search(r"/courses/(\d+)/?$", h))))
        for cid in courses:
            page.goto(f"{base}/courses/{cid}/assignments", wait_until="domcontentloaded")
            _settle(page)
            hrefs = page.eval_on_selector_all("a[href*='/assignments/']", "els => els.map(e => e.href)")
            ids = list(dict.fromkeys(m.group(1) for h in hrefs
                                     if (m := re.search(rf"/courses/{cid}/assignments/(\d+)", h))))
            if not ids:
                continue
            (a.out / "assignments.html").write_text(page.content(), encoding="utf-8")
            print(f"saved assignments.html ({len(ids)} assignments)")
            aid = a.assignment or ids[0]
            page.goto(f"{base}/courses/{cid}/assignments/{aid}", wait_until="domcontentloaded")
            _settle(page)
            (a.out / "assignment.html").write_text(page.content(), encoding="utf-8")
            print("saved assignment.html")
            break
        else:
            raise SystemExit("no course with a visible assignment list")
    finally:
        ctx.close()
        pw.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
