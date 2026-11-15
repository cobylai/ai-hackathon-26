"""The only writes Flux makes to the Mac: one calendar event, one reminder, and showing an event.

    add_event(title, start, end, location="", all_day=False)  -> into MUSE_CALENDAR ("Muse demo")
    add_reminder(name, due, remind_at, note="")              -> into the "Muse demo" Reminders list
    show_event(title, start)                                  -> Calendar shows that event

Called only after the user said yes to a preview (reason/act.py). Every value goes to
osascript as an argument, never pasted into the script, so text from an email can't
become AppleScript. Raises CalendarError (from applecal) on any failure.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime

from . import TIMEOUT, CalendarError, _CACHE, calendar_name

REMINDER_LIST = "Muse demo"

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

_SHOW_EVENT = _DATE + r'''
on run argv
  set {calName, ttl, s} to argv
  set t0 to my mkdate(s)
  tell application "Calendar"
    set hits to (events of calendar calName whose summary is ttl and start date >= t0 and start date < (t0 + 60))
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


def add_event(title: str, start: datetime, end: datetime, location: str = "",
              all_day: bool = False, calendar: str | None = None) -> None:
    name = calendar or calendar_name()
    _run(_ADD_EVENT, [name, title, _d(start), _d(end), location or "", "1" if all_day else "0"], "Calendar")
    _CACHE.pop(name, None)  # the next read sees the new event


def show_event(title: str, start: datetime, calendar: str | None = None) -> bool:
    """True when Calendar found and showed the event."""
    return _run(_SHOW_EVENT, [calendar or calendar_name(), title, _d(start)], "Calendar") == "OK"


def add_reminder(name: str, due: datetime | None, remind_at: datetime | None, note: str = "",
                 list_name: str | None = None) -> None:
    lst = list_name or os.environ.get("MUSE_REMINDERS") or REMINDER_LIST
    _run(_ADD_REMINDER, [lst, name, _d(due), _d(remind_at), note or ""], "Reminders")
