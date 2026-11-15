"""Person pages: who someone is and how they relate to the user. No model call.

One file per person, <bank>/people/<slug>.md: JSON front matter (name, aliases, relation,
facts, updated_at) and a readable body. Pages start empty; the discovery piece fills them:

    from bank import people
    people.set_relation("Felix Ambrose", "cabin trip organizer")
    people.set_fact("Felix Ambrose", "collects the cabin money", source="<entry path or url>")
    people.get("felix")   # {"name", "aliases", "relation", "facts", "updated_at", "path", "entries"} | None
    people.names()        # ["Felix Ambrose", ...]
    people.remove_fact("Felix Ambrose", "collects the cabin money")

get() adds "entries" live from bank.by_person (never copied into the page), so a sender
with no page still gets one with no facts. Pages are not bank entries: search and due
don't read them.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import store
from .query import by_person

FOLDER = "people"
FIELDS = ("name", "aliases", "relation", "facts", "updated_at")


def _dir(root: Path | None) -> Path:
    return (root or store.bank_dir()) / FOLDER


def _render(page: dict) -> str:
    lines = ["---"] + [f"{k}: {json.dumps(page.get(k), ensure_ascii=False)}" for k in FIELDS] + ["---"]
    lines.append(f"# {page['name']}")
    lines.append("")
    lines.append(f"How they relate to you: {page.get('relation') or 'not known yet'}")
    if page.get("aliases"):
        lines.append(f"Also called: {', '.join(page['aliases'])}")
    lines.append("")
    lines.append("## Facts")
    lines += [f"- {f['fact']}" for f in page.get("facts") or []] or ["(none yet)"]
    return "\n".join(lines) + "\n"


def _read(path: Path) -> dict:
    page = store.parse(path.read_text())
    page.pop("body", None)
    page["path"] = str(path)
    return page


def _pages(root) -> list[dict]:
    out = []
    for p in sorted(_dir(root).glob("*.md")):
        try:
            out.append(_read(p))
        except Exception:
            continue
    return out


def _find(name: str, root) -> dict | None:
    n = name.strip().lower()
    if not n:
        return None
    pages = _pages(root)
    for pg in pages:  # exact name or alias first
        if n == pg["name"].lower() or n in [a.lower() for a in pg.get("aliases") or []]:
            return pg
    for pg in pages:  # then a whole word of the name ("felix" -> "Felix Ambrose")
        if n in re.findall(r"[a-z0-9']+", pg["name"].lower()):
            return pg
    return None


def _write(page: dict, root) -> dict:
    page["updated_at"] = datetime.now().isoformat(timespec="seconds")
    d = _dir(root)
    d.mkdir(parents=True, exist_ok=True)
    path = Path(page.get("path") or d / f"{store.slug(page['name'])}.md")
    tmp = path.with_suffix(".tmp")
    tmp.write_text(_render(page))
    tmp.replace(path)
    page["path"] = str(path)
    return page


def _ensure(name: str, root) -> dict:
    return _find(name, root) or {"name": name.strip(), "aliases": [], "relation": None, "facts": []}


def set_fact(name: str, fact: str, source: str | None = None, root: Path | None = None) -> dict:
    """Add one fact to name's page (made if missing). An exact repeat is skipped. Returns the page."""
    fact = re.sub(r"\s+", " ", fact or "").strip()
    if not fact:
        raise ValueError("empty fact")
    page = _ensure(name, root)
    if any(f["fact"].lower() == fact.lower() for f in page["facts"]):
        return page
    page["facts"].append({"fact": fact, "source": source,
                          "added": datetime.now().isoformat(timespec="seconds")})
    return _write(page, root)


def set_relation(name: str, relation: str | None, root: Path | None = None) -> dict:
    page = _ensure(name, root)
    page["relation"] = (relation or "").strip() or None
    return _write(page, root)


def add_alias(name: str, alias: str, root: Path | None = None) -> dict:
    page = _ensure(name, root)
    if alias.strip() and alias.strip().lower() not in [a.lower() for a in page["aliases"]]:
        page["aliases"].append(alias.strip())
    return _write(page, root)


def remove_fact(name: str, fact: str, root: Path | None = None) -> bool:
    page = _find(name, root)
    if not page:
        return False
    keep = [f for f in page["facts"] if f["fact"].lower() != fact.strip().lower()]
    if len(keep) == len(page["facts"]):
        return False
    page["facts"] = keep
    _write(page, root)
    return True


def names(root: Path | None = None) -> list[str]:
    return [p["name"] for p in _pages(root)]


def get(name: str, root: Path | None = None) -> dict | None:
    """The page for name plus their entries (newest first). A sender with no page gets
    an empty one named after their newest email; no page and no email: None."""
    page = _find(name, root)
    entries = [e for e in by_person(page["name"] if page else name, root=root) if e.get("kind") == "email"]
    if page is None:
        if not entries:
            return None
        page = {"name": entries[0].get("sender_name") or entries[0].get("sender_address") or name,
                "aliases": [], "relation": None, "facts": [], "updated_at": None, "path": None}
    elif not entries:
        for a in page.get("aliases") or []:
            entries = [e for e in by_person(a, root=root) if e.get("kind") == "email"]
            if entries:
                break
    page["entries"] = entries
    return page
