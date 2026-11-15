"""Run the 12 agent tasks against the live local Bonsai (127.0.0.1:8080). Fixture data only.

    BONSAI_MODELS_DIR=... uv run python -m reason.agent_eval [--only 3] [--repeat 2] [--out f.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from reason import agent
from reason.agent_eval import TASKS, check, world


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m reason.agent_eval")
    ap.add_argument("--only", type=int, action="append", help="task number (1-12); repeatable")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", help="write every run (trace included) as JSON here")
    args = ap.parse_args(argv)
    from reason.live_check import block_network
    block_network()  # localhost (Bonsai) only; the web tools are fixtures
    runs, passed = [], 0
    t_all = time.monotonic()
    for rep in range(args.repeat):
        for i, task in enumerate(TASKS, 1):
            if args.only and i not in args.only:
                continue
            w = world()
            try:
                res = agent.run(task["q"], w.env(online=True))
            finally:
                w.close()
            ok, why = check(task, res)
            passed += ok
            runs.append({"task": i, "rep": rep, "q": task["q"], "pass": ok, "why": why, "ok": res.ok,
                         "stop": res.stop, "steps": len(res.trace), "tokens": res.tokens,
                         "seconds": res.seconds, "text": res.text,
                         "proposal": (f"{res.proposal['kind']} {res.proposal['item']['id']}"
                                      if res.proposal else None),
                         "trace": agent.trace_lines(res.trace)})
            r = runs[-1]
            print(f"[{'PASS' if ok else 'FAIL'}] {i:>2} {task['q']}")
            print(f"     {r['steps']} steps, {r['tokens']} tokens, {r['seconds']} s, stop={r['stop']}"
                  f"{', proposal ' + r['proposal'] if r['proposal'] else ''}")
            for line in r["trace"]:
                print(f"       {line[:150]}")
            print(f"     -> {res.text[:220]!r}")
            if why:
                print(f"     why: {why}")
            sys.stdout.flush()
    n = len(runs)
    steps = sum(r["steps"] for r in runs) / max(n, 1)
    toks = sum(r["tokens"] for r in runs) / max(n, 1)
    secs = sum(r["seconds"] for r in runs) / max(n, 1)
    print(f"\n{passed}/{n} passed; mean {steps:.1f} steps, {toks:.0f} tokens, {secs:.1f} s per task; "
          f"{time.monotonic() - t_all:.0f} s total")
    if args.out:
        with open(args.out, "w") as fh:
            json.dump({"passed": passed, "runs": runs}, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
