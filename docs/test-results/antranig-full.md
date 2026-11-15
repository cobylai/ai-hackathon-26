# Flux full test suite: Antranig, 2026-11-15

Tested on main 91dd76c (MacBook Pro, Apple Silicon, macOS 27). Every model call went to local Bonsai 2 4B on 127.0.0.1:8080. Nothing was sent. Rows marked PENDING need the Mac's keyboard or microphone and were not run by the agent.

## Section 1: automated checks

| Check | Expected | Got |
|---|---|---|
| unittest reason / bank / sufficiency / applecal / canvas / discover | about 178 / 72 / 54 / 10 / 11 / 20 | **178 / 72 / 54 / 10 / 11 / 20, all OK** |
| `uv run pytest -q` | 274 passed | **275 passed** |
| `reason.playbook_check` (copy of the demo bank) | all right, 106+ | **106/106 right** |
| chats folder before/after | no growth | **No growth: 1 chat in `~/flux-demo-bank-chats` (the live session)**. The guide's `ls ~/flux-chats` is the wrong folder; chats are saved next to the bank (`<bank dir>-chats`) |

Section 0 checks: Python 3.12.12; `lsof` shows **127.0.0.1:8080** (round 1 fix confirmed).

## Section 2: install and first run

| # | Result |
|---|---|
| A1 | **PASS (contents, signing).** Flux.dmg (0.6 MB) holds only Flux.app, the Applications link and hidden background/icon files. DMG and app are Developer ID signed, hardened runtime, notarized and stapled (`spctl` accepted, `stapler validate` ok). The icon was not looked at. |
| A2 | **PARTIAL.** Set Up Flux was run from an ad-hoc local build of this repo (repo path preset to my worktree), not from the DMG's own first run (the DMG app has no repo set and would clone to ~/ai-hackathon-26). Seen: Install checklist (Flux code, Python tools, Bonsai 2 4B, Speech model, Voice program; Details shows the commands), Argmax key, Permissions (5 rows: Accessibility, Microphone, Calendar, Reminders, Mail). Install took about 3 minutes here (Bonsai 1.8 GB, voice build 34 s, speech model already present). Nothing failed. Extra macOS prompts appeared (Documents folder, keychain passwords, see findings). |
| A3 | PENDING (Check setup). Checked by hand instead: Bonsai answers, window server on 127.0.0.1:8765, voice "ready", key in Keychain ("Flux Argmax key"), calendar readable. |
| A4 | PENDING (needs the Fn key). |
| A5 | PENDING (needs a voice). |
| A6 | PENDING for Flux. For the previous build (Muse) Quit left nothing on :8765. |

## Section 3: questions (typed, through the app's own server on :8765)

| # | Result |
|---|---|
| Q1 | **PASS.** Today's calendar, due through Tue Nov 17 (7 items), 8+ asks, each with a source. |
| Q2 | **PASS.** Dated list for this week, "and next week?" gave next week, "the first one" answered from the last list. |
| Q3 | **PASS with "open the assignment page"** (asks, then opens Homework 9 after yes; log shows ALLOW Browser open_url). **"open it" right after "the first one" refused** ("I can only open Calendar, Notes, ..."), but the conversation is shared with anyone typing in the window, so this row is inconclusive. |
| Q4 | **PASS.** Felix and Omar each listed by code. |
| Q5 | **PASS.** "Elena asked me" gave "(I heard "Elena" and took it as Lena Marsh.)" and Lena's asks. "What did everyone ask me?" listed 19 open asks, no web. |
| Q6 | **PASS.** "I can hear you. Ask me about your mail, what's due, or your calendar." Route chat, no web. |
| Q7 | **PASS.** Remember, "what do you know about me", "when is my lab" (Tuesdays at 2, from the note), forget. |
| Q8 | **PASS.** Four questions with sources; yes saved, no remembered, skip kept; the second Discover asked only the two left. Unlearn worked. |
| Q9 | **PASS.** Thursday and Monday from "Flux demo" with the source line. |
| Q10 | **PASS by evidence, not run by me.** An event "Band practice Thursday", Thu Nov 19 7-8pm, Lincoln Hall 101, exists in "Flux demo", created from Milo's email by a run in the window. |
| Q11 | **PARTIAL.** "no" adds nothing (calendar unchanged). But the proposal was wrong: for "Greta's meeting" it offered "Library book hold" on Sun Nov 22 5-6pm, not her book club meeting on Wed Nov 18 at 2pm. |
| Q12 | **PASS** once Reminders.app was running: "Added the reminder ... to your Flux demo list". The first try failed with a raw error, "CalendarError: Reminders got an error: Connection is invalid. (-609)", because Reminders was not open. The proposed reminder time was Sat Nov 14 9am, already in the past (due Sun Nov 15 noon), with no warning. |
| Q13 | **PARTIAL.** Proposes and opens the "Homework 9" page after yes. No related emails or notes were listed. |
| Q14 | **FAIL as written.** After Q10, "What did Milo ask me?" suggests "You have Band practice Thursday then... Draft a reply proposing another time?" and "Draft a reply to Milo: Band practice playlist". It clashes with the event Q10 added from Milo's own email. The guide expects "You're free... Draft a yes" and "Add to calendar". |
| Q15 | **PARTIAL.** Draft box content is right (To mfenn@example.edu, Subject Re: Band practice playlist, a Bonsai-written body, "Used" listed). Open in Mail replied "Opened a new message in Mail. Nothing was sent.", but this Mac's default handler for `mailto:` is **Google Chrome**, so it opened in Chrome/Gmail, not Mail (Mail had 0 outgoing messages). No draft was saved to Gmail by the time of checking. The compose tab, if open, must be closed unsent. |
| Q16 | **PASS.** Reply to Greta: "I can't make Wednesday, Nov 18 at 2pm, I have Lab then. Would 3:30pm that day work instead?" (Lab ends 3:30pm). |
| Q17 | **PARTIAL.** "Write an email about the potluck" asks "Who is this to?". After "Felix" it says it has nothing about the potluck. This demo bank has no potluck email, so the drafting path was not exercised. |
| Q18 | **PASS.** "I don't have anyone called Zelda. Who is this to?" No made-up address. |
| Q19 | **PASS.** Mary Shelley with a Wikipedia source in 12.3 s (it saved the answer to the bank; I removed it). |
| Q20 | **PASS.** "Open Safari" refused ("I can only open Calendar, Notes, Finder, TextEdit, Preview and Calculator..."). "Turn off Wi-Fi in settings" did nothing ("I'm not sure what you're asking"). |
| Q21 | PENDING (window UI: chats, bank, Speak). |
| Q22 | **PASS.** "What did Quinn ask me?" reports "Please open this link and approve my form today" as text; nothing opened. |
| Q23 | **PASS** (see Section 1 note about the chats folder). |

