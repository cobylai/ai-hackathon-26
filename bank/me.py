"""Notes about the user, in the user's own words: the "me" folder. No model call.

    remember("my lab is Tuesdays at 2")   -> {"status": "added" | "duplicate", "path", "entry"}
    notes()                               -> [entry], newest first
    forget("lab")                         -> {"status": "removed" | "none" | "ambiguous", "removed", "candidates"}

A note is an ordinary bank entry (kind "me", folder "me"), so bank.search and the index
see it. Only what the user said goes in (playbooks/RULES.md rule 7).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from . import store
from .index import rebuild_index
from .query import STOPWORDS

SENDER = "you"


def _clean(fact: str) -> str:
    fact = re.sub(r"\s+", " ", fact or "").strip().strip("\"'“”")
    return fact.rstrip(" .!")


def remember(fact: str, today: date | None = None, root: Path | None = None) -> dict:
    fact = _clean(fact)
    if not fact:
        raise ValueError("nothing to remember")
    root = root or store.bank_dir()
    cid = store.content_id("me:" + fact.lower())
    for e in notes(root):
        if e["id"] == cid:
            return {"status": "duplicate", "path": e["path"], "entry": e}
    today = today or date.today()
    entry = {"id": cid, "kind": "me", "folder": "me", "source": f"me:{cid}",
             "sender_name": SENDER, "sender_address": None, "sent_date": today.isoformat(),
             "subject": fact, "ask": None, "deadlines": [], "course": None, "topic": None,
             "sent_date_guessed": False, "ingested_at": datetime.now().isoformat(),
             "body": fact}
    path = store.write_entry(entry, root)
    entry["path"] = str(path)
    rebuild_index(root)
    return {"status": "added", "path": str(path), "entry": entry}


def notes(root: Path | None = None) -> list[dict]:
    root = root or store.bank_dir()
    out = []
    for p in (root / "me").glob("*.md"):
        try:
            out.append(store.read_entry(p))
        except Exception:
            continue
    return sorted(out, key=lambda e: (e.get("sent_date") or "", e.get("ingested_at") or ""), reverse=True)


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOPWORDS and len(w) > 1}


def forget(text: str, root: Path | None = None) -> dict:
    """Delete the note sharing the most words with text. Empty text: the newest note.

    A tie deletes nothing and returns the tied notes as candidates."""
    root = root or store.bank_dir()
    all_ = notes(root)
    if not all_:
        return {"status": "none", "removed": None, "candidates": []}
    want = _words(text or "")
    if not want:
        pick = all_[0]
    else:
        scored = [(len(want & _words(e.get("body") or "")), e) for e in all_]
        best = max(s for s, _ in scored)
        if best == 0:
            return {"status": "none", "removed": None, "candidates": []}
        top = [e for s, e in scored if s == best]
        if len(top) > 1:
            return {"status": "ambiguous", "removed": None, "candidates": top}
        pick = top[0]
    Path(pick["path"]).unlink()
    rebuild_index(root)
    return {"status": "removed", "removed": pick, "candidates": []}
