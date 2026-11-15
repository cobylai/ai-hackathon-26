"""Real-inbox mail sync: Gmail (signed-in browser profile) -> the bank, incrementally.

Design ideas (not code) follow OpenJarvis' Gmail connector (Apache-2.0,
github.com/open-jarvis/OpenJarvis): a persisted cursor with a high-water mark,
stable per-message doc ids ("gmail:<id>"), a Document-shaped record per
message, and resumable syncs. Flux reads Gmail through harness/email (a
read-only browser path); IMAP/OAuth would need a secret the user creates.

The bank is outside git: $FLUX_BANK_DIR, else ~/flux-bank (live_bank_dir).
All model work is bank.ingest -> local Bonsai (llm/client.py). Never sends.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE_FILE = ".mailsync.json"
LOCK_FILE = ".mailsync.lock"
DEFAULT_DAYS = 14
DEFAULT_LIMIT = 200


@dataclass
class Document:
    """One message, shaped like a connector Document."""
    doc_id: str          # "gmail:<thread>:<message id>" (or ...#<index> if Gmail gave no id)
    thread_id: str
    title: str | None
    author: str
    timestamp: str | None
    content: str


@dataclass
class ThreadRow:
    thread_id: str
    subject: str = ""
    date: str = ""
    snippet: str = ""


@dataclass
class Result:
    threads_seen: int = 0
    threads_skipped: int = 0   # unchanged since the last run
    threads_read: int = 0
    threads_failed: int = 0
    messages: int = 0
    added: int = 0
    duplicates: int = 0
    errors: int = 0
    remaining: int = 0         # threads left when the time budget ran out
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    def line(self) -> str:
        s = (f"{self.threads_seen} thread(s): {self.threads_read} read, {self.threads_skipped} unchanged, "
             f"{self.threads_failed} failed; {self.messages} message(s), {self.added} added, "
             f"{self.duplicates} already filed, {self.errors} error(s); {self.seconds:.1f}s")
        return s + (f"; {self.remaining} left (run again)" if self.remaining else "")


# ---- helpers (moved from scripts/sync_email.py, which re-exports them) ----

def split_sender(sender: str) -> tuple[str | None, str | None]:
    """'Name <addr>' -> (name, addr); a bare address or name fills one side."""
    m = re.match(r"\s*(.*?)\s*<([^>]+)>\s*$", sender or "")
    if m:
        return (m.group(1) or None), m.group(2)
    s = (sender or "").strip()
    return (None, s) if "@" in s else (s or None, None)


def iso_date(raw: str) -> str | None:
    """Gmail's title date -> ISO. Seen: 'Thu, Nov 12, 2026, 4:30 PM' (fixture)
    and '14 Nov 2026, 22:24' (live account, 24-hour locale)."""
    s = " ".join((raw or "").replace(" ", " ").split())
    for fmt in ("%a, %b %d, %Y, %I:%M %p", "%b %d, %Y, %I:%M %p", "%a, %b %d, %Y %I:%M %p",
                "%d %b %Y, %H:%M", "%a, %d %b %Y, %H:%M", "%d %b %Y, %I:%M %p", "%b %d, %Y, %H:%M"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def check_live_bank(root: Path) -> None:
    """Live (real) mail must not land in a sample-mail demo or test bank."""
    name = root.name.lower()
    if "demo" in name or "test" in name:
        raise SystemExit(f"Refusing to sync live mail into {root}: it looks like a demo/test "
                         "bank (sample mail). Use FLUX_BANK_DIR=~/flux-bank, or pass "
                         "--allow-demo if you really mean it.")


def inside_repo(path: Path) -> bool:
    p = Path(path).expanduser().resolve()
    r = REPO.resolve()
    return p == r or r in p.parents


def live_bank_dir() -> Path:
    """Where real mail goes: $FLUX_BANK_DIR, else ~/flux-bank. Never inside the repo."""
    env = os.environ.get("FLUX_BANK_DIR") or os.environ.get("MUSE_BANK_DIR")
    root = Path(env).expanduser() if env else Path.home() / "flux-bank"
    assert_outside_repo(root)
    return root


def assert_outside_repo(root: Path) -> None:
    if inside_repo(root):
        raise SystemExit(f"Refusing to use {root} for real mail: it is inside the git repo "
                         f"({REPO}). Use ~/flux-bank or set FLUX_BANK_DIR to a folder outside it.")


def file_thread(thread_id: str, subject: str | None, messages, ingest, ids=None, known=()) -> list[dict]:
    """messages = read_messages() output, newest first: [(sender, date, body)].
    ids (same order, optional): Gmail message ids; ids in `known` are skipped."""
    out = []
    n = len(messages)
    for i, (sender, raw_date, body) in enumerate(reversed(messages)):  # oldest first
        mid = (ids[n - 1 - i] if ids and len(ids) == n else "") or ""
        if mid and mid in known:
            continue
        if not (body or "").strip():
            continue
        name, addr = split_sender(sender)
        source = f"gmail:{thread_id}:{mid}" if mid else f"gmail:{thread_id}#{i}"
        r = ingest(body, source=source, kind="email", sender_name=name, sender_address=addr,
                   sent_date=iso_date(raw_date), subject=subject or None)
        r["message_id"] = mid
        out.append(r)
    return out


# ---- cursor state (high-water mark + per-thread fingerprint + seen message ids) ----

def _fp(row: ThreadRow) -> str:
    return hashlib.sha256(f"{row.date}|{row.snippet}|{row.subject}".encode()).hexdigest()[:16]


def load_state(root: Path) -> dict:
    try:
        s = json.loads((Path(root) / STATE_FILE).read_text())
        if isinstance(s, dict) and isinstance(s.get("threads"), dict):
            return s
    except (OSError, ValueError):
        pass
    return {"version": 1, "last_run": None, "high_water": None, "threads": {}}


def save_state(root: Path, state: dict) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / (STATE_FILE + ".tmp")
    tmp.write_text(json.dumps(state))
    tmp.replace(root / STATE_FILE)


class Locked(Exception):
    pass


class _Lock:
    def __init__(self, root: Path):
        Path(root).mkdir(parents=True, exist_ok=True)
        self.f = open(Path(root) / LOCK_FILE, "w")

    def __enter__(self):
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.close()
            raise Locked("another mail sync is already running")
        return self

    def __exit__(self, *a):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


# ---- the sync ----

def sync_mail(gw, ingest, root: Path, *, days: int = DEFAULT_DAYS, limit: int = DEFAULT_LIMIT,
              budget_s: float | None = None, progress=lambda s: None, max_errors: int = 3,
              clock=time.monotonic) -> Result:
    """gw.list_threads(days, limit) -> [ThreadRow]; gw.read_thread(id) -> (messages, ids) | None.
    Skips threads whose row is unchanged; files only unseen messages. Resumable."""
    root = Path(root)
    assert_outside_repo(root)
    t0 = clock()
    res = Result()
    with _Lock(root):
        state = load_state(root)
        rows, seen = [], set()
        for r in gw.list_threads(days, limit):
            if r.thread_id and r.thread_id not in seen:
                seen.add(r.thread_id)
                rows.append(r)
        rows = rows[:limit]
        res.threads_seen = len(rows)
        consecutive = 0
        for k, row in enumerate(rows):
            st = state["threads"].get(row.thread_id) or {}
            if st.get("fp") == _fp(row) and st.get("done"):
                res.threads_skipped += 1
                continue
            if budget_s is not None and clock() - t0 > budget_s:
                res.remaining = sum(1 for x in rows[k:] if not (
                    state["threads"].get(x.thread_id, {}).get("fp") == _fp(x)
                    and state["threads"].get(x.thread_id, {}).get("done")))
                break
            got = gw.read_thread(row.thread_id)
            if not got:
                res.threads_failed += 1
                continue
            msgs, ids = got
            res.threads_read += 1
            known = set(st.get("msgs") or [])
            try:
                rs = file_thread(row.thread_id, row.subject, msgs, ingest, ids, known)
                consecutive = 0
            except Exception as e:  # model down, disk full ...: leave the thread unmarked, retry next run
                res.errors += 1
                consecutive += 1
                res.notes.append(f"{type(e).__name__}")
                if consecutive >= max_errors:
                    res.notes.append("stopped: repeated errors (is Bonsai running on 127.0.0.1:8080?)")
                    break
                continue
            res.messages += len(rs)
            res.added += sum(r["status"] == "added" for r in rs)
            res.duplicates += sum(r["status"] != "added" for r in rs)
            st_ids = known | {r["message_id"] for r in rs if r.get("message_id")} | {i for i in (ids or []) if i}
            state["threads"][row.thread_id] = {"fp": _fp(row), "done": True, "msgs": sorted(st_ids)}
            hw = iso_date(row.date) or None
            if hw and (not state.get("high_water") or hw > state["high_water"]):
                state["high_water"] = hw
            save_state(root, state)  # after every thread: a crash loses at most one
            progress(f"  thread {k + 1}/{len(rows)}: {len(rs)} message(s)")
        state["last_run"] = datetime.now().isoformat(timespec="seconds")
        save_state(root, state)
    res.seconds = clock() - t0
    return res


# ---- the live gateway: harness/email, read-only ----

class HarnessGateway:
    """Search and read only. Never opens compose, never drafts, never sends."""

    def __init__(self):
        from harness.browser.session import get_session
        from harness.email.status import signed_in
        self.page = get_session().start().page
        if not signed_in(self.page):
            raise SystemExit("Not signed in to Gmail: run  uv run python -m harness login "
                             "https://mail.google.com  once, then retry.")

    def list_threads(self, days, limit):
        from harness.email import search
        return [ThreadRow(r.thread_id, r.subject, r.date, r.snippet)
                for r in search.collect_rows(self.page, days=days, limit=limit)]

    def read_thread(self, thread_id):
        from harness.email import read
        if not read.open_thread(self.page, thread_id):
            return None
        return read.read_messages(self.page), read.message_ids(self.page)


def run(days=DEFAULT_DAYS, limit=DEFAULT_LIMIT, budget_s=None, root: Path | None = None,
        gateway=None, ingest=None, progress=lambda s: None, allow_demo=False) -> Result:
    root = Path(root) if root else live_bank_dir()
    assert_outside_repo(root)
    if not allow_demo:
        check_live_bank(root)
    if ingest is None:
        from bank import ingest as _i
        ingest = lambda *a, **k: _i(*a, root=root, **k)  # noqa: E731
    return sync_mail(gateway or HarnessGateway(), ingest, root, days=days, limit=limit,
                     budget_s=budget_s, progress=progress)
