"""Score routing on reason/tests/routing_eval.jsonl (make it with scripts/gen_routing_eval.py).

Each question runs alone, with the network treated as off, so nothing reaches the web: a question
that would have gone to the web comes back as route "offline". That is the number to drive to zero
for questions that are not web questions.

  FLUX_BANK_DIR=<copy of ~/flux-demo-bank> uv run python -m reason.route_eval [--show 30]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

EVAL = Path(__file__).parent / "tests" / "routing_eval.jsonl"
WEB_BOUND = {"offline", "web"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=30, help="how many misses to print")
    ap.add_argument("--today", default=str(date.today()))
    a = ap.parse_args(argv)
    from bank import store
    from .answer import answer
    from .session import Session

    items = [json.loads(l) for l in EVAL.read_text().splitlines() if l.strip()]
    # Skipped: follow-ups (they need an earlier answer) and anything that would open Gmail or the Mac.
    skip = re.compile(r"^[\s\-]*(and |what about |the (first|second|third) one|who sent that|when is it due)"
                      r"|sync|gmail|refresh|check my (mail|email)|open |draft|reply", re.I)
    items = [i for i in items if not (i.get("kind") == "seed" and (i["route"] == "followup" or skip.search(i["q"])))]
    today = date.fromisoformat(a.today)
    right = leaks = 0
    wrong: list[tuple] = []
    by_route: Counter = Counter()
    with tempfile.TemporaryDirectory(prefix="flux-eval-") as tmp:
        root = Path(tmp) / "bank"
        src = store.bank_dir()
        shutil.copytree(src, root) if src.exists() else root.mkdir()
        for it in items:
            exp = it["route"]
            try:
                got = answer(it["q"], today=today, root=root, session=Session(), _online=lambda: False).route
            except Exception as e:
                got = f"error:{type(e).__name__}"
            ok = (got not in WEB_BOUND) if exp == "not_web" else (got == exp)
            leak = got in WEB_BOUND and exp not in WEB_BOUND | {"offline", "web"}
            right += ok
            leaks += leak
            by_route[exp, ok] += 1
            if not ok:
                wrong.append((it["q"], exp, got, leak))
    n = len(items)
    print(f"routing: {right}/{n} right ({100 * right // max(n, 1)}%); wrongly sent to the web: {leaks}")
    for r in sorted({k[0] for k in by_route}):
        g, b = by_route[r, True], by_route[r, False]
        print(f"  {r:10} {g}/{g + b}")
    for q, exp, got, leak in wrong[: a.show]:
        print(f"{'WEB ' if leak else '    '}{q!r}: wanted {exp}, got {got}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
