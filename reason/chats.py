"""Saved chats: one JSON file per conversation, on this Mac, outside the repo.

    folder()            $MUSE_CHATS_DIR, else "<bank dir>-chats" (~/muse-demo-bank-chats),
                        else ~/muse-chats when the bank sits inside the repo
    save(session)       writes <id>.json (atomically); a chat with no turns is not written
    load(id)            -> Session, follow-ups go on from where it left off
    listing()           -> [{"id", "title", "started", "updated", "turns"}], newest first
    delete(id)          removes the file

The files hold personal content (questions and answers about mail), so they are never
written inside the repo. No model call: a chat's title is its first question.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from bank import store

from .session import Session

REPO = Path(__file__).resolve().parent.parent
_ID = re.compile(r"^[0-9a-f]{6,32}$")


def folder() -> Path:
    env = os.environ.get("MUSE_CHATS_DIR")
    if env:
        return Path(env).expanduser()
    bank = store.bank_dir().expanduser().resolve()
    if bank == REPO or REPO in bank.parents:
        return Path.home() / "muse-chats"
    return bank.parent / f"{bank.name}-chats"


def _path(chat_id: str, root: Path | None = None) -> Path:
    if not _ID.match(chat_id or ""):
        raise ValueError(f"not a chat id: {chat_id!r}")
    return (root or folder()) / f"{chat_id}.json"


def save(s: Session, root: Path | None = None) -> Path | None:
    if not s.turns:
        return None
    p = _path(s.id, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(s.to_dict(), ensure_ascii=False, indent=1))
    os.replace(tmp, p)
    return p


def load(chat_id: str, root: Path | None = None) -> Session:
    return Session.from_dict(json.loads(_path(chat_id, root).read_text()))


def read(chat_id: str, root: Path | None = None) -> dict:
    """The saved chat as it is on disk (what the window redraws)."""
    return json.loads(_path(chat_id, root).read_text())


def delete(chat_id: str, root: Path | None = None) -> bool:
    p = _path(chat_id, root)
    if p.exists():
        p.unlink()
        return True
    return False


def listing(root: Path | None = None) -> list[dict]:
    root = root or folder()
    out = []
    for p in root.glob("*.json") if root.exists() else []:
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):
            continue  # a half-written or foreign file: skip it
        turns = d.get("turns") or []
        if not turns or not _ID.match(str(d.get("id") or "")):
            continue
        out.append({"id": d["id"], "title": d.get("title") or turns[0].get("question") or "",
                    "started": d.get("started") or "",
                    "updated": turns[-1].get("at") or d.get("started") or "", "turns": len(turns)})
    out.sort(key=lambda c: c["updated"], reverse=True)
    return out
