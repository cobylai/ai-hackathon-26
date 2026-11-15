"""Computer control that closes the gap between knowing and doing. playbooks/open.md,
schedule.md, setup.md. Code only: every value comes from a bank entry's stored fields or
from what the user said, never from text read on screen or in an email.

    open_email(entry)            the email in Apple Mail (test account), else its Gmail page
    event_for(entry)             {"title", "start", "end", "location", "all_day"} | None
    reminder_for(entry, when)    {"name", "due", "remind_at", "note"} | None
    add_event(ev) / add_reminder(r) / show_event(row_event)

Every action is logged in the partner's ~/.harness/actions.log and checked against his
block list and STOP file.
"""
from __future__ import annotations

import re
import subprocess
from datetime import date, datetime, time, timedelta

from bank import dates

TEST_ACCOUNT = "ilovelocalai@gmail.com"
MEETING_MINUTES = 60
REMIND_HOUR = 9

# Opens one message of the test account only; values are arguments, never script text.
_MAIL_OPEN = r'''
on run argv
  set {acct, addr, subj} to argv
  tell application "Mail"
    set hits to {}
    repeat with a in accounts
      if (email addresses of a) contains acct then
        set hits to (messages of mailbox "INBOX" of a whose sender contains addr and subject contains subj)
        exit repeat
      end if
    end repeat
    if hits is {} then return "NONE"
    open item 1 of hits
    activate
  end tell
  return "OK"
end run
'''


class Blocked(RuntimeError):
    pass


def _guard(app: str, action: str, label: str) -> None:
    """The partner's STOP file and block list, then one log line."""
    from harness.computer import policy
    if policy.stopped():
        raise Blocked(policy.STOPPED_MESSAGE)
    blocked = {a.strip().lower() for a in policy.load_policy()["block_apps"]}
    if app.strip().lower() in blocked:
        policy.log_action(app, action, label, policy.DENY)
        raise Blocked(f"{app} is on the block list")
    policy.log_action(app, action, label, policy.ALLOW)


# ---- email --------------------------------------------------------------------

def gmail_url(entry: dict) -> str | None:
    """The thread's Gmail page in the test account, for mail synced from real Gmail."""
    m = re.match(r"^gmail:([0-9a-f]{8,})(?:#\d+)?$", str(entry.get("source") or ""))
    return f"https://mail.google.com/mail/?authuser={TEST_ACCOUNT}#all/{m.group(1)}" if m else None


