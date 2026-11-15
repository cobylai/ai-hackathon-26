"""Write reason/tests/routing_eval.jsonl: labeled questions for scoring routing.

Seeds come from the Examples tables in playbooks/*.md. An outside model writes
paraphrases, typos and speech-to-text slips of each seed. It only ever sees
made-up questions, never real mail or calendar data. This is build-time test
data only; the app itself still talks to local Bonsai alone.

Backends (first that is set):
  DEEPSEEK_API_KEY   -> https://api.deepseek.com (model DEEPSEEK_MODEL, default deepseek-chat)
  otherwise          -> LM Studio at http://127.0.0.1:1234/v1 (model LMS_MODEL, default qwen/qwen3.5-9b)

  uv run python scripts/gen_routing_eval.py [--per-seed 6] [--limit 0]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reason" / "tests" / "routing_eval.jsonl"

# Questions that must never go to the web (the failures from the full test pass, plus more).
NEVER_WEB = [
    "Who are you", "who are you?", "what am I?", "what does this week look like?",
    "how does my week look", "what can you do", "who made you", "are you an AI",
    "what do I have going on tomorrow", "what's my day look like", "am I busy friday",
    "what's due", "anything I should know about", "what did I forget",
]


def seeds() -> list[dict]:
    rows = []
    for p in sorted((ROOT / "playbooks").glob("*.md")):
        if p.name == "RULES.md":
            continue
        text = p.read_text()
        m = re.search(r"## Examples\n(.*?)(?:\n## |\Z)", text, re.S)
        if not m:
            continue
        for line in m.group(1).splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[0] and not set(cells[0]) <= set("-: ") and cells[0].lower() != "question":
                rows.append({"q": cells[0], "route": cells[1], "book": p.stem})
    return rows


def chat(prompt: str) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        url, model = "https://api.deepseek.com/chat/completions", os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        headers = {"Authorization": f"Bearer {key}"}
    else:
        url, model = "http://127.0.0.1:1234/v1/chat/completions", os.environ.get("LMS_MODEL", "qwen/qwen3.5-9b")
        headers = {}
    body = json.dumps({"model": model, "temperature": 0.9, "max_tokens": 800 if key else 4000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def variants(seed: str, n: int) -> list[str]:
    out = chat(
        f"A student types or speaks short requests to a personal assistant on their Mac (mail, calendar, "
        f"coursework). Write {n} different ways to say the same request as: \"{seed}\"\n"
        "Mix: casual wording, a typo or two, no punctuation, a speech-to-text slip (a misheard name or word), "
        "and one very short version. Keep names and dates in the request. One per line, no numbering, no quotes.")
    lines = [re.sub(r'^[\-\*\d\.\)\s"]+|"$', "", l).strip() for l in out.splitlines()]
    return [l for l in lines if 3 < len(l) < 140][:n]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-seed", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0, help="only the first N seeds (0 = all)")
    a = ap.parse_args()
    rows = seeds()
    if a.limit:
        rows = rows[: a.limit]
    seen, items = set(), []
    def add(q, route, kind, book=""):
        k = q.lower().strip(" ?.!")
        if k not in seen:
            seen.add(k); items.append({"q": q, "route": route, "kind": kind, "book": book})
    for r in rows:
        add(r["q"], r["route"], "seed", r["book"])
    for q in NEVER_WEB:
        add(q, "not_web", "never_web")
    for i, r in enumerate(rows, 1):
        try:
            for v in variants(r["q"], a.per_seed):
                add(v, r["route"], "variant", r["book"])
        except Exception as e:  # keep going: a few misses are fine
            print(f"seed {i}/{len(rows)} failed: {e}", file=sys.stderr)
        if i % 10 == 0:
            print(f"{i}/{len(rows)} seeds, {len(items)} questions", file=sys.stderr)
    OUT.write_text("".join(json.dumps(x) + "\n" for x in items))
    print(f"wrote {len(items)} questions to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
