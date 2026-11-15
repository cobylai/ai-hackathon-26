# Live demo: Flux on your own data

Flux has two states that never mix:

| | Demo (staged, for the video) | Live (your data) |
|---|---|---|
| Bank | `~/flux-demo-bank` (sample mail and sample coursework) | `~/flux-bank` (what Sync mail and the web route filed) |
| Calendar | "Flux demo" | the one calendar you name |
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

## Before going offline (online, once)

1. `scripts/flux-mode live --calendar "<your calendar>"`, then relaunch Flux. The menu's first line says **Your data · ~/flux-bank**.
2. **Mail:** menu → **Sync mail** (or `FLUX_BANK_DIR=~/flux-bank uv run python scripts/sync_email.py 7`). It reads the Gmail account signed in on the hidden browser's profile (`uv run python -m harness login https://mail.google.com` once), at most 10 threads per sync, read-only.
3. **Coursework:** there is no live Canvas sync yet (see "What doesn't work live"). Coursework that arrives by email is synced with the mail.
4. **Calendar:** Calendar.app keeps a local copy of iCloud and Google calendars, so let it finish syncing while online.
5. **Web answers you want offline:** ask them online and say yes to "save that to your notes".
6. **Confirm the bank has content:** click the status line ("N items in the bank") or run `ls ~/flux-bank/*/`. Ask "What did everyone ask me?" to see what's there.
7. **Permissions already granted:** microphone, Accessibility (Fn-Space), and Automation for Calendar, Reminders and Mail. Menu → **Check setup** lists any that are missing.
8. **Launch once with voice** so the speech model is loaded. The first launch on a Mac compiles for several minutes. Ask one question by voice.
9. Bonsai is running on 127.0.0.1:8080 (Flux starts it).
10. Turn **Wi-Fi off**.

## Questions (no staged names)

Pick names from your own bank: the bank list on the right shows who wrote to you.

| Capability | Ask |
|---|---|
| Chat | "Hey, can you hear me okay?" |
| Catch me up | "Catch me up" |
| Due | "What's due this week?" → "and next week?" → "the first one" → "who sent that?" |
| Open it | "open it" → yes (the email opens in Mail if it's in the mail account, else its saved copy) |
| Person | "What did <someone who emailed you> ask me?" → "and <another sender>?" |
| Everyone | "What did everyone ask me?" |
| People | "Who is <sender>?" |
| Calendar | "What's on my calendar this week?", "When is my next meeting?", "Am I free Monday?" |
| Memory | "Remember that my lab is Tuesdays at 2." → "What do you know about me?" → "When is my lab?" → "Forget that" |
| Notes and mail | a question about something in your mail, e.g. "Where is <an event someone mentioned>?" |
| Web, offline | a factual question you saved online, asked again ("Who wrote the novel Frankenstein?") |
| Drafts | "Draft a reply to <sender>" → Open in Mail (nothing is sent) |
| Add to calendar | "Add <an item with a date> to my calendar" → yes (goes into your calendar) |
| Remind me | "Remind me about <an item with a due date>" → yes (goes into your default Reminders list) |
| Set me up | "Set me up for <an item>" → yes |
| Discovery | "Discover" → yes / no / skip / stop |

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
| Bank question "How much is my phone bill?" | **miss**: "I don't have that in your notes or mail." The bill email is in the bank, but the bank search didn't match "phone" to it. |
| Suggestions | shown under due, person and catch-me-up answers |
| Voice, real Wi-Fi off | not run here (needs a person at the mic) |

## What doesn't work live (not fixed)

- **No live Canvas sync.** Coursework in the demo comes from saved Canvas pages rewritten into sample assignments (`scripts/demo/`). A real Canvas page can be saved (`scripts/demo/save_canvas_pages.py`, Duo sign-in) and `canvas/read.py` reads it, but nothing files real pages into `~/flux-bank` yet.
- **One mail account.** Opening an email in Mail and Gmail drafts work only in the account `FLUX_ACCOUNT` names (default the test account).
- **Mail sync** reads the last 7 days, at most 10 threads per sync.
- **Calendar:** one calendar; repeating events show only at their first date.
