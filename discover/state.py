"""What the user answered in discovery: <bank>/discover/answers.json. No model call.

One record per candidate id: the question, what it wrote (or would have), its sources and
the answer: "yes" (written), "no" (never ask again) or "removed" (was yes, then unlearned;
never ask again). Skipped questions get no record, so they come back next run.
The discover folder is not a bank entry folder: search, due and the index don't read it.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from bank import store

FOLDER = "discover"


def path(root: Path | None = None) -> Path:
    return (root or store.bank_dir()) / FOLDER / "answers.json"


def load(root: Path | None = None) -> list[dict]:
    p = path(root)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text()).get("answers") or []
    except (ValueError, OSError):
        return []


def _save(records: list[dict], root) -> None:
    p = path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"answers": records}, indent=1, ensure_ascii=False) + "\n")
    tmp.replace(p)


def record(cand: dict, answer: str, root: Path | None = None, wrote: str | None = None) -> dict:
    recs = [r for r in load(root) if r["id"] != cand["id"]]
    rec = {k: cand[k] for k in ("id", "kind", "question", "fact", "write", "sources")}
    rec.update(answer=answer, wrote=wrote, at=datetime.now().isoformat(timespec="seconds"))
    recs.append(rec)
    _save(recs, root)
    return rec


def mark(rec_id: str, answer: str, root: Path | None = None) -> None:
    recs = load(root)
    for r in recs:
        if r["id"] == rec_id:
            r["answer"] = answer
            r["at"] = datetime.now().isoformat(timespec="seconds")
    _save(recs, root)


def answered(root: Path | None = None) -> set[str]:
    return {r["id"] for r in load(root)}


def learned(root: Path | None = None) -> list[dict]:
    """Confirmed facts still in place, in the order they were confirmed."""
    return [r for r in load(root) if r.get("answer") == "yes"]
