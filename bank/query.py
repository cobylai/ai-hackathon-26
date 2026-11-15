"""Readers. Offline: they only read markdown files and never import llm."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from . import store

STOPWORDS = set("""a an and are as at be by did do does for from had has have i in is it me my
of on or s so that the this to was what when where which who why will with you your about
any did due get got me need any""".split())

_STRONG = ("subject", "sender_name", "sender_address")
_WEAK = ("ask", "course", "topic", "source", "body")


def _terms(query: str) -> list[str]:
    words = re.findall(r"[a-z0-9@.\-]+", query.lower())
    return list(dict.fromkeys(w.strip(".-") for w in words if w.strip(".-") not in STOPWORDS
                              and w.strip(".-")))


def _text(e: dict, fields) -> str:
    parts = []
    for f in fields:
        v = e.get(f)
        if f == "body":
            parts.append(v or "")
        elif v:
            parts.append(str(v))
    if "ask" in fields:
        parts += [d.get("phrase") or "" for d in e.get("deadlines") or []]
    return " ".join(parts).lower()


def search(query: str, limit: int = 10, root: Path | None = None) -> list[dict]:
    terms = _terms(query)
    if not terms:
        return []
    scored = []
    for e in store.all_entries(root):
        strong, weak = _text(e, _STRONG), _text(e, _WEAK)
        score = 0
        for t in terms:
            if t in strong:
                score += 2
            elif t in weak:
                score += 1
        if score:
            scored.append((score, e.get("sent_date") or "", e))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [e for _, _, e in scored[:limit]]


def by_person(name: str, root: Path | None = None) -> list[dict]:
    n = name.strip().lower()
    if not n:
        return []
    hits = [e for e in store.all_entries(root)
            if n in (e.get("sender_name") or "").lower() or n in (e.get("sender_address") or "").lower()]
    return sorted(hits, key=lambda e: e.get("sent_date") or "", reverse=True)


def _iso(d) -> str:
    return d.isoformat() if isinstance(d, date) else str(d)[:10]


def due(start_date, end_date, root: Path | None = None) -> list[dict]:
    lo, hi = _iso(start_date), _iso(end_date)
    rows = []
    for e in store.all_entries(root):
        for d in e.get("deadlines") or []:
            if d.get("date") and lo <= d["date"] <= hi:
                rows.append({"date": d["date"], "time": d.get("time"),
                             "phrase": d.get("phrase"), "entry": e})
    rows.sort(key=lambda r: (r["date"], r["time"] is None, r["time"] or ""))
    return rows
