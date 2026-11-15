# Submission pack

Everything for the Discord submission (due **noon Sun 2026-11-15**), drafted for Coby to edit. Coby posts and records. **Flux** is the app name (Flux or Hearth, undecided): one find-and-replace of `Flux` fixes this file and the README. Everything has landed on main (computer control X, suggestions and drafts W, saved chats, the signed Mac app).

- Release page: **link TBD** (built on a cobydev branch, not deployed yet).
- Last partner test round: [PARTNER-TESTING-FINAL.md](PARTNER-TESTING-FINAL.md) (results not in yet).

## One-sentence descriptions (pick one)

1. Flux is a voice assistant for students that runs entirely on a Mac, answering "what's due", "what did Felix ask me" and "catch me up" from your mail, coursework, calendar and notes with Wi-Fi off, using local Bonsai 2 4B and Argmax speech-to-text.
2. Hold a key and ask: Flux answers from your own mail, Canvas coursework, calendar and notes in about a second, fully offline, with every model call on a local Bonsai 2 4B and voice through Argmax.
3. Flux reads your mail and coursework while you're online and answers questions about them when you're not, privately on your Mac, with zero cloud calls and most answers needing no model at all.

## Discord post (paste-ready)

```text
**Flux**
Team: Coby Lai, Antranig Baghdassarian

Flux is a voice assistant for students that runs entirely on a Mac, answering "what's due", "what did Felix ask me" and "catch me up" from your mail, coursework, calendar and notes with Wi-Fi off, using local Bonsai 2 4B and Argmax speech-to-text.

Prizes: Main track (Argmax voice), Sustainability (right-sized: Bonsai 2 4B, and most questions are answered by code with no model call)
Repo: https://github.com/cobylai/ai-hackathon-26
Video: <VIDEO LINK>
Release page: <RELEASE PAGE LINK, cobydev, TBD>
```

Check before posting: Antranig's surname spelling; the prize names against the Discord list (below); the repo is reachable by the judges (it is **private** now).

### Prizes

Our kickoff notes name only these two. Check the Discord announcement for the full list and exact names.

| Prize | Fits? | Why |
|---|---|---|
| Main track | Yes | Needs Argmax: push-to-talk speech-to-text runs through the Argmax Pro SDK on-device. |
| Sustainability (judged on right-sizing the model) | Yes | Bonsai 2 4B chosen over 9B on a side-by-side check (same accuracy on our fixtures, faster, 2.2 GB vs 3.8 GB); due, person, calendar, catch-me-up, memory, follow-up, suggestion, free/busy and computer-control answers use no model; a 32k budget guard and 6,000-token chunking. |

## Video script (2:00 max)

Use the Mac app panel (Fn-Space) or the window. Speak is **off** (no spoken answers in the video). Spoken lines are held on Fn-Space; web questions are typed. Answers below are from the checked demo runs (`docs/integration.md`, `docs/PARTNER-TEST-REPORT.md`, `docs/reasoning-layer.md`, the playbooks); the exact rows depend on the bank built for the recording day.

| Time | On screen | Said (voice-over or into the mic) |
|---|---|---|
| 0:00–0:10 | Title over the panel on the desktop. | "Students live in mail, Canvas and a calendar. Flux answers questions about all three, out loud, entirely on this Mac." |
| 0:10–0:25 | Open the bank on the right: Mail and Coursework groups. Type "Who wrote the novel Frankenstein?" Answer: Mary Shelley, quoted line, "Source: en.m.wikipedia.org/wiki/Frankenstein", then "Say or type yes to save that to your notes." Type yes → "Saved to your notes." (about 10 s; cut the wait.) | "While we're online, it has read sample mail and sample coursework into a local bank. A question it can't answer, it looks up, quotes, cites, and saves." |
| 0:25–0:32 | Control Center: Wi-Fi off. The status line turns to offline. | "Now Wi-Fi off." |
| 0:32–0:45 | Hold Fn-Space: "Catch me up." Answer: today's calendar (Demo practice run, Hackathon judging), due through Tue Nov 17, asks from the last 7 days, each with its source. | (into mic) "Catch me up." |
| 0:45–1:05 | Hold: "What's due this week?" → a dated table, mail and coursework together. Hold: "And tomorrow?" → Mon Nov 16, including Hugo's team-name vote at 5pm. Hold: "What did Felix ask me?" → Cabin packing list: bring a sleeping bag; pay your $35 share for the cabin trip. Each shows 0.0 s. | (into mic) the three questions. VO: "No model needed for these: code reads the bank, so they come back instantly." |
| 1:05–1:20 | Hold: "Remember that my lab is Tuesdays at 2." → "Got it. I'll remember: my lab is Tuesdays at 2." Hold: "What do you know about me?" → the note, "Source: your notes". | (into mic) the two lines. |
| 1:20–1:35 | Hold: "What did Milo ask me?" → Milo's band-practice ask, and under it **Suggested**: "You're free Thursday, Nov 19 at 7pm. Draft a yes to Milo?" Click **Draft yes** → the draft box (To, Subject "Re: …", a yes body, "Nothing is sent."). Click **Open in Mail** → a new Mail message, filled in. Close it unsent. | (into mic) "What did Milo ask me?" VO: "It checked my calendar, I'm free, so it drafts the yes. Nothing is ever sent." |
| 1:35–1:48 | Type "Who wrote the novel Frankenstein?" again, still offline → Mary Shelley, same source, from the bank in under a second. | "The web answer from earlier, now offline." |
| 1:48–2:00 | End card: Flux · Bonsai 2 4B, local · Argmax on-device voice · zero cloud calls · Coby Lai & Antranig Baghdassarian. | "Bonsai 2 4B, Argmax, zero cloud calls." |

