"""Read events from Apple Calendar (Calendar.app) with osascript. No network, no new dependency.

    from applecal import events
    events(date(2026, 11, 15), date(2026, 11, 21))   # start and end days, both included
    -> [{"title", "start": datetime, "end": datetime, "location", "all_day"}], sorted by start

Which calendar: FLUX_CALENDAR if set, else the mode's default (bank/mode.py): "Flux demo" in
demo mode, the calendar you named in live mode (docs/calendar.md).
Default (FLUX_CALENDARS=demo): that one calendar, via osascript.
FLUX_CALENDARS=all: every real calendar via EventKit, repeats expanded (applecal/real.py, docs/agent/real-calendar.md).
Not named `calendar`, which would shadow Python's own `calendar` module.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time as _time
from datetime import date, datetime, time, timedelta

DEFAULT_CALENDAR = "Flux demo"  # the demo mode's calendar (bank/mode.py)
NO_CALENDAR = ('no calendar chosen for live mode; name yours with '
               'scripts/flux-mode live --calendar "<name>"')
TIMEOUT = 45  # a cold read is 5-6 s, slower when the Mac is busy


class CalendarError(RuntimeError):
    """Calendar.app could not be read (no access, no such calendar, timeout)."""


def calendar_key() -> str:
    """The calendar to read: FLUX_CALENDAR, else the mode's ("" when live mode has none yet)."""
    env = os.environ.get("FLUX_CALENDAR") or os.environ.get("MUSE_CALENDAR")
    if env:
        return env
    from bank import mode
    return mode.calendar()


def read_all() -> bool:
    """FLUX_CALENDARS=all reads the real calendars through EventKit; default (demo) is the one
    "Flux demo" calendar through osascript, exactly as before. Writes never follow this flag."""
    return (os.environ.get("FLUX_CALENDARS") or "demo").strip().lower() == "all"


def source_label(evs: list[dict] | None = None) -> str:
    """Calendar name(s) for a 'Source:' line: the write calendar in demo mode; in all mode the
    calendars the shown events came from (or 'all calendars' when none were shown)."""
    if not read_all():
        return calendar_name()
    names = sorted({e["calendar"] for e in evs or [] if e.get("calendar")}, key=str.lower)
    return ", ".join(names) or "all calendars"


def calendar_name() -> str:
    """For answers' source lines: the calendar's name."""
    return calendar_key() or "none chosen"


# Dates come back as numbers (iso()), so the Mac's date format doesn't matter.
# Fields are split by ASCII unit/record separators, which never appear in titles.
_SCRIPT = r'''
on p2(n)
  return text -2 thru -1 of ("0" & n)
end p2
on iso(t)
  return (year of t as integer as text) & "-" & my p2(month of t as integer) & "-" & my p2(day of t) & "T" & my p2(hours of t) & ":" & my p2(minutes of t)
end iso
on run argv
  set calName to item 1 of argv
  set hint to item 2 of argv as integer
  set US to (ASCII character 31)
  set RS to (ASCII character 30)
  set out to ""
  tell application "Calendar"
    -- Finding a calendar by name is slow (seconds), by index fast; so try the index hint first.
    set idx to 0
    if hint > 0 and hint <= (count of calendars) then
      if name of calendar hint is calName then set idx to hint
    end if
    if idx is 0 then
      set ns to name of calendars
      repeat with i from 1 to count of ns
        if item i of ns is calName then
          set idx to i
          exit repeat
        end if
      end repeat
    end if
    if idx is 0 then error "no calendar named " & calName number 4040
    set out to (idx as text) & RS
    -- One bulk fetch per property; a `whose` date filter costs ~1.5 s per property here,
    -- so all events are fetched and the range is filtered in Python.
    tell events of calendar idx to set {ts, ss, es, ls, als} to {summary, start date, end date, location, allday event}
  end tell
  repeat with i from 1 to count of ts
    set loc to item i of ls
    if loc is missing value then set loc to ""
    set ttl to item i of ts
    if ttl is missing value then set ttl to ""
    set out to out & ttl & US & my iso(item i of ss) & US & my iso(item i of es) & US & loc & US & (item i of als) & RS
  end repeat
  return out
end run
'''


