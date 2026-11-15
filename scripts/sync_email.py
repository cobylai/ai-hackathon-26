"""Email -> bank sync: read the last N days of Gmail and file each message.

    FLUX_BANK_DIR=~/flux-bank uv run python scripts/sync_email.py 7
    (live mail is refused for a bank folder named *demo* or *test*; --allow-demo overrides)
    uv run python scripts/sync_email.py --fixture tests/pages/gmail_thread.html

Uses only the partner's read paths: harness.email.search (email_search rows,
each with a thread_id), read.open_thread and read.read_messages. It never
opens compose, never drafts, never sends. Each message's sender, date and body
go to bank.ingest, which calls local Bonsai. --fixture reads a saved Gmail
thread page instead of live mail.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from bank.mailsync import (check_live_bank, file_thread, iso_date, split_sender)  # noqa: E402,F401


def sync(days: int, ingest, *, root: Path | None = None, allow_demo: bool = False) -> list[dict]:
    """Live Gmail -> ingest. Refuses a demo/test bank (root, else $FLUX_BANK_DIR) unless allow_demo."""
    if not allow_demo:
        from bank import bank_dir
        check_live_bank(Path(root) if root else bank_dir())
    from harness.browser.session import get_session
    from harness.email import read, search
    from harness.email.status import signed_in

    page = get_session().start().page
    if not signed_in(page):
        raise SystemExit("Not signed in to Gmail: run  uv run python -m harness login "
                         "https://mail.google.com  once, then retry.")
    print(search.search(days=days).splitlines()[0])
    results = []
    for row in search.last_rows():
        if not row.thread_id or not read.open_thread(page, row.thread_id):
            print(f"  skip row {row.n}: thread did not open")
            continue
        rs = file_thread(row.thread_id, row.subject, read.read_messages(page), ingest)
        for r in rs:
            print(f"  {r['status']}: {r['path']}")
        results += rs
    return results


def sync_fixture(path: str, ingest) -> list[dict]:
    from playwright.sync_api import sync_playwright

    from harness.email import read

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(Path(path).resolve().as_uri())
        title = page.title().split(" - ")[0]
        msgs = read.read_messages(page)
        browser.close()
    rs = file_thread("fixture-" + Path(path).stem, title, msgs, ingest)
    for r in rs:
        print(f"  {r['status']}: {r['path']}")
    return rs


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("days", nargs="?", type=int, default=14)
    ap.add_argument("--limit", type=int, default=200, help="most threads to look at (default 200)")
    ap.add_argument("--budget", type=float, default=None, help="stop after this many seconds; run again to resume")
    ap.add_argument("--every", type=float, default=None, metavar="MIN",
                    help="background refresh: repeat every MIN minutes until Ctrl-C")
    ap.add_argument("--fixture", help="saved Gmail thread HTML instead of live mail")
    ap.add_argument("--allow-demo", action="store_true",
                    help="allow live mail into a bank folder named *demo* or *test*")
    a = ap.parse_args(argv)
    from bank import bank_dir, ingest, mailsync

    if a.fixture:
        root = bank_dir()
        print(f"bank: {root}")
        t0 = time.monotonic()
        rs = sync_fixture(a.fixture, ingest)
        print(f"{len(rs)} message(s), {sum(r['status'] == 'added' for r in rs)} added, {time.monotonic() - t0:.1f}s")
        return
    root = mailsync.live_bank_dir()  # refuses a path inside the repo
    if not a.allow_demo:
        check_live_bank(root)  # before the browser starts
    print(f"bank: {root}")
    while True:
        try:
            res = mailsync.run(a.days, a.limit, a.budget, root=root, progress=print, allow_demo=a.allow_demo)
            print(res.line())
        except mailsync.Locked as e:
            print(f"skipped: {e}")
        if not a.every:
            return
        try:
            time.sleep(a.every * 60)
        except KeyboardInterrupt:
            return


if __name__ == "__main__":
    main()
