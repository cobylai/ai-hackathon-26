"""The demo week on the "Flux demo" calendar, and a reset that rewrites it (brief DEMO).

    uv run python scripts/demo/demo_calendar.py reset [--today YYYY-MM-DD]   # wipe + write the week
    uv run python scripts/demo/demo_calendar.py show  [--today YYYY-MM-DD]   # print the week, no writes

Every event here is made up. reset deletes every event in the calendar named
"Flux demo" and every reminder in the Reminders list "Flux demo", then writes the
week below from today to today+6 (plus one all-day event the week after). It
refuses any other calendar or list name, so a real calendar is never touched.

Fixed points the video and the playbook checks lean on:
  Tue 2-4pm   "CHEM 1583 Lab"  (Nina's Tuesday 2:30 clashes; "my lab is Tuesdays at 2")
  Wed 1:30-3:30pm "Lab"        (Greta's Wednesday 2pm clashes; playbooks/suggest.md)
  Thu 3pm and Thu 7pm free     (Felix's "Thursday at 3", Milo's band practice)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DEMO = "Flux demo"
TODAY = date(2026, 11, 15)

# weekday (Mon=0) -> [(title, start, end, location)]
WEEK = {
    0: [("Team standup", "09:30", "10:00", "Rhodes 402"),
        ("HIST 2147 lecture", "10:10", "11:00", "Goldwin Smith 132"),
        ("MATH 2938 lecture", "13:25", "14:15", "Malott 251"),
        ("Robotics club", "19:00", "20:30", "Upson 142")],
    1: [("INFO 3361 lecture", "10:10", "11:25", "Gates G01"),
        ("Office hours with Prof. Reyes", "11:40", "12:30", "Upson 225"),
        ("CHEM 1583 Lab", "14:00", "16:00", "Baker Lab 150")],
    2: [("HIST 2147 lecture", "10:10", "11:00", "Goldwin Smith 132"),
        ("Lab", "13:30", "15:30", "Baker Lab 200"),
        ("Outing club meeting", "17:30", "18:30", "Willard Straight 409")],
    3: [("INFO 3361 lecture", "10:10", "11:25", "Gates G01"),
        ("CHEM 1583 lecture", "12:20", "13:10", "Baker Lab 200"),
        ("Dentist appointment", "16:00", "17:00", "Ithaca Dental")],
    4: [("HIST 2147 lecture", "10:10", "11:00", "Goldwin Smith 132"),
        ("MATH 2938 lecture", "13:25", "14:15", "Malott 251"),
        ("Dinner with Felix", "18:00", "19:00", "Collegetown Bagels")],
    5: [("Garden club workday", "11:00", "13:00", "Community garden"),
        ("Career fair prep", "15:00", "16:00", "Barnes Hall")],
    6: [("Demo practice run", "09:00", "10:00", "Duffield Atrium"),
        ("Hackathon judging", "12:00", "13:30", "Duffield Atrium")],
}


def week(today: date | None = None) -> list[dict]:
    """The events from today to today+6, plus 'Thanksgiving break' on the next Wednesday after."""
    today = today or TODAY
    out = []
    for i in range(7):
        d = today + timedelta(days=i)
        for title, s, e, loc in WEEK[d.weekday()]:
            out.append({"title": title, "location": loc, "all_day": False,
                        "start": datetime.combine(d, time.fromisoformat(s)),
                        "end": datetime.combine(d, time.fromisoformat(e))})
    wed = today + timedelta(days=7)
    wed += timedelta(days=(2 - wed.weekday()) % 7)
    out.append({"title": "Thanksgiving break", "location": "", "all_day": True,
                "start": datetime.combine(wed, time(0, 0)), "end": datetime.combine(wed, time(23, 59))})
    return out


_WIPE_CAL = r'''
on run argv
  set calName to item 1 of argv
  tell application "Calendar"
    if not (exists calendar calName) then error "no calendar named " & calName number 4040
    delete every event of calendar calName
    return (count of events of calendar calName) as text
  end tell
end run
'''

_WIPE_REM = r'''
on run argv
  set listName to item 1 of argv
  tell application "Reminders"
    if not (exists list listName) then return "OK"
    delete every reminder of list listName
  end tell
  return "OK"
end run
'''


def _refuse(name: str) -> None:
    if name != DEMO:
        raise SystemExit(f'refusing: only the "{DEMO}" calendar and list are reset, not "{name}"')


def _osa(script: str, args: list[str], timeout: int = 300) -> str:
    """osascript with a long timeout: deleting a few dozen events can take over a minute."""
    import subprocess
    p = subprocess.run(["osascript", "-", *args], input=script, capture_output=True, text=True,
                       timeout=timeout)
    if p.returncode != 0:
        raise SystemExit(f"osascript failed: {p.stderr.strip()}")
    return p.stdout.strip()


def reset(today: date | None = None, calendar: str = DEMO, reminders: str = DEMO) -> int:
    from applecal import _CACHE
    from applecal.write import add_event
    _refuse(calendar)
    _refuse(reminders)
    for _ in range(3):  # until the calendar is really empty
        if _osa(_WIPE_CAL, [calendar]) == "0":
            break
    else:
        raise SystemExit(f'"{calendar}" still has events after three wipes')
    _osa(_WIPE_REM, [reminders])
    evs = week(today)
    for ev in evs:
        add_event(ev["title"], ev["start"], ev["end"], ev["location"], ev["all_day"], calendar=calendar)
    _CACHE.pop(calendar, None)
    return len(evs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts/demo/demo_calendar.py")
    ap.add_argument("mode", choices=("reset", "show"))
    ap.add_argument("--today", type=date.fromisoformat, default=TODAY)
    a = ap.parse_args(argv)
    if a.mode == "show":
        for ev in week(a.today):
            print(f"{ev['start']:%a %b %d %H:%M}-{ev['end']:%H:%M}  {ev['title']}  ({ev['location']})")
        return 0
    n = reset(a.today)
    print(f'"{DEMO}": wiped, wrote {n} events; "{DEMO}" reminders list emptied')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
