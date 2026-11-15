"""Catch me up: the day in one answer. Code only, no model call. playbooks/catchup.md.

Three sections, each from a function that already exists:
  today's calendar   applecal.events(today, today)
  due soon           bank.due(today, today + 2), mail and Canvas together
  recent asks        bank email entries with an ask, sent in the last 7 days
If the calendar can't be read, its line says why and the other two still answer.
"""
from __future__ import annotations

from datetime import date, timedelta

import bank
from bank import store

from . import playbook, route
from .playbook import say

DUE_DAYS = 2      # today plus the next two days
ASK_DAYS = 7      # mail received today and the 6 days before
ASK_LIMIT = 8


def is_catchup(question: str) -> bool:
    return bool(playbook.trigger("catchup", "catchup").search(question or ""))


def _calendar(today: date, events_fn) -> list[str]:
    import applecal
    from .answer import _event_line
    try:
        evs = (events_fn or applecal.events)(today, today)
    except applecal.CalendarError as e:
        return [say("catchup", "cal_error", error=e)]
    lines = [say("catchup", "cal_head", day=route._day(today))]
    lines += [_event_line(e, False) for e in evs] or [say("catchup", "cal_none")]
    return lines + [say("calendar", "source", calendar=applecal.calendar_name())]


def _due(today: date, root) -> tuple[list[str], list[str]]:
    from .answer import _time, source_label
    end = today + timedelta(days=DUE_DAYS)
    rows = bank.due(today, end, root=root)
    lines = [say("catchup", "due_head", end=route._day(end))]
    for r in rows:
        e = r["entry"]
        what = (e.get("ask") or e.get("body") or e.get("subject") or "").strip().rstrip(".")
        when = " ".join(x for x in (route._day(date.fromisoformat(r["date"])), _time(r.get("time"))) if x)
        lines.append(say("catchup", "due_row", when=when, what=what, source=source_label(e)))
    if not rows:
        lines.append(say("catchup", "due_none"))
    lines.append(say("catchup", "due_source"))
    return lines, [r["entry"]["path"] for r in rows]


def _asks(today: date, root) -> tuple[list[str], list[str]]:
    from .answer import _short_date
    lo = (today - timedelta(days=ASK_DAYS - 1)).isoformat()
    hits = [e for e in store.all_entries(root)
            if e.get("kind") == "email" and (e.get("ask") or "").strip()
            and lo <= str(e.get("sent_date") or "")[:10] <= today.isoformat()]
    hits.sort(key=lambda e: e.get("sent_date") or "", reverse=True)
    lines = [say("catchup", "ask_head", days=ASK_DAYS)]
    for e in hits[:ASK_LIMIT]:
        who = e.get("sender_name") or e.get("sender_address") or "unknown sender"
        lines.append(say("catchup", "ask_row", date=_short_date(e.get("sent_date")), who=who,
                         ask=e["ask"].strip().rstrip(".")))
    if len(hits) > ASK_LIMIT:
        lines.append(say("catchup", "ask_more", n=len(hits) - ASK_LIMIT))
    if not hits:
        lines.append(say("catchup", "ask_none", days=ASK_DAYS))
    lines.append(say("catchup", "ask_source", days=ASK_DAYS))
    return lines, [e["path"] for e in hits[:ASK_LIMIT]]


def handle(q: str, today: date, root, events_fn=None):
    """An Answer for a catch-up question, or None if it isn't one."""
    if not is_catchup(q):
        return None
    from .answer import Answer
    cal = _calendar(today, events_fn)
    due, due_paths = _due(today, root)
    asks, ask_paths = _asks(today, root)
    text = "\n\n".join("\n".join(s) for s in (cal, due, asks))
    return Answer(text, "catchup", list(dict.fromkeys(due_paths + ask_paths)))
