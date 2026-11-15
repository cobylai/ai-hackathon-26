"""Email -> bank sync: read the last N days of Gmail and file each message.

    MUSE_BANK_DIR=~/muse-bank uv run python scripts/sync_email.py 7
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


def split_sender(sender: str) -> tuple[str | None, str | None]:
    """'Name <addr>' -> (name, addr); a bare address or name fills one side."""
    m = re.match(r"\s*(.*?)\s*<([^>]+)>\s*$", sender or "")
    if m:
        return (m.group(1) or None), m.group(2)
    s = (sender or "").strip()
    return (None, s) if "@" in s else (s or None, None)


def iso_date(raw: str) -> str | None:
    """Gmail's title date ('Thu, Nov 12, 2026, 4:30 PM') -> '2026-11-12'."""
    s = " ".join((raw or "").replace(" ", " ").split())
    for fmt in ("%a, %b %d, %Y, %I:%M %p", "%b %d, %Y, %I:%M %p", "%a, %b %d, %Y %I:%M %p"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def file_thread(thread_id: str, subject: str | None, messages, ingest) -> list[dict]:
    """messages = read_messages() output, newest first: [(sender, date, body)]."""
    out = []
    for i, (sender, raw_date, body) in enumerate(reversed(messages)):  # oldest first
        if not (body or "").strip():
            continue
        name, addr = split_sender(sender)
        r = ingest(body, source=f"gmail:{thread_id}#{i}", kind="email",
                   sender_name=name, sender_address=addr,
                   sent_date=iso_date(raw_date), subject=subject or None)
        out.append(r)
    return out


def sync(days: int, ingest) -> list[dict]:
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
    ap.add_argument("days", nargs="?", type=int, default=7)
    ap.add_argument("--fixture", help="saved Gmail thread HTML instead of live mail")
    a = ap.parse_args(argv)
    from bank import bank_dir, ingest

    print(f"bank: {bank_dir()}")
    t0 = time.monotonic()
    rs = sync_fixture(a.fixture, ingest) if a.fixture else sync(a.days, ingest)
    added = sum(r["status"] == "added" for r in rs)
    print(f"{len(rs)} message(s), {added} added, {time.monotonic() - t0:.1f}s")


if __name__ == "__main__":
    main()
