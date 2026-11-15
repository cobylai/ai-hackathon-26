"""Suggested next steps under an answer: at most two, decided by code. playbooks/suggest.md.

    for_answer(a, session, today, root, events_fn) -> [{"id", "line", "button", "kind", ...}]
    take(id, session) -> the suggestion (and hides it), or None
    dismiss(id, session) -> bool
    meeting(e, today, events_fn) -> {"when", "start", "free", "clash", "slot"} | None

No model call. Free or busy is worked out from the email's own day and time and one day of
Apple Calendar; it is stated only when both were read. Nothing runs until a click.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

from bank import dates, store

from . import playbook
from .playbook import say

LIMIT = 2
ROUTES = ("due", "catchup", "person", "bank", "followup")
SLOT = timedelta(hours=1)        # a proposed time holds an hour
STEP = timedelta(minutes=30)     # free slots are looked for on the half hour
DAY_START, DAY_END = time(9, 0), time(18, 0)
URL_RE = re.compile(r"^(https?|file)://", re.I)

_hidden: dict[str, set[str]] = {}   # session id -> keys dismissed, drafted or opened
_offered: dict[str, dict] = {}      # suggestion id -> suggestion (with its entry)


def _sid(session) -> str:
    return getattr(session, "id", None) or "-"


def reset() -> None:
    _hidden.clear()
    _offered.clear()


def first_name(e: dict) -> str:
    who = (e.get("sender_name") or "").strip()
    if not who or "@" in who:
        return (e.get("sender_address") or "there").split("@")[0]
    parts = who.split()
    if parts[0].lower().rstrip(".") in ("prof", "professor", "dr", "mr", "mrs", "ms") and len(parts) > 1:
        return who
    return parts[0]


def _text(e: dict) -> str:
    return " ".join(str(e.get(k) or "") for k in ("ask", "subject", "body"))


def is_meeting(e: dict) -> bool:
    return e.get("kind") == "email" and bool(playbook.trigger("suggest", "meeting").search(_text(e)))


def _sent(e: dict) -> date:
    try:
        return date.fromisoformat(str(e.get("sent_date"))[:10])
    except ValueError:
        return date.today()


def proposed(e: dict) -> datetime | None:
    """The day and time an email proposes, worked out in code; None unless both are read."""
    text = _text(e)
    day, hhmm = None, None
    for d in e.get("deadlines") or []:
        if d.get("date"):
            try:
                day = date.fromisoformat(d["date"])
            except ValueError:
                continue
            hhmm = d.get("time")
            break
    if day is None:
        for part in (e.get("ask"), e.get("subject"), e.get("body")):
            if part and (day := dates.resolve_date(str(part), _sent(e))):
                break
    if not hhmm:
        hhmm = dates.resolve_time(text)
    if not hhmm:
        m = playbook.trigger("suggest", "bare_time").search(text)
        if m:
            h, mi = int(m.group(1)), int(m.group(2) or 0)
            if 1 <= h <= 7:
                h += 12
            elif not 8 <= h <= 12:
                h = None
            hhmm = f"{h:02d}:{mi:02d}" if h is not None else None
    if day is None or not hhmm:
        return None
    hh, mm = (int(x) for x in hhmm.split(":"))
    return datetime.combine(day, time(hh, mm))


def when_text(t: datetime) -> str:
    from .answer import _time
    return f"{t:%A}, {t:%b} {t.day} at {_time(f'{t:%H:%M}')}"


def _overlap(evs: list[dict], lo: datetime, hi: datetime) -> dict | None:
    for ev in evs:
        if ev.get("all_day"):
            continue
        if ev["start"] < hi and ev["end"] > lo:
            return ev
    return None


def next_free(evs: list[dict], t: datetime) -> datetime | None:
    """The first free hour that day, 9am to 6pm: after the proposed time first, then before it."""
    day = t.date()
    lo, hi = datetime.combine(day, DAY_START), datetime.combine(day, DAY_END)
    starts, s = [], lo
    while s + SLOT <= hi:
        starts.append(s)
        s += STEP
    for s in [x for x in starts if x > t] + [x for x in starts if x < t]:
        if not _overlap(evs, s, s + SLOT):
            return s
    return None


def meeting(e: dict, events_fn=None) -> dict | None:
    """Free or busy for a meeting email; None when the time or the calendar can't be read."""
    if not is_meeting(e):
        return None
    t = proposed(e)
    if t is None:
        return None
    import applecal
    try:
        evs = (events_fn or applecal.events)(t.date(), t.date())
    except applecal.CalendarError:
        return None
    clash = _overlap(evs, t, t + SLOT)
    out = {"when": when_text(t), "start": t.isoformat(), "free": clash is None,
           "clash": (clash.get("title") or "something") if clash else None, "slot": None}
    if clash:
        s = next_free(evs, t)
        if s:
            from .answer import _time
            out["slot"] = _time(f"{s:%H:%M}")
    return out