_INDEX: dict[str, int] = {}  # calendar name -> its index in Calendar.app, per process


def parse(out: str) -> list[dict]:
    """osascript output -> event dicts sorted by start. The first record is the calendar index."""
    evs = []
    for rec in out.strip("\n").split("\x1e"):
        f = rec.split("\x1f")
        if len(f) != 5:
            continue
        evs.append({"title": f[0].strip(), "start": datetime.fromisoformat(f[1]),
                    "end": datetime.fromisoformat(f[2]), "location": f[3].strip(),
                    "all_day": f[4].strip() == "true"})
    return sorted(evs, key=lambda e: e["start"])


CACHE_SECONDS = 60
_CACHE: dict[str, tuple[float, list[dict]]] = {}  # calendar name -> (monotonic time, all events)


_LOCK = threading.Lock()  # a question asked during warm() waits for that read, not a second one


def warm(calendar: str | None = None) -> threading.Thread:
    """Read the calendar into the cache in the background, so the first calendar question
    doesn't wait for the cold read. Errors are ignored here; the question reports them."""
    def run():
        try:
            if read_all():
                events(date.today(), date.today() + timedelta(days=7))
            else:
                _fetch(calendar if calendar is not None else calendar_key())
        except CalendarError:
            pass
    t = threading.Thread(target=run, name="applecal-warm", daemon=True)
    t.start()
    return t


def _fetch(name: str) -> list[dict]:
    if not name:
        raise CalendarError(NO_CALENDAR)
    with _LOCK:
        return _fetch_locked(name)


def _fetch_locked(name: str) -> list[dict]:
    """Every event in the calendar. Calendar.app scripting takes ~3 s, so the result is kept
    for FLUX_CALENDAR_CACHE seconds (default 60): later questions answer at once."""
    ttl = float((os.environ.get("FLUX_CALENDAR_CACHE") or os.environ.get("MUSE_CALENDAR_CACHE")) or CACHE_SECONDS)
    hit = _CACHE.get(name)
    if hit and _time.monotonic() - hit[0] < ttl:
        return hit[1]
    try:
        p = subprocess.run(["osascript", "-", name, str(_INDEX.get(name, 0))], input=_SCRIPT,
                           capture_output=True, text=True, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CalendarError(f"osascript failed: {e}") from e
    if p.returncode != 0:
        msg = p.stderr.strip()
        if "no calendar named" in msg:
            raise CalendarError(f'no calendar named "{name}" in Calendar.app')
        if "-1743" in msg or "Not authorized" in msg:
            raise CalendarError("no permission to control Calendar (System Settings > "
                                "Privacy & Security > Automation)")
        if "-10004" in msg:
            raise CalendarError("Calendar refused the request; is Python running under sandbox-exec?")
        raise CalendarError(msg or "osascript failed")
    head = p.stdout.split("\x1e", 1)[0].strip()
    if head.isdigit():
        _INDEX[name] = int(head)
    evs = parse(p.stdout)
    _CACHE[name] = (_time.monotonic(), evs)
    return evs


def events(start: date, end: date, calendar: str | None = None) -> list[dict]:
    """Events overlapping the days start..end (both included). Raises CalendarError.
    With FLUX_CALENDARS=all (and no explicit calendar) reads the real calendars, repeats expanded."""
    if read_all() and not calendar:
        return _events_real(start, end)
    lo = datetime.combine(start, time.min)
    hi = datetime.combine(end + timedelta(days=1), time.min)
    return [e for e in _fetch(calendar if calendar is not None else calendar_key())
            if e["start"] < hi and (e["end"] > lo or (e["end"] == e["start"] and e["start"] >= lo))]


def _events_real(start: date, end: date) -> list[dict]:
    from . import real
    ttl = float((os.environ.get("FLUX_CALENDAR_CACHE") or os.environ.get("MUSE_CALENDAR_CACHE")) or CACHE_SECONDS)
    try:
        return real.read(start, end, ttl)
    except real.AccessDenied as e:
        raise CalendarError("no permission to read Calendar (System Settings > Privacy & "
                            "Security > Calendars > turn on the app that runs Flux)") from e
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        raise CalendarError(f"EventKit read failed: {e}") from e
