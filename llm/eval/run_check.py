"""4B-vs-9B model check. Runs against whatever size the server has loaded.

    BONSAI_SIZE=4B python -m llm.eval.run_check   # server must be serving 4B

Writes llm/eval/results/<size>.json and prints a summary table.
"""
from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

from llm import client, config

HERE = Path(__file__).parent
FIX = HERE / "fixtures"
OUT = HERE / "results"

TODAY = "Friday, 13 November 2026"

EXTRACT_SYSTEM = "You extract facts from emails. You never invent information."
EXTRACT_HINT = ('{"sender": "sender email address", "date": "date the email was sent, YYYY-MM-DD", '
                '"ask": "what the sender asks the reader to do, or null if nothing", '
                '"deadlines": ["each deadline the reader must meet, as written; empty list if none"]}')

SUFF_SYSTEM = ("You decide whether a web page contains enough information to answer a "
               "question. Reply with exactly one of: enough, not enough.")


def extraction_prompt(email: str) -> str:
    return f"Extract the fields from this email.\n\nEMAIL:\n{email}"


def sufficiency_prompt(q: str, url: str, page: str) -> str:
    return (f"Today is {TODAY}.\n\nQUESTION: {q}\n\nPAGE ({url}):\n{page}\n\n"
            "Does the page alone contain enough information to answer the question? "
            "Reply with exactly: enough, or: not enough.")


def _lc(x) -> str:
    return json.dumps(x).lower() if not isinstance(x, str) else x.lower()


def score_extraction(got, exp) -> dict:
    if not isinstance(got, dict):
        return {"sender": False, "date": False, "ask": False, "deadlines": False}
    sender = exp["sender"].lower() in _lc(got.get("sender", ""))
    date = str(got.get("date", "")).strip()[:10] == exp["date"]
    ask = got.get("ask")
    ask_s = "" if ask in (None, "", [], "null", "none", "None") else _lc(ask)
    if exp["ask_keywords"]:
        ask_ok = any(any(k in ask_s for k in grp) for grp in exp["ask_keywords"])
    else:
        ask_ok = ask_s == "" or ask_s.strip(". ") in ("none", "nothing", "null", "n/a")
    dl = got.get("deadlines") or []
    dl_s = _lc(dl)
    if exp["deadline_keywords"]:
        dl_ok = all(any(k in dl_s for k in grp) for grp in exp["deadline_keywords"])
    else:
        dl_ok = (dl in ([], None, "", "none")) or dl_s in ('[]', '["none"]', '[null]')
    return {"sender": sender, "date": date, "ask": ask_ok, "deadlines": dl_ok}


def parse_suff(text: str):
    t = text.strip().lower().strip(".\"'` \n")
    if t.startswith("not enough") or "not enough" in t:
        return "not enough"
    if t.startswith("enough") or t == "enough":
        return "enough"
    return None


def server_mem_mb() -> float | None:
    """Physical footprint of the mlx_vlm.server process (includes Metal buffers)."""
    try:
        pid = subprocess.run(["pgrep", "-f", "mlx_vlm.server"], capture_output=True,
                             text=True).stdout.split()[0]
        out = subprocess.run(["footprint", "-p", pid], capture_output=True, text=True).stdout
        m = re.search(r"Footprint:\s*([\d.]+)\s*(KB|MB|GB)", out)
        if m:
            return float(m.group(1)) * {"KB": 1 / 1024, "MB": 1, "GB": 1024}[m.group(2)]
        rss = subprocess.run(["ps", "-o", "rss=", "-p", pid], capture_output=True, text=True)
        return int(rss.stdout.strip()) / 1024
    except Exception:
        return None


def main() -> None:
    size = config.BONSAI_SIZE
    model = client.loaded_model()
    print(f"Model check: {size} ({model})", file=sys.stderr)
    fixtures = [json.loads(p.read_text()) for p in sorted(FIX.glob("*.json"))]
    rows, mem = [], []
    for f in fixtures:
        t0 = time.monotonic()
        if f["task"] == "extraction":
            stats = {}
            try:
                got = client.complete_json(extraction_prompt(f["email"]), system=EXTRACT_SYSTEM,
                                           json_schema_hint=EXTRACT_HINT, max_tokens=400,
                                           _stats=stats)
                err = None
            except client.BonsaiError as e:
                got, err = None, str(e)
            dt = time.monotonic() - t0
            fields = score_extraction(got, f["expected"])
            row = dict(id=f["id"], task="extraction", correct=all(fields.values()),
                       fields=fields, first_try_valid=stats.get("first_try_valid", False),
                       calls=stats.get("calls"), seconds=dt / max(1, stats.get("calls") or 1),
                       got=got, error=err)
        else:
            r = client.chat([{"role": "system", "content": SUFF_SYSTEM},
                             {"role": "user", "content": sufficiency_prompt(
                                 f["question"], f["url"], f["page"])}], max_tokens=10)
            ans = parse_suff(r.text)
            row = dict(id=f["id"], task="sufficiency", correct=ans == f["expected"],
                       expected=f["expected"], got=r.text, valid=ans is not None,
                       seconds=r.seconds, prompt_tokens=r.prompt_tokens,
                       estimated_prompt_tokens=r.estimated_prompt_tokens)
        m = server_mem_mb()
        if m:
            mem.append(m)
        rows.append(row)
        print(f"  {row['id']:<26} {'OK ' if row['correct'] else 'MISS'} {row['seconds']:.2f}s",
              file=sys.stderr)

    summary = {}
    for task in ("extraction", "sufficiency"):
        rs = [r for r in rows if r["task"] == task]
        s = dict(n=len(rs), correct=sum(r["correct"] for r in rs),
                 median_s=round(statistics.median(r["seconds"] for r in rs), 2))
        if task == "extraction":
            s["json_valid_first_try"] = sum(r["first_try_valid"] for r in rs)
            for fld in ("sender", "date", "ask", "deadlines"):
                s[f"field_{fld}"] = sum(r["fields"][fld] for r in rs)
        else:
            s["valid_label"] = sum(r["valid"] for r in rs)
        summary[task] = s
    summary["peak_server_mem_mb"] = round(max(mem)) if mem else None
    OUT.mkdir(exist_ok=True)
    (OUT / f"{size}.json").write_text(json.dumps(
        {"size": size, "model": model, "summary": summary, "rows": rows}, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
