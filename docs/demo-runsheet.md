# Demo run sheet (the 2-minute video)

One screen recording, no narration: Coby and Antranig take turns asking Flux questions, and
Flux does all the explaining. The take starts with the bank already synced (no Sync on
camera). Everything on screen is **sample data**: the status line reads "Demo data", and the
end card says sample mail and coursework.

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

Then the typed check (network blocked; the preflight and all 12 lines must be RIGHT):

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

## The 12 lines

Who asks: Coby (C) and Antranig (A), each taking one whole workflow. Every answer is fixed
text or code output. Lines 1, 2, 7, 9 and 12 are fixed wording from `playbooks/about.md`.

| # | Who | Say (mic button) | Must appear |
|---|---|---|---|
| 1 | C | "What is Flux?" (still online) | The overview: "Flux is a private assistant that runs entirely on this Mac…" and "What it can do" |
| — | | *Wi-Fi off in the menu bar, on camera* | Status line: "Demo data · Offline · 55 items in the bank" |
| 2 | C | "Do you need the internet?" | "No. I read your mail and coursework/deadlines while you're online, then answer from what I saved. You're offline right now, and I still work." |
| 3 | A | "Catch me up." | Today on your calendar (Sun Nov 15), "Due today through Tue Nov 17", "Asks in mail from the last 7 days" |
| 4 | A | "What's due this week?" | "Due this week (Nov 15 to Nov 22)", each row with its source |
| 5 | A | "And tomorrow?" | "Due Mon Nov 16": reading quiz 9am, chart critique 1:30pm, Hugo's vote 5pm |
| 6 | C | "What did Felix ask me?" | Felix's asks, plus **Suggested: You're free Thursday, Nov 19 at 3pm. Draft a yes to Felix?** Click **Draft yes**. The draft box shows To fambrose@example.edu, "Re: Free Thursday at 3?" and "Hi Felix, Yes, Thursday, Nov 19 at 3pm works for me. See you then." Edit one word. |
| 7 | C | "Will you send that?" | "No. I write the draft and you send it. I never send anything myself." Then click **Open in Mail**: a Mail compose window, filled in, unsent |
| 8 | A | "Set me up for the lab report." | The page "Lab Report 3", the email from Lena Marsh "Lab report format", and the email from Jonah Pike "Lab Report 3 template". Click **Yes, do it**: the page opens in Chrome (local file, works offline) |
| 9 | A | "When is my chemistry exam?" | "I have nothing saved about a chemistry exam, and I won't guess." |
| 10 | C | "Remember that my lab is Tuesdays at 2." | "I'll remember: my lab is Tuesdays at 2." |
| 11 | C | "What do you know about me?" | "my lab is Tuesdays at 2" (your notes) |
| 12 | A | "What model are you running?" | "Bonsai 2, the 4B model, running on this Mac. Your voice is transcribed by Argmax, also on this Mac. Most answers about your day use no model at all: I look them up in what I saved." |
| — | | *End card* | Flux · Bonsai 2 4B · Argmax · zero cloud calls · sample mail and coursework · both names |

If it runs over two minutes, cut "And tomorrow?" first, then the remember pair (10–11).

Known on screen:
- **Line 8:** the two emails don't open, because sample mail isn't in Apple Mail. Flux says "I couldn't open that email itself…" and shows the saved copy. Only the Lab Report 3 page opens.
- **Sync mail:** in demo mode it syncs the real Gmail account into ~/flux-bank, so don't click it.

## Voice pass (with Coby at the mic)

Say each line once through the window's mic button. Write down what the transcript shows. Names and
numbers are where voice goes wrong: Felix, Jonah, "Lab Report 3", "Tuesdays at 2".
