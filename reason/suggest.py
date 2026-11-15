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


def _own_event(ev: dict, e: dict, t: datetime) -> bool:
    """True when the overlapping event is this email's own: same title, same start.

    "Add to calendar" creates the event with the subject as the title at the proposed
    time, so the same thing coming back from the calendar is not a clash with itself.
    """
    return ((ev.get("title") or "").strip().lower() == (e.get("subject") or "").strip().lower()
            and ev.get("start") == t)


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
    if clash and _own_event(clash, e, t):
        return None  # already on the calendar because this email put it there (finding 12)
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
    k = "reply" if kind in ("reply", "meeting") else kind  # a meeting answer is a reply
    return f"{k}:{e.get('path') or e.get('id')}"


REMIND_ROUTES = ("due", "catchup")


def _calendar(e: dict, m: dict, today: date | None) -> dict | None:
    """'Add to calendar' for a free meeting time: worker 14's event_for, only if it is that time."""
    from . import computer
    ev = computer.event_for(e, today)
    if not ev or ev.get("all_day") or ev["start"].isoformat() != m["start"]:
        return None
    return {"kind": "calendar", "event": ev,
            "line": say("suggest", "calendar", title=ev["title"], when=computer.when_text(ev["start"])),
            "button": say("suggest", "calendar_button")}


def _remind(e: dict, today: date | None) -> dict | None:
    """'Remind me' for a due item: worker 14's reminder_for (alert 2 hours before, or 9am that day)."""
    from . import computer
    r = computer.reminder_for(e, "", today)
    if not r or (today and r["due"].date() < today):
        return None
    return {"kind": "remind", "reminder": r,
            "line": say("suggest", "remind", name=r["name"], when=computer.when_text(r["remind_at"])),
            "button": say("suggest", "remind_button")}


def _candidates(e: dict, route: str, today: date | None, hidden: set, events_fn) -> list[dict]:
    """This entry's suggestions, best first."""
    remind = route in REMIND_ROUTES
    if e.get("kind") == "canvas" and URL_RE.match(str(e.get("source") or "")):
        out = [{"kind": "open", "line": say("suggest", "open", title=e.get("subject") or "the assignment"),
                "button": say("suggest", "open_button"), "url": str(e["source"])}]
        return out + ([r] if remind and (r := _remind(e, today)) else [])
    if e.get("kind") != "email" or not e.get("sender_address"):
        return []
    first = first_name(e)
    if is_meeting(e) and _key("reply", e) not in hidden:
        m = meeting(e, events_fn)
        if m:
            if m["free"]:
                out = [{"kind": "meeting", "meeting": m, "line": say("suggest", "free", when=m["when"], first=first),
                        "button": say("suggest", "free_button")}]
                return out + ([c] if (c := _calendar(e, m, today)) else [])
            return [{"kind": "meeting", "meeting": m, "line": say("suggest", "busy", clash=m["clash"], when=m["when"]),
                     "button": say("suggest", "busy_button")}]
    out = []
    if (e.get("ask") or "").strip() or is_meeting(e):
        out.append({"kind": "reply", "line": say("suggest", "reply", first=first,
                                                 subject=e.get("subject") or "(no subject)"),
                    "button": say("suggest", "reply_button")})
    return out + ([r] if remind and (r := _remind(e, today)) else [])


def for_answer(a, session=None, today: date | None = None, root=None, events_fn=None) -> list[dict]:
    """At most two suggestions from what this answer found. playbooks/suggest.md, steps 1-5."""
    if a.route not in ROUTES:
        return []
    hidden = _hidden.get(_sid(session), set())
    entries = _entries(a, root)
    entries = [e for e in entries if is_meeting(e)] + [e for e in entries if not is_meeting(e)]
    out = []
    for e in entries:
        for s in _candidates(e, a.route, today, hidden, events_fn):
            k = _key(s["kind"], e)
            if k in hidden or any(x["key"] == k for x in out):
                continue
            out.append({**s, "id": uuid.uuid4().hex[:10], "key": k, "entry": e, "session": _sid(session)})
            if len(out) == LIMIT:
                break
        if len(out) == LIMIT:
            break
    for s in out:
        _offered[s["id"]] = s
    return out


def run(s: dict) -> str:
    """A clicked 'Add to calendar' or 'Remind me': worker 14's writes (block list, log). Never sends."""
    from . import computer
    try:
        if s["kind"] == "calendar":
            ev = s["event"]
            computer.add_event(ev)
            return say("suggest", "added_event", title=ev["title"], when=computer.when_text(ev["start"]))
        r = s["reminder"]
        computer.add_reminder(r)
        return say("suggest", "added_reminder", name=r["name"], when=computer.when_text(r["remind_at"]))
    except Exception as ex:
        return say("suggest", "add_failed", why=f"{type(ex).__name__}: {ex}")


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
