"""Sync generated thread pages into a test bank (brief N). Offline: no Gmail.

    FLUX_BANK_DIR=data/bank-test uv run python scripts/sync_test_threads.py [data/test-threads]

Each page from make_test_threads.py is opened as a local file in the partner's
hidden browser (his Session class, on a scratch profile under data/ so it never
competes with the signed-in Gmail profile; every non-file request is aborted), read with his
read.read_messages, and filed with the live sync's file_thread -> bank.ingest.
Then each bank entry's sender name, address, sent date and subject are checked
against truth.json.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _sync_email():
    spec = importlib.util.spec_from_file_location("sync_email", ROOT / "scripts" / "sync_email.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv=None) -> int:
    from bank import bank_dir, ingest
    from harness.browser.session import Session
    from harness.email import read

    folder = Path((argv or sys.argv[1:] or [str(ROOT / "data" / "test-threads")])[0])
    truth = {m["key"]: m for m in json.loads((folder / "truth.json").read_text())["mail"]}
    se = _sync_email()
    root = bank_dir()
    if (ROOT / "data" / "bank-test").resolve() != root.resolve() and not (
            "test" in root.name or "demo" in root.name):
        raise SystemExit(f"FLUX_BANK_DIR is {root}; point it at a test or demo bank")
    print(f"bank: {root}")

    session = Session(ROOT / "data" / "test-profile").start()
    page = session.page
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file:") else r.abort())
    t0 = time.monotonic()
    results, match = [], 0
    for key in sorted(truth):
        page.goto((folder / f"{key}.html").resolve().as_uri(), wait_until="load")
        subject = page.title().removesuffix(" - Gmail")
        msgs = read.read_messages(page)
        rs = se.file_thread(f"test-{key}", subject, msgs, ingest)
        t = truth[key]
        for r in rs:
            e = r["entry"]
            got = (e.get("sender_name"), e.get("sender_address"), e.get("sent_date"), e.get("subject"))
            want = (t["name"], t["address"], t["sent"], t["subject"])
            ok = got == want
            match += ok
            print(f"  {key} {r['status']:<9} {'MATCH' if ok else 'DIFF ' + repr(got) + ' want ' + repr(want)}")
        results += rs
    session.stop()
    print(f"{len(results)} filed, {match}/{len(truth)} match sender/address/date/subject, "
          f"{time.monotonic() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