def _entries(a, root) -> list[dict]:
    out, seen = [], set()
    for r in a.rows or []:
        e = r.get("entry") if r.get("kind") == "entry" else None
        if e and e.get("path") not in seen:
            seen.add(e.get("path"))
            out.append(e)
    for p in a.sources or []:
        if p in seen or not str(p).endswith(".md"):
            continue
        try:
            e = store.read_entry(Path(p))
        except Exception:
            continue
        e.setdefault("path", p)
        seen.add(p)
        out.append(e)
    return out


def _key(kind: str, e: dict) -> str:
    return f"{'open' if kind == 'open' else 'reply'}:{e.get('path') or e.get('id')}"


def for_answer(a, session=None, today: date | None = None, root=None, events_fn=None) -> list[dict]:
    """At most two suggestions from what this answer found. playbooks/suggest.md, steps 1-5."""
    if a.route not in ROUTES:
        return []
    hidden = _hidden.get(_sid(session), set())
    meets, rest = [], []
    for e in _entries(a, root):
        if e.get("kind") == "canvas" and URL_RE.match(str(e.get("source") or "")):
            s = {"kind": "open", "line": say("suggest", "open", title=e.get("subject") or "the assignment"),
                 "button": say("suggest", "open_button"), "url": str(e["source"])}
            rest.append((s, e))
            continue
        if e.get("kind") != "email" or not e.get("sender_address"):
            continue
        first = first_name(e)
        if is_meeting(e) and _key("reply", e) not in hidden:
            m = meeting(e, events_fn)
            if m:
                s = ({"line": say("suggest", "free", when=m["when"], first=first),
                      "button": say("suggest", "free_button")} if m["free"] else
                     {"line": say("suggest", "busy", clash=m["clash"], when=m["when"]),
                      "button": say("suggest", "busy_button")})
                meets.append(({"kind": "meeting", "meeting": m, **s}, e))
                continue
        if (e.get("ask") or "").strip() or is_meeting(e):
            rest.append(({"kind": "reply", "line": say("suggest", "reply", first=first,
                                                         subject=e.get("subject") or "(no subject)"),
                          "button": say("suggest", "reply_button")}, e))
    out = []
    for s, e in meets + rest:
        k = _key(s["kind"], e)
        if k in hidden or any(x["key"] == k for x in out):
            continue
        s = {**s, "id": uuid.uuid4().hex[:10], "key": k, "entry": e, "session": _sid(session)}
        out.append(s)
        if len(out) == LIMIT:
            break
    for s in out:
        _offered[s["id"]] = s
    return out


def public(sugs: list[dict]) -> list[dict]:
    """What /ask sends the page: no entries, no paths."""
    return [{"id": s["id"], "line": s["line"], "button": s["button"], "kind": s["kind"]} for s in sugs or []]


def _hide(s: dict) -> None:
    _hidden.setdefault(s["session"], set()).add(s["key"])


def take(sid: str) -> dict | None:
    """The suggestion behind a click; it won't be offered again in that chat."""
    s = _offered.pop(sid, None)
    if s:
        _hide(s)
    return s


def dismiss(sid: str) -> bool:
    s = _offered.pop(sid, None)
    if s:
        _hide(s)
    return s is not None


def mark_drafted(session, e: dict) -> None:
    """A typed "draft a reply to X" hides that email's reply suggestion too."""
    _hidden.setdefault(_sid(session), set()).add(_key("reply", e))
