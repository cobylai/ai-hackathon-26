"""index.md: one line per entry, newest first, capped so Bonsai can read it whole."""
from __future__ import annotations

from pathlib import Path

from . import store

INDEX_TOKEN_CAP = 20_000
SUMMARY_CHARS = 100


def _count(text: str) -> int:
    try:
        from llm import tokens  # offline tokenizer; no server needed
        return tokens.count(text)
    except Exception:
        return int(len(text) / 2.5) + 1


def index_line(e: dict) -> str:
    who = e.get("sender_name") or e.get("sender_address") or e.get("source") or "?"
    where = e["folder"] + (f" {e['course']}" if e.get("course") else "")
    summ = " ".join((e.get("body") or "").split())
    if len(summ) > SUMMARY_CHARS:
        summ = summ[:SUMMARY_CHARS - 1].rstrip() + "…"
    dls = []
    for d in e.get("deadlines") or []:
        when = d.get("date") or "?"
        if d.get("time"):
            when += f" {d['time']}"
        dls.append(f"{when} ({d.get('phrase')})")
    due = "due " + "; ".join(dls) if dls else "no deadline"
    rel = Path(e["path"]).relative_to(Path(e["path"]).parents[1]).as_posix() if e.get("path") \
        else store.entry_relpath(e)
    sent = ("~" if e.get("sent_date_guessed") else "") + str(e.get("sent_date"))
    return f"{sent} | {who} | {where} | {summ} | {due} | {rel}"


def rebuild_index(root: Path | None = None) -> Path:
    root = root or store.bank_dir()
    root.mkdir(parents=True, exist_ok=True)
    entries = sorted(store.all_entries(root),
                     key=lambda e: (e.get("sent_date") or "", e.get("ingested_at") or ""),
                     reverse=True)
    header = ("# Flux context store index\n"
              "date | from | folder | summary | deadlines | file\n")
    lines, used = [], _count(header)
    for i, e in enumerate(entries):
        line = index_line(e)
        n = _count(line) + 1
        if used + n > INDEX_TOKEN_CAP:
            lines.append(f"({len(entries) - i} older entries omitted)")
            break
        lines.append(line)
        used += n
    path = root / "index.md"
    path.write_text(header + "\n".join(lines) + ("\n" if lines else ""))
    return path
