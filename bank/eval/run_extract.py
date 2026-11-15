"""Ingest every fixture into a fresh temp store and score the entries.

    python -m bank.eval.run_extract --runs 3      # server must be serving 4B

An entry is right when sender_address, sent_date, ask, the set of resolved
deadline dates, folder and course all match. ask_keywords None = not scored
(pages). Writes bank/eval/results/<size>_run<N>.json.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

import bank
from bank import extract
from llm import client, config

HERE = Path(__file__).parent
FIX = HERE / "fixtures"
OUT = HERE / "results"
FIELDS = ("sender_address", "sent_date", "ask", "deadlines", "folder", "course", "summary")


def score(e: dict, exp: dict) -> dict:
    ask = (e.get("ask") or "").lower()
    if exp["ask_keywords"] is None:
        ask_ok = True
    elif exp["ask_keywords"]:
        ask_ok = any(any(k in ask for k in grp) for grp in exp["ask_keywords"])
    else:
        ask_ok = e.get("ask") is None
    got_dates = sorted({d["date"] for d in e.get("deadlines") or [] if d.get("date")})
    unresolved = [d for d in e.get("deadlines") or [] if not d.get("date")]
    return {
        "sender_address": e.get("sender_address") == exp["sender_address"],
        "sent_date": e.get("sent_date") == exp["sent_date"],
        "ask": ask_ok,
        "deadlines": got_dates == sorted(exp["deadline_dates"]) and not unresolved,
        "folder": e.get("folder") == exp["folder"],
        "course": e.get("course") == exp["course"],
        "summary": bool((e.get("body") or "").strip()),
    }


def raw_score(raws: list[dict], exp: dict) -> dict:
    """What the model alone got for the fields code overrides or resolves."""
    r = raws[0] if raws else {}
    addr = str(r.get("sender_address") or "").strip().lower() or None
    return {"sender_address": addr == exp["sender_address"]}


def run_once(fixtures: list[dict], n: int) -> dict:
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for f in fixtures:
            t0 = time.monotonic()
            today = date.fromisoformat(f.get("ingest_date", "2026-11-14"))
            try:
                r = bank.ingest(f["text"], f["source"], f["kind"], today=today, root=root)
                e, raws, err = r["entry"], r["raw"], None
            except client.BonsaiError as ex:
                e, raws, err = {}, [], str(ex)
            dt = time.monotonic() - t0
            fs = score(e, f["expected"])
            rows.append(dict(id=f["id"], set="new" if f["id"].startswith("n") else "original",
                             correct=all(fs.values()), fields=fs,
                             model_only=raw_score(raws, f["expected"]), seconds=round(dt, 2),
                             entry={k: e.get(k) for k in ("sender_address", "sent_date", "ask",
                                                          "deadlines", "folder", "course", "body")},
                             raw=raws, error=err))
            print(f"  run{n} {f['id']:<24} {'OK  ' if rows[-1]['correct'] else 'MISS'} "
                  f"{dt:.2f}s {"" if rows[-1]["correct"] else [k for k, v in fs.items() if not v]} {"" if rows[-1]["correct"] else repr(e.get("ask"))[:120]}",
                  file=sys.stderr)
        due_rows = bank.due("2026-11-16", "2026-11-20", root=root)
    summ = {}
    for s in ("original", "new"):
        rs = [r for r in rows if r["set"] == s]
        summ[s] = {"n": len(rs), "correct": sum(r["correct"] for r in rs),
                   **{f"field_{k}": sum(r["fields"][k] for r in rs) for k in FIELDS},
                   "model_only_sender_address": sum(r["model_only"]["sender_address"] for r in rs)}
    summ["median_s"] = round(statistics.median(r["seconds"] for r in rows), 2)
    summ["due_2026_11_16_to_20"] = [f"{d['date']} {d['time'] or ''} {d['phrase']!r} "
                                    f"[{d['entry']['id']}]" for d in due_rows]
    return {"run": n, "size": config.BONSAI_SIZE, "model": client.loaded_model(),
            "prompt": extract.PROMPT, "system": extract.SYSTEM, "hint": extract.HINT,
            "summary": summ, "rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", default="", help="comma list of fixture id prefixes")
    args = ap.parse_args()
    fixtures = [json.loads(p.read_text()) for p in sorted(FIX.glob("*.json"))]
    if args.only:
        pre = tuple(args.only.split(","))
        fixtures = [f for f in fixtures if f["id"].startswith(pre)]
    print(f"Context-store check: {config.BONSAI_SIZE} ({client.loaded_model()})", file=sys.stderr)
    OUT.mkdir(exist_ok=True)
    for n in range(1, args.runs + 1):
        res = run_once(fixtures, n)
        if not args.only:
            (OUT / f"{config.BONSAI_SIZE}_run{n}.json").write_text(json.dumps(res, indent=2) + "\n")
        print(json.dumps({"run": n, **res["summary"]}, indent=2))


if __name__ == "__main__":
    main()
