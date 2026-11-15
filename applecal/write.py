"""The only writes Flux makes to the Mac: one calendar event, one reminder, and showing an event.

    add_event(title, start, end, location="", all_day=False)  -> into FLUX_CALENDAR ("Flux demo")
    add_reminder(name, due, remind_at, note="")              -> into the "Flux demo" Reminders list
    show_event(title, start)                                  -> Calendar shows that event

Called only after the user said yes to a preview (reason/act.py). Every value goes to
osascript as an argument, never pasted into the script, so text from an email can't
become AppleScript. Raises CalendarError (from applecal) on any failure.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime

from . import TIMEOUT, CalendarError, _CACHE, calendar_key

REMINDER_LIST = "Flux demo"  # the demo mode's list (bank/mode.py)

# A date is passed as "Y M D h m" and built here, so the Mac's date format doesn't matter.
_DATE = r'''
on mkdate(s)
  set AppleScript's text item delimiters to " "
  set p to text items of s
  set AppleScript's text item delimiters to ""
  set d to current date
  set day of d to 1
  set year of d to (item 1 of p) as integer
  set month of d to (item 2 of p) as integer
  set day of d to (item 3 of p) as integer
  set time of d to ((item 4 of p) as integer) * 3600 + ((item 5 of p) as integer) * 60
  return d
end mkdate
'''

_ADD_EVENT = _DATE + r'''
on run argv
  set {calName, ttl, s, e, loc, allDay} to argv
  tell application "Calendar"
    if not (exists calendar calName) then error "no calendar named " & calName number 4040
    tell calendar calName
      set ev to make new event at end with properties {summary:ttl, start date:my mkdate(s), end date:my mkdate(e), location:loc, allday event:(allDay is "1")}
    end tell
  end tell
  return "OK"
end run
'''

_WRITABLE = r'''
on run argv
  tell application "Calendar"
    repeat with c in calendars
      try
        if writable of c then return name of c
      end try
    end repeat
  end tell
  error "no writable calendar" number 4040
end run
'''

_DEFAULT_LIST = r'''
on run argv
  tell application "Reminders" to return name of default list
end run
'''

_SHOW_EVENT = _DATE + r'''
on run argv
  set {calName, ttl, s} to argv
  set t0 to my mkdate(s)
  tell application "Calendar"
    set hits to {}
    if calName is "" then
      repeat with c in calendars
        try
          set hits to hits & (events of c whose summary is ttl and start date >= t0 and start date < (t0 + 60))
        end try
      end repeat
    else
      set hits to (events of calendar calName whose summary is ttl and start date >= t0 and start date < (t0 + 60))
    end if
    if hits is {} then return "NONE"
    show item 1 of hits
    activate
  end tell
  return "OK"
end run
'''

_ADD_REMINDER = _DATE + r'''
on run argv
  set {listName, nm, dueS, remS, note} to argv
  tell application "Reminders"
    if not (exists list listName) then make new list with properties {name:listName}
    tell list listName
      set props to {name:nm, body:note}
      set r to make new reminder at end with properties props
      if dueS is not "" then set due date of r to my mkdate(dueS)
      if remS is not "" then set remind me date of r to my mkdate(remS)
    end tell
  end tell
  return "OK"
end run
'''


def _d(dt: datetime | None) -> str:
    return "" if dt is None else f"{dt.year} {dt.month} {dt.day} {dt.hour} {dt.minute}"


def _run(script: str, args: list[str], app: str) -> str:
    try:
        p = subprocess.run(["osascript", "-", *args], input=script, capture_output=True,
                           text=True, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CalendarError(f"osascript failed: {e}") from e
    if p.returncode != 0:
        msg = p.stderr.strip()
        if "-1743" in msg or "Not authorized" in msg:
            raise CalendarError(f"no permission to control {app} (System Settings > "
                                "Privacy & Security > Automation)")
        if "no calendar named" in msg:
            raise CalendarError(f'no calendar named "{args[0]}" in Calendar.app')
        if "-10004" in msg:
            raise CalendarError(f"{app} refused the request; is Python running under sandbox-exec?")
        raise CalendarError(msg or "osascript failed")
    return p.stdout.strip()


_TARGETS: dict[str, str] = {}  # per process: the resolved write calendar and reminders list


def target_calendar() -> str:
    """The calendar new events go into: the configured one, or in live mode with none
    configured, the first writable calendar on this Mac."""
    key = calendar_key()
    if key:
        return key
    if "cal" not in _TARGETS:
        _TARGETS["cal"] = _run(_WRITABLE, [], "Calendar")
    return _TARGETS["cal"]


def reminder_list() -> str:
    """The Reminders list: FLUX_REMINDERS, else the mode's (demo "Flux demo"; live the default list)."""
    env = os.environ.get("FLUX_REMINDERS") or os.environ.get("MUSE_REMINDERS")
    if env:
        return env
    from bank import mode
    name = mode.reminders()
    if name:
        return name
    if "rem" not in _TARGETS:
        _TARGETS["rem"] = _run(_DEFAULT_LIST, [], "Reminders")
    return _TARGETS["rem"]


def add_event(title: str, start: datetime, end: datetime, location: str = "",
              all_day: bool = False, calendar: str | None = None) -> None:
    name = calendar or target_calendar()
    _run(_ADD_EVENT, [name, title, _d(start), _d(end), location or "", "1" if all_day else "0"], "Calendar")
    _CACHE.pop(name, None)  # the next read sees the new event
    _CACHE.pop(calendar_key(), None)


def show_event(title: str, start: datetime, calendar: str | None = None) -> bool:
    """True when Calendar found and showed the event."""
    return _run(_SHOW_EVENT, [calendar if calendar is not None else calendar_key(), title, _d(start)], "Calendar") == "OK"


def add_reminder(name: str, due: datetime | None, remind_at: datetime | None, note: str = "",
                 list_name: str | None = None) -> None:
    lst = list_name or reminder_list()
    _run(_ADD_REMINDER, [lst, name, _d(due), _d(remind_at), note or ""], "Reminders")
