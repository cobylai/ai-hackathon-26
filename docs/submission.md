# Submission pack

Everything for the Discord submission (due **noon Sun 2026-11-15**), drafted for Coby to edit. Coby posts and records. **NAME** is the app name (Muse or Hearth, undecided): one find-and-replace of `NAME` fixes this file and the README. Items marked **pending** wait on work that hasn't landed yet.

## One-sentence descriptions (pick one)

1. NAME is a voice assistant for students that runs entirely on a Mac, answering "what's due", "what did Felix ask me" and "catch me up" from your mail, coursework, calendar and notes with Wi-Fi off, using local Bonsai 2 4B and Argmax speech-to-text.
2. Hold a key and ask: NAME answers from your own mail, Canvas coursework, calendar and notes in about a second, fully offline, with every model call on a local Bonsai 2 4B and voice through Argmax.
3. NAME reads your mail and coursework while you're online and answers questions about them when you're not, privately on your Mac, with zero cloud calls and most answers needing no model at all.

## Discord post (paste-ready)

```text
**NAME**
Team: Coby Lai, Antranig Baghdassarian

NAME is a voice assistant for students that runs entirely on a Mac, answering "what's due", "what did Felix ask me" and "catch me up" from your mail, coursework, calendar and notes with Wi-Fi off, using local Bonsai 2 4B and Argmax speech-to-text.

Prizes: Main track (Argmax voice), Sustainability (right-sized: Bonsai 2 4B, and most questions are answered by code with no model call)
Repo: https://github.com/cobylai/ai-hackathon-26
Video: <VIDEO LINK>
```

Check before posting: Antranig's surname spelling; the prize names against the Discord list (below); the repo is reachable by the judges (it is **private** now).

### Prizes

Our kickoff notes name only these two. Check the Discord announcement for the full list and exact names.

| Prize | Fits? | Why |
|---|---|---|
| Main track | Yes | Needs Argmax: push-to-talk speech-to-text runs through the Argmax Pro SDK on-device. |
| Sustainability (judged on right-sizing the model) | Yes | Bonsai 2 4B chosen over 9B on a side-by-side check (same accuracy on our fixtures, faster, 2.2 GB vs 3.8 GB); due, person, calendar, catch-me-up, memory and follow-up answers use no model; a 32k budget guard and 6,000-token chunking. |

## Video script (2:00 max)

Use the Mac app panel (Fn-Space) or the window. Speak is **off** (no spoken answers in the video). Spoken lines are held on Fn-Space; web questions are typed. Answers below are from the checked demo runs (`docs/integration.md`, `docs/PARTNER-TEST-REPORT.md`, `docs/reasoning-layer.md`, the playbooks); the exact rows depend on the bank built for the recording day.

| Time | On screen | Said (voice-over or into the mic) |
|---|---|---|
| 0:00–0:10 | Title over the panel on the desktop. | "Students live in mail, Canvas and a calendar. NAME answers questions about all three, out loud, entirely on this Mac." |
| 0:10–0:25 | Open the bank on the right: Mail and Coursework groups. Type "Who wrote the novel Frankenstein?" Answer: Mary Shelley, quoted line, "Source: en.m.wikipedia.org/wiki/Frankenstein", "Saved to your notes." (about 10 s; cut the wait.) | "While we're online, it has read sample mail and sample coursework into a local bank. A question it can't answer, it looks up, quotes, cites, and saves." |
| 0:25–0:32 | Control Center: Wi-Fi off. The status line turns to offline. | "Now Wi-Fi off." |
| 0:32–0:45 | Hold Fn-Space: "Catch me up." Answer: today's calendar (Demo practice run, Hackathon judging), due through Tue Nov 17, asks from the last 7 days, each with its source. | (into mic) "Catch me up." |
| 0:45–1:05 | Hold: "What's due this week?" → a dated table, mail and coursework together. Hold: "And tomorrow?" → Mon Nov 16, including Hugo's team-name vote at 5pm. Hold: "What did Felix ask me?" → Cabin packing list: bring a sleeping bag; pay your $35 share for the cabin trip. Each shows 0.0 s. | (into mic) the three questions. VO: "No model needed for these: code reads the bank, so they come back instantly." |
| 1:05–1:20 | Hold: "Remember that my lab is Tuesdays at 2." → "Got it. I'll remember: my lab is Tuesdays at 2." Hold: "What do you know about me?" → the note, "Source: your notes". | (into mic) the two lines. |
| 1:20–1:35 | Click Discover. A yes/no question built from the bank, e.g. "Are you taking CHEM 1583 Kitchen Chemistry?" Click or say yes → "Saved: I'm taking CHEM 1583 Kitchen Chemistry." Then Stop. | VO: "It can also ask about you, and keeps only what you confirm." |
| 1:35–1:48 | Type "Who wrote the novel Frankenstein?" again, still offline → Mary Shelley, same source, from the bank in under a second. | "The web answer from earlier, now offline." |
| 1:48–2:00 | End card: NAME · Bonsai 2 4B, local · Argmax on-device voice · zero cloud calls · Coby Lai & Antranig Baghdassarian. | "Bonsai 2 4B, Argmax, zero cloud calls." |