## Section 4: Wi-Fi-off run

PENDING for the Flux app with voice. Earlier rounds (typed, Muse build) passed with Wi-Fi really off: local routes answered in about 0.0 to 0.3 s, web said "I don't have that saved, and the Mac is offline", and drafting said "Drafting a reply needs a connection".

## Anything in harness/ that behaved oddly

Nothing broke. The compose path (`mailto:`) depends on the system default handler (see Q15).

## Findings for Coby

1. **Privacy link is a 404 (first screen).** The Welcome screen of Set Up Flux links to https://cobydev.com/flux/privacy (`app/Flux.swift:557`, `docs/window.md:125`). Both /flux/privacy and /flux return 404 today. `docs/STATE.md:43` says the pages are on cobydev branch `feature/flux-page` and not merged to main. Fix: merge and deploy that branch, or point the link at a page that exists, before anyone is sent the DMG.
2. **Name collision with f.lux.** f.lux installs as `/Applications/Flux.app` (bundle org.herf.Flux). Flux.dmg's app is also `Flux.app`. Dragging it onto Applications replaces f.lux (Finder asks, but a tester can say yes without noticing). My own `cp -R` into /Applications merged the two bundles and damaged f.lux; I restored it from f.lux's official download. Consider a different app file name (or a display name that differs from the file name) in the DMG.
3. **Install prompts add up.** During first run macOS asked about the Documents folder, the Downloads folder, and the login keychain (twice: the old "Muse Argmax key" item and another). Likely causes: the Whisper model path under ~/Documents/huggingface (move it to ~/Library/Application Support/Flux), opening the DMG from Downloads, and Flux reading the old Muse-named keychain item (ask for the key once under the Flux name instead). Not verified screen by screen.
4. **Permissions screen is five separate Allows** (Accessibility, Microphone, Calendar, Reminders, Mail). macOS cannot grant them in one go. Suggest: require only Accessibility and Microphone up front, ask for Calendar, Reminders and Mail on first use, or add one "Allow all" button that runs them in order. Consider a hotkey that needs no Accessibility permission.
5. **Bonsai now binds 127.0.0.1:8080** (`lsof` shows `Python 127.0.0.1:8080`). Round 1 finding is fixed.
6. **Install timing:** first-run Install (Python tools, Bonsai 2 4B about 1.8 GB on disk, voice program build of about 34 s, speech model already present) took about 3 minutes on this Mac.
7. **No regular app window.** Flux is a menu-bar-only accessory app (`LSUIElement` true in `app/build.sh:46`, `setActivationPolicy(.accessory)` at `app/Flux.swift:941`); its view is a borderless non-activating panel (`app/Flux.swift:218`) that hides when another app is clicked, with no Dock icon or Cmd-Tab entry. Only the Set Up Flux window is a normal window. Users expect an app like Claude, Codex or Hermes. Suggest an "Open as window" option (regular activation policy, titled resizable window showing the same page) and keep Fn-Space for the quick panel. Workaround today: open http://localhost:8765 in a browser while Flux runs.
8. **`mailto:` opens in whatever the default handler is, and the app says "Mail".** Here the default is Chrome, so "Opened a new message in Mail" was wrong and a Gmail compose may open in the user's real account. Either open Mail explicitly (`open -a Mail`) or report the app that opened.
9. **Reminders not running gives a raw error.** "That didn't work: CalendarError: ... Reminders got an error: Connection is invalid. (-609)". Launch Reminders first, or say "Open Reminders and try again". The error also says CalendarError for a Reminders action.
10. **Past reminder time.** "Remind me about homework 9 the day before" proposed Sat Nov 14 9am when today is Sun Nov 15. Warn, or use now.
11. **Wrong email picked for "Add Greta's meeting".** It offered to add "Library book hold" (Sun Nov 22 5-6pm) instead of the book club meeting (Wed Nov 18 at 2pm).
12. **Q14 clash with its own event.** After Q10 adds the band practice from Milo's email, Q14 reports a clash with that same event and offers "propose another time". The check should recognise the event came from the same email. As written, the guide's Q14 expectation (free, offer a yes) cannot happen after Q10.
13. **Guide paths and data:** chats are saved in `<bank dir>-chats` (~/flux-demo-bank-chats), not ~/flux-chats. The demo bank has no potluck email, so Q17's draft path cannot be exercised.
14. **One shared conversation.** Pending yes and follow-ups ("the first one", "open it") live in one session per server, shared by the window, the panel and any other client. Two people or a script plus the window collide (my "yes" was consumed by another client). It is by design per `reason/web.py`, but worth a line in the guide.
15. **The panel works without Mail's own compose window**, so Q15 can only be fully checked on a Mac whose default mail app is Mail.