def mail_app_open(address: str, subject: str) -> bool:
    """Open the message in Apple Mail's test account. False when it isn't there."""
    _guard("Mail", "open_message", f"{address} | {subject}")
    subj = re.sub(r"^\s*((re|fwd?)\s*:\s*)+", "", subject or "", flags=re.I)[:60]
    try:
        p = subprocess.run(["osascript", "-", TEST_ACCOUNT, address or "", subj], input=_MAIL_OPEN,
                           capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return p.returncode == 0 and p.stdout.strip() == "OK"


# ---- dates from stored fields (bank date code, never the model) ---------------------

def _dated(entry: dict) -> list[tuple[date, str | None]]:
    """(date, "HH:MM" | None) from the entry's deadlines; else from date phrases in its ask
    and summary, resolved by bank.dates against the sent date."""
    out = []
    for d in entry.get("deadlines") or []:
        if d.get("date"):
            try:
                out.append((date.fromisoformat(str(d["date"])[:10]), d.get("time")))
            except ValueError:
                pass
    if out:
        return out
    try:
        sent = date.fromisoformat(str(entry.get("sent_date"))[:10])
    except ValueError:
        return []
    for text in (entry.get("ask"), entry.get("body"), entry.get("subject")):
        for phrase in dates.find_phrases(text or ""):
            d, t = dates.resolve(phrase, sent)
            if d:
                out.append((d, t))
    # "Wednesday, November 18 at 2pm" comes back as two phrases: keep one per day, with its time.
    best: dict[date, str | None] = {}
    for d, t in out:
        best[d] = best.get(d) or t
    return list(best.items())


_PLACE = re.compile(r"\b(?:in|at)\s+((?:[A-Z][\w'.\-]*\s+){0,3}(?:Hall|Room|Building|Library|Center|"
                    r"Centre|Lab|Auditorium|Chapel|Gym|Cafe|Café)(?:\s+(?:[Rr]oom\s+)?\d+[A-Z]?)?)")


def place(entry: dict) -> str:
    for text in (entry.get("ask"), entry.get("body"), entry.get("subject")):
        m = _PLACE.search(text or "")
        if m:
            return m.group(1).strip()
    return ""


def event_for(entry: dict, today: date | None = None) -> dict | None:
    """The event to add: subject as title, the first stored date (upcoming first), one hour."""
    ds = _dated(entry)
    if not ds:
        return None
    if today:
        ds = sorted(ds, key=lambda x: (x[0] < today, x[0]))
    d, t = ds[0]
    title = (entry.get("subject") or "").strip() or "Event"
    if t:
        h, m = (int(x) for x in t.split(":"))
        start = datetime.combine(d, time(h, m))
        return {"title": title, "start": start, "end": start + timedelta(minutes=MEETING_MINUTES),
                "location": place(entry), "all_day": False}
    start = datetime.combine(d, time.min)
    return {"title": title, "start": start, "end": start + timedelta(days=1),
            "location": place(entry), "all_day": True}


def reminder_for(entry: dict, when: str = "", today: date | None = None) -> dict | None:
    """Due = the stored deadline. Alert: the day before at 9am if asked, else 2 hours
    before a timed deadline, else 9am on the day."""
    ds = _dated(entry)
    if not ds:
        return None
    if today:
        ds = sorted(ds, key=lambda x: (x[0] < today, x[0]))
    d, t = ds[0]
    due = datetime.combine(d, time(*(int(x) for x in t.split(":")))) if t else datetime.combine(d, time(REMIND_HOUR))
    if re.search(r"day before|night before", when or "", re.I):
        remind = datetime.combine(d - timedelta(days=1), time(REMIND_HOUR))
    elif t:
        remind = due - timedelta(hours=2)
    else:
        remind = datetime.combine(d, time(REMIND_HOUR))
    name = (entry.get("ask") or entry.get("subject") or "").strip().rstrip(".") or "Reminder"
    who = entry.get("sender_name") or entry.get("sender_address") or ""
    note = f"From {who}: {entry.get('subject') or ''}".strip() if who else (entry.get("subject") or "")
    return {"name": name, "due": due, "remind_at": remind, "note": note}


# ---- the writes (after a yes) ----------------------------------------------------

def add_event(ev: dict) -> None:
    from applecal import write
    _guard("Calendar", "add_event", f"{ev['title']} | {ev['start']:%Y-%m-%d %H:%M}")
    write.add_event(ev["title"], ev["start"], ev["end"], ev.get("location") or "", ev.get("all_day", False))


def add_reminder(r: dict) -> None:
    from applecal import write
    _guard("Reminders", "add_reminder", f"{r['name']} | {r['remind_at']:%Y-%m-%d %H:%M}")
    write.add_reminder(r["name"], r["due"], r["remind_at"], r.get("note") or "")


def show_event(ev: dict) -> bool:
    from applecal import write
    _guard("Calendar", "show_event", f"{ev.get('title')} | {ev.get('start')}")
    start = ev["start"] if isinstance(ev["start"], datetime) else datetime.fromisoformat(str(ev["start"]))
    return write.show_event(ev.get("title") or "", start)


def when_text(dt: datetime, all_day: bool = False) -> str:
    day = f"{dt:%a} {dt:%b} {dt.day}"
    if all_day:
        return f"{day} (all day)"
    h = dt.hour % 12 or 12
    return f"{day} {h}{':%02d' % dt.minute if dt.minute else ''}{'am' if dt.hour < 12 else 'pm'}"
