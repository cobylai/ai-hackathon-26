"""The rules engine: nudges(now, bank, calendar_events, state, config) -> [Nudge]. Pure and deterministic.

No clock, file, model or network access in here: `now` is passed in. Nudge text is built from code
templates plus the sender / subject / deadline phrase of an entry, shown as quoted data. Email text is
never an instruction: a nudge only displays, and its `source` names the entry it came from.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta

DEFAULT_CONFIG = {
    "kinds": {"deadline": True, "event": True, "ask": True},
    "max_per_hour": 3,
    "quiet_start": "22:00",
    "quiet_end": "08:00",
    "deadline_lead_minutes": 240,   # a deadline with a time is nudged this long before
    "event_lead_minutes": 30,
    "ask_after_days": 3,            # an ask this old and not yet past its deadline
    "ask_max_days": 14,
}


@dataclass(frozen=True)
class Nudge:
    id: str
    kind: str          # deadline | event | ask
    text: str
    source: str        # the bank entry path / source id, or the calendar event title + start
    due_at: str        # ISO local datetime the nudge is about

    def to_dict(self) -> dict:
        return asdict(self)


def _cfg(config) -> dict:
    out = {**DEFAULT_CONFIG, **(config or {})}
    out["kinds"] = {**DEFAULT_CONFIG["kinds"], **((config or {}).get("kinds") or {})}
    return out


def _nid(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]


def _clean(s, n=60) -> str:
    """One short plain line: control characters and newlines out, cut at n."""
    s = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", str(s or ""))).strip().strip('"')
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _hm(s: str) -> time:
    h, m = str(s).split(":")
    return time(int(h), int(m))


def in_quiet_hours(now: datetime, config=None) -> bool:
    c = _cfg(config)
    a, b, t = _hm(c["quiet_start"]), _hm(c["quiet_end"]), now.time()
    if a == b:
        return False
    return (a <= t < b) if a < b else (t >= a or t < b)


def _in(delta: timedelta) -> str:
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "now"
    if mins < 60:
        return f"in {mins} minute{'s' if mins != 1 else ''}"
    h, m = divmod(mins, 60)
    return f"in {h} hour{'s' if h != 1 else ''}" + (f" {m} min" if m else "")


def _clock(t: datetime) -> str:
    return t.strftime("%-I:%M%p").lower().replace(":00", "")


def _label(e: dict) -> str:
    return e.get("sender_name") or e.get("sender_address") or "someone"


def _src(e: dict) -> str:
    return str(e.get("path") or e.get("source") or e.get("id") or "unknown")


def _deadline_nudges(now, bank, c):
    out = []
    lead = timedelta(minutes=c["deadline_lead_minutes"])
    for e in bank:
        for d in e.get("deadlines") or []:
            if not d.get("date"):
                continue
            try:
                day = date.fromisoformat(d["date"])
            except ValueError:
                continue
            if d.get("time"):
                try:
                    due = datetime.combine(day, _hm(d["time"]))
                except ValueError:
                    continue
                if not (timedelta(0) <= due - now <= lead):
                    continue
                when = f"at {_clock(due)} ({_in(due - now)})"
            else:
                if day != now.date():
                    continue
                due = datetime.combine(day, time(23, 59))
                when = "today"
            what = _clean(d.get("phrase") or e.get("subject") or "something")
            out.append(Nudge(_nid("deadline", _src(e), d["date"], d.get("time"), d.get("phrase")), "deadline",
                             f'Due {when}: "{what}" ({_label(e)}).', _src(e), due.isoformat(timespec="minutes")))
    return out


def _event_nudges(now, events, c):
    out = []
    lead = timedelta(minutes=c["event_lead_minutes"])
    for ev in events or []:
        st = ev.get("start")
        if not isinstance(st, datetime) or ev.get("all_day"):
            continue
        if not (timedelta(0) <= st - now <= lead):
            continue
        title = _clean(ev.get("title") or "An event", 50)
        src = f'calendar: {title} {st.isoformat(timespec="minutes")}'
        out.append(Nudge(_nid("event", title, st.isoformat()), "event",
                         f"{title} starts {_in(st - now)} ({_clock(st)}).", src, st.isoformat(timespec="minutes")))
    return out


def _ask_nudges(now, bank, c):
    out = []
    for e in bank:
        if e.get("kind") != "email" or not (e.get("ask") or "").strip():
            continue
        try:
            sent = date.fromisoformat(str(e.get("sent_date") or "")[:10])
        except ValueError:
            continue
        age = (now.date() - sent).days
        if not (c["ask_after_days"] <= age <= c["ask_max_days"]):
            continue
        # not if every dated deadline on it has already passed (a stale ask)
        dls = [d["date"] for d in e.get("deadlines") or [] if d.get("date")]
        if dls and max(dls) < now.date().isoformat():
            continue
        out.append(Nudge(_nid("ask", _src(e)), "ask",
                         f"{_label(e)} asked you something {age} days ago; check whether it's still open.",
                         _src(e), datetime.combine(sent, time(9, 0)).isoformat(timespec="minutes")))
    return out


def nudges(now: datetime, bank: list, calendar_events: list, state: dict | None, config: dict | None = None) -> list:
    """What to say now. `bank` is a list of bank entries, `calendar_events` applecal.events dicts.
    `state` (proactive.state) holds dismissed / snoozed / shown. Nothing here writes anything."""
    c = _cfg(config)
    st = state or {}
    if in_quiet_hours(now, c):
        return []
    found = []
    if c["kinds"].get("deadline"):
        found += _deadline_nudges(now, bank or [], c)
    if c["kinds"].get("event"):
        found += _event_nudges(now, calendar_events, c)
    if c["kinds"].get("ask"):
        found += _ask_nudges(now, bank or [], c)
    dismissed = set(st.get("dismissed") or [])
    snoozed = st.get("snoozed") or {}
    shown = st.get("shown") or {}
    live = []
    for n in found:
        if n.id in dismissed:
            continue
        until = snoozed.get(n.id)
        if until and datetime.fromisoformat(until) > now:
            continue
        live.append(n)
    live.sort(key=lambda n: (n.due_at, n.kind, n.id))
    recent = sum(1 for t in shown.values() if timedelta(0) <= now - datetime.fromisoformat(t) < timedelta(hours=1))
    room = max(0, int(c["max_per_hour"]) - recent)
    out = []
    for n in live:
        if n.id in shown:        # already shown: stays on the strip until dismissed or past
            out.append(n)
        elif room > 0:
            out.append(n)
            room -= 1
    return sorted(out, key=lambda n: (n.due_at, n.kind, n.id))