- **Discovery beat swap (pending):** if a reply draft (worker 19) or "open it" (worker 14) lands and is checked live, it replaces the 1:20–1:35 beat, e.g. after "What did Felix ask me?": "Draft a reply to Felix saying yes" → the draft preview → "yes" → "Saved a reply draft … It was not sent." Drafting needs a connection, so that beat goes **before** Wi-Fi off. Not yet checked live for the video.
- Person names: use only Felix, Hugo, Ivy, Jonah, Greta, Omar, Lena or Milo. Avoid Nina, Tess, Kiri, Rafe.
- Say "sample mail and sample coursework" in the voice-over; don't imply a real inbox.

## Before recording

- [ ] Bonsai server running, restarted since the 127.0.0.1 change (82da364): `pkill -f mlx_vlm.server; scripts/serve_bonsai.sh 4B`; `lsof -iTCP:8080 -sTCP:LISTEN` shows `localhost`/`127.0.0.1`, not `*`.
- [ ] Demo bank rebuilt for today (DAY=2026-11-15): sample mail ("Demo bank" in `docs/integration.md`), then sample coursework (`docs/canvas.md`). Check: `make_test_mail.py check ... --offline` gives 37/38.
- [ ] "Muse demo" calendar has today's made-up events (one-off, not repeating).
- [ ] The Frankenstein question is **not** in the bank before recording (it's asked on camera while online, then again offline). Rehearse it on a copy of the bank, not the demo bank.
- [ ] Mac app built once and launched once beforehand (first voice start compiles for minutes). Don't rebuild after that: each build asks for permissions again.
- [ ] Microphone, Calendar and Accessibility allowed for the app; "Check setup" in the menu lists no problems.
- [ ] The full Wi-Fi-off run done once already, with voice, end to end (not yet done: open risk).
- [ ] Questions rehearsed by voice, each once, in this order; Speak off; any old discovery answers cleared ("What have you learned?", "unlearn N") and old notes forgotten so the memory beat starts clean.
- [ ] Notifications off (Focus), other windows closed, no real mail or calendar visible.

## Later (not in the demo)

- Use what I'm looking at: answer about the front window's content (X4).
- A learned weekly schedule (from calendar and notes).
- Proactive nudges ("Hugo's vote is due at 5pm").
- Live Canvas sync (today it reads saved pages).

## Pending

| Item | Owner | Status |
|---|---|---|
| X: bigger computer control (Mail, Settings, Chrome) | worker 14 | **pending** |
| W: suggested replies / drafts | worker 19 | **pending** |
| Final fixes | — | **pending**; one final pass on this file and the README after the last lands |

## Repo readiness

**Done here (current tree only):** in `docs/log/feature-email-gmail.md` and `docs/plan/notes-email-eval.md`, the two Cornell addresses, one third-party name, two thread subjects and two course codes are replaced with placeholders (`<user-address>`, `<other-participant-address>`, `<name>`, `<thread subject>`, `<course>`). The meaning is kept.

**History search** (`git log -p --all`, `git log -S/-G`, outside `samples/`), main at the time of writing. Nothing was rewritten; repo visibility is unchanged. Those are Coby's calls.

| Found | Where | Commits |
|---|---|---|
| Antranig's Cornell address | author/committer email on all 62 of his commits; also in the two docs above before the scrub | docs: f4d9067, 6bbc554, bb58af1, 9a45c68 (removed in the scrub commit) |
| A third party's Cornell address (reply-draft incident) | the two docs above | 9a45c68 |
| A third party's full name in a Gmail subject ("… Sign Up Notification: <name>") | `docs/plan/notes-email-eval.md` | 9a45c68 |
| A first name in a real thread subject | `docs/log/feature-email-gmail.md` | f4d9067 |
| Real course codes and real subjects/snippets from Antranig's mailbox ("BME 3030 HW5 Oral Defense - Scheduling Correction", "BME 4080 Submission Posted: Design History File") | `tests/pages/gmail_list.html` (still in the tree; harness tests use them: `tests/test_asks.py`, `tests/test_email_search.py`), and the eval notes | 85c9e59, 496c315, 2e23640, 9a45c68 |
| "ECE 4760" search query | email logs | 496c315, 9a45c68 |
| Partner's full name as a sender in sample-mail screenshots | `docs/window/*.png` | (screenshots; he's an author) |
| Keys/tokens (`ax_`, `axst_`, `sk-`, `ghp_`, `hf_`, AWS, private keys) | none found | — |
| Phone numbers, cookies, session tokens | none found | — |
| Real Canvas pages or `data/` | never committed (`data/canvas-templates`, the saved Gmail `template.html` and the banks live outside git) | — |
| Coby's school address | not in history (his commits use the GitHub noreply address) | — |

Coby's calls: whether to rewrite history for the addresses (it would change every commit sha), whether to replace the real subjects in `tests/pages/gmail_list.html` (partner's test fixture), and making the repo public or adding the judges.
