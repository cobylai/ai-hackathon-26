# Apple Calendar

Muse answers calendar questions from the macOS Calendar app, offline:

- "what's on my calendar tomorrow"
- "when is my next meeting"
- "what do I have this week"

`applecal/` reads events with `osascript` against Calendar.app. There's no network, no model call and no new dependency. iCloud sync happens before the demo; Calendar.app keeps a local copy, so it works with Wi-Fi off. (It's not named `calendar/` because that would shadow Python's own `calendar` module.)

## Setup

1. **Make the calendar.** In Calendar.app: File > New Calendar. Put it under **On My Mac** if that's offered, and name it **Muse demo**. Add made-up events (title, time, location). Muse reads only this calendar, so a video shows no real appointments.
   - Another name: set `MUSE_CALENDAR="Other name"` in the shell that runs Muse. The name is expected to change later.
2. **Allow access.** The first question makes macOS ask: **"Terminal" wants access to control "Calendar"** (or iTerm, VS Code: whichever app runs Python). Click **OK**.
   - If you clicked Don't Allow: System Settings > Privacy & Security > Automation > your terminal app > turn on **Calendar**. Muse then answers "I couldn't read Apple Calendar (no permission to control Calendar ...)".
3. Ask through either front end:

```bash
MUSE_BANK_DIR=~/muse-demo-bank uv run python -m reason
MUSE_BANK_DIR=~/muse-demo-bank uv run python -m reason.web
```

## The route

`reason/route.py: is_calendar` is checked after the due route and before the person route. It matches:

- `calendar` or `schedule`
- `my` / `any` (+ next/upcoming/first) + meeting(s) / event(s) / appointment(s)
- next/upcoming meeting/event/appointment, or "when is my next"
- "what do I have", "what am I doing", "am I busy/free"

"What did <name> say about the meeting" stays a person question. A question with "due" in it stays a due question.

**Ranges** come from the due route's own table (`route.due_range`): today, tomorrow, a weekday, next Friday, this week (on Sat/Sun, today through the coming Sunday), this weekend, next week, or a date. With no time phrase, the range is the next 7 days.

**"Next meeting/event"** is the first event starting after now. All-day events count from today. It looks 60 days ahead.

**The answer** is written by code:

```
On your calendar this week (Nov 14 to Nov 22):
- Sat Nov 14 10am–11am  Brunch with Ivy (Collegetown Bagels)
- Mon Nov 16 9:30am–10am  Team standup
Source: Apple Calendar (Muse demo)
```

For a single day the day is left off each line. If there are no events, it says "Nothing on your calendar <range>." If Calendar can't be read (no such calendar, no permission, a 20 s timeout), it says "I couldn't read Apple Calendar (<reason>)."

## Tests

```bash
uv run python -m unittest discover applecal/tests   # osascript mocked
uv run python -m unittest discover reason/tests     # events source mocked (test_calendar.py)
```

## Known gaps

- **Repeating events:** Calendar's AppleScript `whose start date` doesn't expand them, so a weekly event shows only on its first date. Use one-off events in the demo calendar.
- **Only one calendar** is read.
- **Calendar.app opens** in the background on the first question if it isn't running. The first answer can take a few seconds.
- Calendar events aren't folded into "what's due" answers. The due route is unchanged.
