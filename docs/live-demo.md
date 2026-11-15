# Live demo: Flux on real data

Flux has two states that never mix:

| | Demo (staged, for the video) | Live (your data) |
|---|---|---|
| Bank | `~/flux-demo-bank` (sample mail and sample coursework) | `~/flux-bank` (what Sync mail and the web route filed) |
| Calendar | "Flux demo" | the one calendar you name ("Flux live" for the live demo) |
| Reminders | the "Flux demo" list | your default list |
| Status | the window's status line and the menu say **Demo data** | **Your data** |

Switch with one command, then relaunch Flux (or restart `python -m reason.web`). Switching only changes the setting in `~/.flux/mode`; nothing is copied between the two states.

```bash
scripts/flux-mode demo
scripts/flux-mode live --calendar "Home"     # name your calendar once; it's kept in ~/.flux/calendar
scripts/flux-mode                            # print the current mode
```

`FLUX_MODE`, `FLUX_BANK_DIR`, `FLUX_CALENDAR`, `FLUX_REMINDERS` and `FLUX_ACCOUNT` (the one mail account Flux may draft in or open mail from; default the test account) still override the mode for one shell.

Live mode reads **one** calendar. Reading every calendar on a Mac with many of them took over a minute per question, so there's no "all calendars" option.

## The live calendar: "Flux live"

A new calendar used only for the live demo: not "Flux demo", and none of the Mac's own calendars. Flux reads only the one calendar it's set to, so every other calendar stays out of its answers. To hide the others in Calendar.app too, untick them in the sidebar.

Create it once (On My Mac, so it never syncs anywhere), then point live mode at it:

```bash
osascript -e 'tell application "Calendar" to make new calendar with properties {name:"Flux live"}'
scripts/flux-mode live --calendar "Flux live"
```

Then add three or four real events you're happy to show (this week, with times and places), in Calendar.app.

## Before going offline (online, once)

1. `scripts/flux-mode live --calendar "Flux live"`, then relaunch Flux. The menu's first line and the window's status line say **Your data**.
2. **Mail:** menu → **Sync mail** (or `FLUX_BANK_DIR=~/flux-bank uv run python scripts/sync_email.py 7`). It reads the **test Gmail account** signed in on the hidden browser's profile, the last 7 days, at most 10 threads per sync, read-only. No personal inbox.
3. **Confirm the bank:** click the status line, or `find ~/flux-bank -name "*.md" ! -name index.md | wc -l`. On 2026-11-15 after one sync it held **9 emails** from 4 senders.
4. **Coursework:** there is no live Canvas path (see "What doesn't work live"), so the live run leaves coursework questions out. No staged pages go into the live bank.
5. **Calendar:** the "Flux live" events are in Calendar.app (local, so nothing to sync).
6. **Web answers you want offline:** ask them online and say yes to "save that to your notes".
7. **Permissions already granted:** microphone, Accessibility (Fn-Space), and Automation for Calendar, Reminders and Mail. Menu → **Check setup** lists any that are missing.
8. **Launch once with voice** so the speech model is loaded (the first launch on a Mac compiles for several minutes). Ask one question by voice.
9. Bonsai is running on 127.0.0.1:8080 (Flux starts it).
10. Turn **Wi-Fi off**.

### Mail the test account still needs

The 9 emails cover a plain ask (ramen recommendation, chem lab notes, potluck dessert), deadlines (HIST 2290 essay Mon 11:59pm, housing form Fri noon, robotics parts order Wed 5pm) and a bill. Two gaps:

- **No email proposes a meeting time,** so the "You're free … Draft a yes?" suggestion can't show.
- **Bill amounts:** the bank's summary of a bill drops the amount, so "How much is my bill?" misses. **Bill amounts are not in the live run.** A bill email can still be sent; it shows up as plain mail in catch me up and due.

Send these to the test account, then Sync mail again:

| From | Subject | Body |
|---|---|---|
| Antranig | Study session Thursday? | Are you free Thursday at 4pm to go over the chem lab? We could meet in the library. |
| Coby | Phone bill: $42.18 due Friday | Your phone bill is $42.18 and it's due Friday, November 20. Pay it in the app. |

**Names by voice:** the senders are "Coby Lai" and "Antranig Baghdassarian". Whisper has heard "Coby" as "Kobe", and "Antranig" hasn't been tried. Type the person questions in the live run, or try each name by voice once before.

