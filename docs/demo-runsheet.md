# Demo run sheet (the 2-minute video)

One story: Flux learns while online, then Wi-Fi goes off and it still runs your day and
helps you act on it. Everything on screen is **sample data** (made-up mail, coursework and
calendar), and the video says so.

## Before every take

```bash
uv run python scripts/demo/demo_reset.py --today 2026-11-15
```

Set `--today` to the recording day. Bonsai must be running on localhost (`scripts/serve_bonsai.sh 4B`).

What the reset does:
- Empties your notes and the saved chats.
- Wipes and rewrites the **Flux demo** calendar, and empties the **Flux demo** reminders list.
- Turns demo mode on. Relaunch Flux after it.
- It takes about 6 minutes, mostly writing the calendar.
- The first run for a new day also rebuilds `~/flux-demo-bank`, about 6 minutes. A backup is kept as `~/flux-demo-bank.bak-<time>`.

It refuses the real bank `~/flux-bank` and any calendar or list not named "Flux demo".

Then the typed check (network blocked; every line below must be RIGHT):

```bash
uv run python scripts/demo/demo_check.py --today 2026-11-15
```

What's in the demo state (built for Sun Nov 15):
- **Mail:** 30 emails. That's brief M's 23, plus Felix "Free Thursday at 3?", Nina's Tuesday 2:30 seminar practice, Jonah (TA) on Lab Report 3, Ivy's photos, a $48.20 phone bill, the Campus Rec newsletter and Sam's calculator.
- **Coursework:** 25 assignments in 4 courses. Lab Report 3 (CHEM 1583) is due Thu 11:59pm.
- **Calendar:** 21 events from Sun 15 to Sat 21 (`scripts/demo/demo_calendar.py show`). It includes:
  - Tue 2–4pm "CHEM 1583 Lab"
  - Wed 1:30–3:30pm "Lab"
  - nothing at Thu 3pm or Thu 7pm
- **Notes about you:** none.

## Beats

| Time | Do / say | Must appear | If it doesn't |
|---|---|---|---|
| 0:00 | **"What's Flux?"** (replaces the spoken hook) | "Flux is a private assistant that runs entirely on this Mac…", then "What it can do" with example questions | Type it. |
| 0:08 | Online. Open the bank slide-over: "This is sample mail and coursework, already synced." | "55 items in the bank": 30 emails and 25 Canvas items | Don't click **Sync mail** in demo mode: it syncs the real Gmail account into ~/flux-bank, so the demo bank doesn't change. |
| 0:20 | Turn Wi-Fi off in the menu bar, on camera | The label reads offline | — |
| 0:27 | Hold Fn-Space and say **"catch me up"**. "Voice is Argmax, running locally." | Today on your calendar, "Due today through Tue Nov 17", open asks, and under it **Suggested: You're free Thursday, Nov 19 at 3pm. Draft a yes to Felix?** | If the words come out wrong, type "catch me up". If Felix's line isn't there, say "and it suggests replies to meeting asks" and move on. |
| 0:45 | Click **Draft yes**, change one word, click **Open in Mail** | A draft box, then a Mail compose window filled in to Felix | Show the draft box only: "it opens this in Mail for me to send". |
| 1:05 | **"What's due this week?"** | "Due this week" with Lab Report 3 (Thu 11:59pm, CHEM 1583 Kitchen Chemistry) and the $48.20 phone bill | Type it. |
| 1:12 | **"and tomorrow?"** | "Due Mon Nov 16" | Cut this beat first if the video runs long. |
| 1:15 | **"set me up for the lab report"**, then **"yes"** | "To set you up for the lab report, I'll open:", then the page "Lab Report 3", the email from Lena Marsh "Lab report format" and the email from Jonah Pike "Lab Report 3 template". On yes, the page opens in the browser (a local file, so it works with Wi-Fi off) and the email opens in Mail. | If it asks "Which one do you mean", say "Lab Report 3". |
| 1:25 | **"Remember that my lab is Tuesdays at 2"** | "I'll remember: my lab is Tuesdays at 2." | Cut this beat second if long. |
| 1:32 | **"what do you know about me?"** | "my lab is Tuesdays at 2", then "Source: your notes" | — |
| 1:40 | Over the open app: "Answers about you come from code reading saved mail, each with its source. Every model call is Bonsai 2 on this Mac." | — | — |
| 1:48 | End card: Flux, Bonsai 2 4B, Argmax, zero cloud calls, both names | — | — |

Left out on purpose: discovery, web lookups, computer control in other apps, the agent loop, sending.

Spare line, not in the video (the check runs it too): "What did Nina Valdez ask me?" gives
"You have CHEM 1583 Lab then (Tuesday, Nov 17 at 2:30pm). Draft a reply proposing another time?".

## Voice pass (with Coby at the mic)

Say each bold line once with Fn-Space. Write down what the transcript shows. Names and
numbers are where voice goes wrong: Felix, Jonah, "Lab Report 3", "Tuesdays at 2".