- **1:20 beat:** the draft box and Open in Mail work offline (a `mailto:` handed to Mail), so it stays after Wi-Fi off. The free/busy line needs Milo's meeting email (m21, band practice Thu Nov 19 7pm) in the bank and nothing on "Flux demo" at that time. The wording above is from the window screenshots and the suggest/compose playbook examples; the exact body comes from the code template. Rehearse it once offline before recording.
- **Spare beat** if time allows, or if the draft beat misbehaves: "What's due tomorrow?" → "open the first one" → yes (the assignment page opens), or Discover → one yes ("Are you taking CHEM 1583 Kitchen Chemistry?" → "Saved: …").
- Person names: use only Felix, Hugo, Ivy, Jonah, Greta, Omar, Lena or Milo. Avoid Nina, Tess, Kiri, Rafe.
- Say "sample mail and sample coursework" in the voice-over; don't imply a real inbox.

## Before recording

- [ ] Bonsai server running, restarted since the 127.0.0.1 change (82da364): `pkill -f mlx_vlm.server; scripts/serve_bonsai.sh 4B`; `lsof -iTCP:8080 -sTCP:LISTEN` shows `localhost`/`127.0.0.1`, not `*`.
- [ ] Demo bank rebuilt for today (DAY=2026-11-15): sample mail ("Demo bank" in `docs/integration.md`), then sample coursework (`docs/canvas.md`). Check: `make_test_mail.py check ... --offline` gives 37/38.
- [ ] "Flux demo" calendar has today's made-up events (one-off, not repeating), the "Lab" event Wed Nov 18 1:30–3:30pm, and nothing Thu Nov 19 at 7pm (so Milo's practice shows as free).
- [ ] Delete the "Band practice" or "Band practice Thursday" event (Thu Nov 19 7–8pm; Antranig's full test round left one in place) from "Flux demo" if worker 14's live test step 2 added it, or the video's "You're free… Draft a yes to Milo" beat turns into a clash. Delete any test reminders in the "Flux demo" Reminders list too.
- [ ] The demo bank includes the meeting emails m21–m23 (Milo, Greta, Ivy).
- [ ] The Frankenstein question is **not** in the bank before recording (it's asked on camera while online, then again offline). Rehearse it on a copy of the bank, not the demo bank.
- [ ] Mac app built once and launched once beforehand (first voice start compiles for minutes). It's Developer ID signed, so permissions survive a rebuild; without the identity it signs ad hoc and asks again.
- [ ] The setup window done: Argmax key, Accessibility, microphone, Calendar, Reminders and Mail allowed; "Check setup" in the menu lists no problems.
- [ ] Mail.app has a default account so Open in Mail fills a compose window; close it unsent after the take.
- [ ] The full Wi-Fi-off run done once already, with voice, end to end (not yet done: open risk).
- [ ] Questions rehearsed by voice, each once, in this order; Speak off; any old discovery answers cleared ("What have you learned?", "unlearn N") and old notes forgotten so the memory beat starts clean.
- [ ] Notifications off (Focus), other windows closed, no real mail or calendar visible.

## Later (not in the demo)

- Built and tested on the branch `feature/agent-integration`, off by default, not in the demo or on main until after the recording: the agent loop, sending mail after a confirmation (never shown), proactive nudges, and real Gmail and Calendar sync.

- Use what I'm looking at: answer about the front window's content (X4).
- A learned weekly schedule (from calendar and notes).
- Live Canvas sync (today it reads saved pages).

## Landed

| Item | Owner | Status |
|---|---|---|
| X: computer control (open it, add to calendar, remind me, set me up) | worker 14 | on main |
| W: suggestions, reply drafts, compose with Open in Mail | worker 19 | on main |
| T2: saved chats | worker 18 | on main |
| Signed Mac app, 8-screen setup, drag-to-Applications DMG | worker 16 | on main; notarization pending Coby |
| Release page | — | built on a cobydev branch, not deployed; link TBD |

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
