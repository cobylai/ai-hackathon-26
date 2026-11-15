"""Read events from Apple Calendar (Calendar.app) with osascript. No network, no new dependency.

    from applecal import events
    events(date(2026, 11, 15), date(2026, 11, 21))   # start and end days, both included
    -> [{"title", "start": datetime, "end": datetime, "location", "all_day"}], sorted by start

Only one calendar is read: MUSE_CALENDAR, default "Muse demo" (docs/calendar.md).
Not named `calendar`, which would shadow Python's own `calendar` module.
"""
from __future__ import annotations

import os
import subprocess
from datetime import date, datetime, timedelta

DEFAULT_CALENDAR = "Muse demo"
TIMEOUT = 20


class CalendarError(RuntimeError):
    """Calendar.app could not be read (no access, no such calendar, timeout)."""


def calendar_name() -> str:
    return os.environ.get("MUSE_CALENDAR") or DEFAULT_CALENDAR


# Dates are built from numbers, not strings, so the Mac's date format doesn't matter.
# Fields are split by ASCII unit/record separators, which never appear in titles.
_SCRIPT = r'''
on mk(y, m, d)
  set t to current date
  set day of t to 1
  set year of t to y
  set month of t to m
  set day of t to d
  set time of t to 0
  return t
end mk
on p2(n)
  return text -2 thru -1 of ("0" & n)
end p2
on iso(t)
  return (year of t as integer as text) & "-" & my p2(month of t as integer) & "-" & my p2(day of t) & "T" & my p2(hours of t) & ":" & my p2(minutes of t)
end iso
on run argv
  set calName to item 1 of argv
  set d0 to my mk(item 2 of argv as integer, item 3 of argv as integer, item 4 of argv as integer)
  set d1 to my mk(item 5 of argv as integer, item 6 of argv as integer, item 7 of argv as integer)
  set US to (ASCII character 31)
  set RS to (ASCII character 30)
  set out to ""
  tell application "Calendar"
    if not (exists calendar calName) then error "no calendar named " & calName number 4040
    set evs to (every event of calendar calName whose start date < d1 and end date > d0)
    repeat with e in evs
      set loc to location of e
      if loc is missing value then set loc to ""
      set out to out & (summary of e) & US & my iso(start date of e) & US & my iso(end date of e) & US & loc & US & (allday event of e) & RS
    end repeat
  end tell
  return out
end run
'''


def parse(out: str) -> list[dict]:
    """osascript output -> event dicts sorted by start."""
    evs = []
    for rec in out.strip("\n").split("\x1e"):
        f = rec.split("\x1f")
        if len(f) != 5:
            continue
        evs.append({"title": f[0].strip(), "start": datetime.fromisoformat(f[1]),
                    "end": datetime.fromisoformat(f[2]), "location": f[3].strip(),
                    "all_day": f[4].strip() == "true"})
    return sorted(evs, key=lambda e: e["start"])


def events(start: date, end: date, calendar: str | None = None) -> list[dict]:
    """Events overlapping the days start..end (both included). Raises CalendarError."""
    stop = end + timedelta(days=1)
    args = [calendar or calendar_name(), start.year, start.month, start.day,
            stop.year, stop.month, stop.day]
    try:
        p = subprocess.run(["osascript", "-", *map(str, args)], input=_SCRIPT,
                           capture_output=True, text=True, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CalendarError(f"osascript failed: {e}") from e
    if p.returncode != 0:
        msg = p.stderr.strip()
        if "no calendar named" in msg:
            raise CalendarError(f'no calendar named "{args[0]}" in Calendar.app')
        if "-1743" in msg or "Not authorized" in msg:
            raise CalendarError("no permission to control Calendar (System Settings > "
                                "Privacy & Security > Automation)")
        raise CalendarError(msg or "osascript failed")
    return parse(p.stdout)
