"""Entry files on disk: one markdown file per item, JSON-valued front matter.

Data lives in $MUSE_BANK_DIR, else data/bank/ under the repo root. Gitignored.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

FOLDERS = ("course", "person", "other")
FIELDS = ("id", "kind", "folder", "source", "sender_name", "sender_address", "sent_date",
          "subject", "ask", "deadlines", "course", "topic", "ingested_at")

REPO = Path(__file__).resolve().parent.parent


def bank_dir() -> Path:
    env = os.environ.get("MUSE_BANK_DIR")
    return Path(env).expanduser() if env else REPO / "data" / "bank"


def content_id(text: str) -> str:
    norm = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(norm.encode()).hexdigest()[:12]


def slug(s: str | None, n: int = 40) -> str:
    s = re.sub(r"^((re|fwd?|fw)\s*:\s*)+", "", (s or "").strip(), flags=re.I)
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:n].rstrip("-") or "untitled"


def entry_relpath(entry: dict) -> str:
    return f"{entry['folder']}/{entry['sent_date']}-{slug(entry.get('subject'))}-{entry['id']}.md"


def render(entry: dict) -> str:
    lines = ["---"]
    for k in FIELDS:
        lines.append(f"{k}: {json.dumps(entry.get(k), ensure_ascii=False)}")
    lines.append("---")
    lines.append((entry.get("body") or "").strip())
    return "\n".join(lines) + "\n"


def parse(text: str) -> dict:
    if not text.startswith("---\n"):
        raise ValueError("no front matter")
    head, _, body = text[4:].partition("\n---\n")
    entry: dict = {}
    for line in head.splitlines():
        k, sep, v = line.partition(": ")
        if sep:
            entry[k] = json.loads(v)
    entry["body"] = body.strip()
    return entry


def write_entry(entry: dict, root: Path | None = None) -> Path:
    root = root or bank_dir()
    path = root / entry_relpath(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(render(entry))
    tmp.replace(path)
    return path


def read_entry(path: Path) -> dict:
    e = parse(Path(path).read_text())
    e["path"] = str(path)
    return e


def all_entries(root: Path | None = None) -> list[dict]:
    root = root or bank_dir()
    out = []
    for f in FOLDERS:
        for p in sorted((root / f).glob("*.md")):
            try:
                out.append(read_entry(p))
            except (ValueError, json.JSONDecodeError):
                continue
    return out


def find_duplicate(cid: str, source: str | None, root: Path | None = None) -> Path | None:
    """Same source wins (stable message ids from the sync); content id is the fallback."""
    root = root or bank_dir()
    if source:
        for e in all_entries(root):
            if e.get("source") == source:
                return Path(e["path"])
    for f in FOLDERS:
        hits = list((root / f).glob(f"*-{cid}.md"))
        if hits:
            return hits[0]
    return None