## Questions (from what's really in the live bank, 2026-11-15)

**Not in the live run:** bill amounts and coursework (no live Canvas path). Every row below uses only mail, the calendar and notes.

| Capability | Ask | Expect |
|---|---|---|
| Chat | "Hey, can you hear me okay?" | a short reply, no search |
| Catch me up | "Catch me up" | Flux live's events today, due through Tuesday, asks from the last 7 days |
| Due | "What's due this week?" → "and next week?" → "the first one" → "who sent that?" | the essay (Mon 11:59pm), robotics parts (Wed 5pm), housing form (Fri noon), the potluck (Sun 6pm) |
| Open it | "open it" → yes | the email opens in Mail (test account) |
| Person | "What did Antranig ask me?" → "and Coby?" | lab notes, potluck dessert; then essay, housing, ramen, bill |
| Everyone | "What did everyone ask me?" | every open ask |
| People | "Who is Antranig?" | his newest emails |
| Calendar | "What's on my calendar this week?", "When is my next meeting?", "Am I free Thursday?" | from Flux live |
| Memory | "Remember that my lab is Tuesdays at 2." → "What do you know about me?" → "When is my lab?" → "Forget that" | saved, listed, answered from the note, removed |
| Drafts | "Draft a reply to Antranig" → Open in Mail (close it unsent) | a draft from his newest ask |
| Suggestion (after the study-session email) | "What did Antranig ask me?" | "You're free Thursday … Draft a yes to Antranig?" |
| Add to calendar | "Add the housing renewal form to my calendar" → yes | an event in Flux live |
| Remind me | "Remind me about the housing renewal form" → yes | a reminder in your default Reminders list |
| Set me up | "Set me up for the essay" → yes | the essay email opens |
| Discovery | "Discover" → yes / no / stop | questions from the live bank |
| Web, offline | a factual question saved online, asked again | answered from the bank |

## Live check (2026-11-15, Coby's Mac, live mode, network blocked in the process)

Bank: a copy of `~/flux-bank` after a real Sync mail from the test Gmail account (9 emails from 4 senders). Calendar: one of the Mac's own calendars. No yes was given to anything that writes, so nothing was added, opened or drafted. The process blocks every connection except localhost (`reason.live_check.block_network`).

| Capability | Result |
|---|---|
| Chat | works (0.03 s) |
| Catch me up | works: calendar, due through Tuesday and asks from that bank (17.8 s, the cold calendar read; the app warms it at launch) |
| Due + follow-ups ("and next week?", "the first one", "who sent that?") | works, 0.0 s |
| Open it | works: shows "I'll open the email … in Mail" and waits for a yes |
| Person, "and <name>?", Everyone, Who is | works, 0.0 s |
| Calendar (this week, next meeting, free Monday) | works on the named calendar, 0.0 s after the first read |
| Memory (remember, about me, "When is my lab?", forget) | works |
| Web, offline | says it's offline (correct); nothing was saved online first in this bank |
| Drafts (reply and new email) | works: a draft box from the bank, Open in Mail not clicked |
| Add to calendar, Remind me, Set me up, Open my calendar | works up to the yes (each shows what it will do; cancelled) |
| Discovery | works: 4 questions from the live bank |
| Bank question "How much is my phone bill?" / "my Brightline bill?" | **miss**: "I don't have that in your notes or mail." The bill email's summary has no amount (bank summaries lose details), so the bill question is left out of the live run. |
| Suggestions | shown under due, person and catch-me-up answers |
| Voice, real Wi-Fi off | not run here (needs a person at the mic) |

## What doesn't work live (not fixed)

- **No live Canvas sync.** Coursework in the demo comes from saved Canvas pages rewritten into sample assignments (`scripts/demo/`). A real Canvas page can be saved (`scripts/demo/save_canvas_pages.py`, Duo sign-in) and `canvas/read.py` reads it, but nothing files real pages into `~/flux-bank` yet.
- **One mail account.** Opening an email in Mail and Gmail drafts work only in the account `FLUX_ACCOUNT` names (default the test account).
- **Mail sync** reads the last 7 days, at most 10 threads per sync.
- **Calendar:** one calendar; repeating events show only at their first date.
