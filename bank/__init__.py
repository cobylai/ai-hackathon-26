"""Muse context store: what the assistant has read, as markdown files.

    from bank import ingest, search, by_person, due, rebuild_index
    ingest(text, source="msg:1234", kind="email")   # needs the Bonsai server
    due("2026-11-16", "2026-11-20")                  # offline, no model call

Data lives in $MUSE_BANK_DIR, else data/bank/ (gitignored).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from . import people, store
from .index import rebuild_index
from .me import forget, notes, remember
from .query import by_person, due, search
from .store import bank_dir

__all__ = ["ingest", "search", "by_person", "due", "rebuild_index", "bank_dir",
           "remember", "notes", "forget", "people"]


def ingest(text: str, source: str, kind: str, *, sender_name: str | None = None,
           sender_address: str | None = None, sent_date: date | str | None = None,
           subject: str | None = None, today: date | None = None,
           root: Path | None = None) -> dict:
    """Extract facts with Bonsai and file one entry.

    The optional sender/date/subject keywords are for callers (the email sync)
    that already have them split out; they win over anything in the text.
    Returns {"status": "added" | "duplicate", "path": str, "entry": dict, "raw": [model replies]}.
    """
    if kind not in ("email", "page"):
        raise ValueError(f"kind must be 'email' or 'page', got {kind!r}")
    if any((sender_name, sender_address, sent_date, subject)):
        frm = (f"{sender_name} <{sender_address}>" if sender_name and sender_address
               else sender_address or sender_name)
        sd = sent_date.isoformat() if isinstance(sent_date, date) else sent_date
        head = [f"From: {frm}" if frm else None, f"Date: {sd}" if sd else None,
                f"Subject: {subject}" if subject else None]
        text = "\n".join(h for h in head if h) + "\n\n" + text.lstrip()
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
