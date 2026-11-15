"""Live sufficiency check on the loaded Bonsai size.

    python -m sufficiency.eval.run_check --runs 3      # server must be up

Judges the 8 original fixtures (llm/eval/fixtures/p*.json, read in place) and the
8 new ones (sufficiency/eval/fixtures/s*.json). Writes results/<size>_run<N>.json.
A fixture expected "enough" also needs its evidence to contain one expect_evidence text.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from llm import client, config
from sufficiency import judge

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
TODAY = "Friday, 13 November 2026"   # same date as llm/eval/run_check.py

# Evidence texts for the unchanged originals (any one must appear in the quote).
ORIG_EVIDENCE = {"p01_weather_yes": ["rain likely"],
                 "p02_course_due_yes": ["problem set 5", "lab 12"],
                 "p06_hours_yes": ["closed"],
                 "p08_recipe_yes": ["350", "55 to 65"]}


def load():
    orig = [json.loads(p.read_text()) for p in sorted((ROOT / "llm/eval/fixtures").glob("p*.json"))]
    for f in orig:
        f.setdefault("expect_evidence", ORIG_EVIDENCE.get(f["id"]))
    new = [json.loads(p.read_text()) for p in sorted((HERE / "fixtures").glob("s*.json"))]
    return orig, new


def score(f, v) -> bool:
    if f["expected"] == "not enough":
        return not v.enough
    if not v.enough:
        return False
    if f.get("expect_answer"):   # every item must be named in the answer
        ans = (v.answer or "").lower()
        return all(e.lower() in ans for e in f["expect_answer"])
    ev = (v.evidence or "").lower()
    return any(e.lower() in ev for e in f.get("expect_evidence") or [""])


def run_once(n: int, orig, new) -> dict:
    rows = []
    for group, fs in (("orig", orig), ("new", new)):
        for f in fs:
            v = judge(f["question"], f["page"], url=f["url"], today=TODAY)
            ok = score(f, v)
            rows.append(dict(id=f["id"], group=group, correct=ok, expected=f["expected"],
                             enough=v.enough, reason=v.reason, answer=v.answer,
                             evidence=v.evidence, chunk=v.chunk, chunks=v.chunks,
                             seconds=round(v.seconds, 2)))
            print(f"  run{n} {f['id']:<22} {'OK  ' if ok else 'MISS'} {v.reason:<18} "
                  f"{v.seconds:5.2f}s  {(v.answer or '')[:50]}", file=sys.stderr)
    per_call = [r["seconds"] / max(1, r["chunk"] + 1) for r in rows]
    summary = dict(orig=sum(r["correct"] for r in rows if r["group"] == "orig"),
                   new=sum(r["correct"] for r in rows if r["group"] == "new"
                           and r["id"] <= "s08~"),
                   s09=[r["correct"] for r in rows if r["id"].startswith("s09")],
                   median_s_per_judge=round(statistics.median(r["seconds"] for r in rows), 2),
                   median_s_per_model_call=round(statistics.median(per_call), 2))
    return {"run": n, "size": config.BONSAI_SIZE, "model": client.loaded_model(),
            "summary": summary, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    orig, new = load()
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    for n in range(1, a.runs + 1):
        res = run_once(n, orig, new)
        (out / f"{config.BONSAI_SIZE}_run{n}.json").write_text(json.dumps(res, indent=2) + "\n")
        print(f"run{n}: {json.dumps(res['summary'])}")


if __name__ == "__main__":
    main()
