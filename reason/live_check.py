"""Live check for answer(): needs the Bonsai server; uses $MUSE_BANK_DIR (set it outside the repo).

    MUSE_BANK_DIR=/tmp/x uv run python -m reason.live_check load
    MUSE_BANK_DIR=/tmp/x uv run python -m reason.live_check offline --today 2026-11-14 "q1" "q2" ...
    MUSE_BANK_DIR=/tmp/x uv run python -m reason.live_check online --today 2026-11-14 "web question"

load     ingests the bank eval fixtures (bank/eval/fixtures/*.json), then prints every deadline.
offline  blocks socket.connect for everything but localhost in this process, then asks each
         question. Bonsai is on localhost, so it still answers; the web does not.
online   asks each question normally, then says whether its web page landed in the bank.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "bank" / "eval" / "fixtures"
LOCAL = {"127.0.0.1", "::1", "localhost"}


def block_network() -> None:
    real = socket.socket.connect

    def connect(self, addr):
        host = addr[0] if isinstance(addr, tuple) else addr
        if self.family == socket.AF_UNIX or host in LOCAL:
            return real(self, addr)
        raise OSError(f"network blocked for this process ({host})")

    socket.socket.connect = connect


def show(a) -> None:
    print(f"route={a.route}  seconds={a.seconds}")
    print(a.text)
    print("sources:", a.sources)
    print("-" * 60, flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m reason.live_check")
    ap.add_argument("mode", choices=("load", "offline", "online"))
    ap.add_argument("questions", nargs="*")
    ap.add_argument("--today")
    args = ap.parse_args(argv)

    import bank
    from bank import store
    print("bank:", store.bank_dir(), file=sys.stderr)
    if args.mode == "load":
        for p in sorted(FIXTURES.glob("*.json")):
            fx = json.loads(p.read_text())
            r = bank.ingest(fx["text"], source=fx["source"], kind=fx["kind"])
            print(f"{r['status']:<9} {p.name}", file=sys.stderr)
        for e in sorted(store.all_entries(), key=lambda e: e.get("sent_date") or ""):
            dl = [f"{d['date']} {d.get('time') or ''} ({d['phrase']})" for d in e.get("deadlines") or []]
            print(f"{e['sent_date']} | {e.get('sender_name')} | {e.get('subject')} | {dl}")
        return 0

    if args.mode == "offline":
        block_network()
    from reason import answer
    for q in args.questions:
        print("Q:", q)
        a = answer(q, today=args.today)
        show(a)
        if args.mode == "online" and a.route == "web":
            hit = [e for e in store.all_entries() if e.get("source") == a.sources[0]]
            print("page in bank:", hit[0]["path"] if hit else "NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
