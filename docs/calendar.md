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

## Speed

Calendar.app's scripting is slow: about 3 s to read one calendar, and 5–6 s for the first read after launch. A `whose` date filter costs about 1.5 s for each property it fetches, so `applecal` fetches every event of the calendar in one bulk call and filters the dates in Python. It keeps the result for 60 s (`MUSE_CALENDAR_CACHE=<seconds>`), so only the first calendar question in a minute waits. An event you add in Calendar shows up within 60 s.

## Permission and the offline proof

- **Reading Calendar needs a one-time Automation allow.** The first calendar question asks "<terminal app>" wants access to control "Calendar"; click OK. Without it, every calendar answer is the "couldn't read Apple Calendar" message. Each terminal app (Terminal, iTerm, VS Code) asks separately.
- **Calendar can't be read from a process under the network-blocking sandbox.** Under `sandbox-exec` with network denied (what the voice runs used), Calendar refuses the Apple events with -10004. So the `sandbox-exec` network-blocked check doesn't work for the calendar route. "Calendar works with the network off" is shown only by the real Wi-Fi-off run (Antranig's test). The run below blocks sockets inside the Python process instead, which doesn't cover the `osascript` child or Calendar.app.

## Live run (2026-11-14 23:46, Sat; network blocked in the process, localhost allowed)

The demo calendar holds 7 made-up events. The network block is `reason.live_check.block_network()` in the Python process. **Not `sandbox-exec`**: under it, Calendar refuses Apple events (-10004).

| Front end | Question | Answer | Seconds |
|---|---|---|---|
| `python -m reason` | what's on my calendar tomorrow | Sun Nov 15: 9am–10am Demo practice run (Duffield Atrium); noon–1:30pm Hackathon judging (Duffield Atrium) | 5.9 |
| `python -m reason` | when is my next meeting | Sun Nov 15 9am–10am Demo practice run (the 6pm dinner had passed) | 0.0 |
| `python -m reason` | what do I have this week | 6 events, Sat Nov 14 to Thu Nov 19 (Nov 14 to Nov 22) | 0.0 |
| `python -m reason` | am I free Monday | Mon Nov 16: 9:30am–10am Team standup (Rhodes 402) | 0.0 |
| `python -m reason` | what's due this week | the bank's due list, unchanged (route due) | 0.0 |
| `reason.web` `/ask` | What's on my calendar tomorrow? | same 2 events | 5.19 |
| `reason.web` `/ask` | When is my next meeting? | Demo practice run, Sun 9am | 0.0 |
| `reason.web` `/ask` | What do I have this week? | same 6 events | 0.0 |
| `reason.web` `/ask` | Am I free Monday? | Team standup 9:30am | 0.0 |

## Tests

```bash
uv run python -m unittest discover applecal/tests   # osascript mocked
uv run python -m unittest discover reason/tests     # events source mocked (test_calendar.py)
```

## Known gaps

- **Repeating events:** Calendar's AppleScript returns each repeating event once, at its first date, and doesn't expand the repeats. Use one-off events in the demo calendar.
- **Only one calendar** is read.
- **Calendar.app opens** in the background on the first question if it isn't running. The first answer takes about 5 s.
- **`sandbox-exec` breaks it** (-10004). Use the per-process block, or really turn Wi-Fi off.
- **Wi-Fi was not actually turned off** in the live run.
- **Voice** wasn't tried. Calendar questions have no names in them, so they should come through Whisper fine.
- Calendar events aren't folded into "what's due" answers. The due route is unchanged.
