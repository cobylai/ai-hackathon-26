"""Muse context store: what the assistant has read, as markdown files.

    from bank import ingest, search, by_person, due, rebuild_index
    ingest(text, source="msg:1234", kind="email")   # needs the Bonsai server
    due("2026-11-16", "2026-11-20")                  # offline, no model call

Data lives in $MUSE_BANK_DIR, else data/bank/ (gitignored).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from . import store
from .index import rebuild_index
from .query import by_person, due, search
from .store import bank_dir

__all__ = ["ingest", "search", "by_person", "due", "rebuild_index", "bank_dir"]


def ingest(text: str, source: str, kind: str, *, today: date | None = None,
           root: Path | None = None) -> dict:
    """Extract facts with Bonsai and file one entry.

    Returns {"status": "added" | "duplicate", "path": str, "entry": dict, "raw": [model replies]}.
    """
    if kind not in ("email", "page"):
        raise ValueError(f"kind must be 'email' or 'page', got {kind!r}")
    root = root or store.bank_dir()
    cid = store.content_id(text)
    dup = store.find_duplicate(cid, source, root)
    if dup:
        return {"status": "duplicate", "path": str(dup), "entry": store.read_entry(dup), "raw": []}

    from . import extract
    raws = []
    for c in extract.chunks(text):
        r = extract.ask_model(c, kind)
        phrases = extract._phrases(r.get("deadlines"))
        if phrases and not extract._clean(r.get("ask")):
            r["ask"] = extract.ask_for_deadline(c, kind, phrases[0])
            r["_ask_from_followup"] = True
        raws.append(r)
    entry = extract.build_fields(text, kind, today or date.today(), raws)
    entry.update(id=cid, source=source)
    path = store.write_entry(entry, root)
    entry["path"] = str(path)
    rebuild_index(root)
    return {"status": "added", "path": str(path), "entry": entry, "raw": raws}
