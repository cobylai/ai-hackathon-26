# Round 2 test results: Antranig, 2026-11-15

Tested on main at 771ee6e (guide `docs/PARTNER-TESTING-2.md`), MacBook Pro, Apple Silicon, macOS 27, Python 3.12.12. Every model call stayed on local Bonsai 2 4B (127.0.0.1:8080 once bound to localhost; at this commit it still bound `*:8080`). Nothing was sent. This round is superseded by `antranig-full.md` for the later builds; it is kept because it covers the Muse build and rows the full suite does not.

## Test counts

| Check | Expected | Got |
|---|---|---|
| unittest reason / bank / sufficiency / applecal / canvas | about 93 / 65 / 48 / 9 / 10 | 95 / 72 / 48 / 10 / 11, all OK |
| `uv run pytest -q` (3.12) | 271 passed, 3 skipped | 275 passed, 0 skipped (the uBlock Lite tests run because the extension is installed) |
| demo-bank `make_test_mail.py check --offline` | 37/38 | 37/38 (the known miss: hackathon team name options) |
| `reason.playbook_check` | every example right | 40/50 before the "Muse demo" calendar existed, **41/50 after**. The 9 misses are the discovery examples, which assume Canvas pages (optional, skipped), so they ask about different facts; discovery itself behaved correctly |

## Things to try (typed)

| Row | Result |
|---|---|
| What's on my calendar this week? / next event / Am I free Monday? | **PASS.** Events from "Muse demo", each with "Source: Apple Calendar (Muse demo)". "Am I free Monday?" lists the events rather than saying free or busy. |
| Remember that my lab is Tuesdays at 2 | **PASS** ("Got it. I'll remember: ...") |
| What do you know about me? | **PASS** (the note, "Source: your notes") |
| When is my lab? | **PASS** ("Tuesdays at 2", from the note, 0.9 s) |
| Forget that | **PASS** ("Forgotten: ...") |
| Catch me up / What's my day? | **PASS** (calendar, due soon and open asks, each sourced) |
| Open my calendar, then yes | **PASS.** Calendar.app opened; `~/.harness/actions.log` shows `ALLOW Calendar open`. |
| Open Safari | **PASS.** Refused ("I can only open Calendar, Notes, Finder, TextEdit, Preview and Calculator, or a page saved in the bank."). |
| Draft a reply to a sender, then yes (online, Gmail signed in) | **NOT RUN as written, guard PASS.** The harness profile was signed in as the Cornell account, not the test account, and Flux/Muse refused ("Gmail is signed in as ab2864@cornell.edu, not ilovelocalai@gmail.com. I only save drafts in the test account, so nothing was drafted."). A successful draft save was therefore not exercised. |
| Same draft request offline | **PASS.** "Drafting a reply needs a connection, and the Mac is offline. Nothing was drafted." |
| Who wrote Frankenstein? (online) | **PASS.** Mary Shelley, Wikipedia source, 11.1 s. "What is the capital of Peru?" gave Lima in 14.1 s. |
| Edit one line of `playbooks/due.md`, restart, ask | **PASS.** The new wording showed after a restart; the edit was reverted. |
| Discovery: yes, no, skip, second run | **PASS.** Sourced questions; yes saved, no remembered, skip kept; the second run asked only the unanswered one; unlearn worked. |

## Wi-Fi-off run (Wi-Fi really off, against the Mac app's own server)

- **13 local questions: PASS.** due, person, three calendar questions, remember, what-do-you-know, when-is-my-lab, forget, catch me up, Open Safari refused, Open my calendar and yes. Almost all answered in 0.0 to 0.3 s. "When is my lab?" took 9.5 s offline (about 1 s online); the cause was not found.
- The first run's last two rows were invalid because Wi-Fi came back before they ran (a real web answer in 11 s and a draft preview). Rerun with Wi-Fi off: "Who wrote Frankenstein?" gave "I don't have that saved, and the Mac is offline, so I can't look it up."; the draft request gave "Drafting a reply needs a connection, and the Mac is offline. Nothing was drafted."; a local question answered normally; nothing was saved to the bank.
- Voice with Wi-Fi off was not run in this round.

## Window and Mac app

| Row | Result |
|---|---|
| Window answer types, sidebar groups, source links, Yes/Cancel, Escape, narrow and full screen | **NOT RUN** (needs eyes on the page) |
| Mac app: `app/build.sh` and open | **PASS** after also building `voice/swift` in the checkout. The user entered the key and allowed the prompts; the window server (:8765), Bonsai (:8080) and voice ("ready") came up and the calendar read 6 events. |
| "Check setup" lists no problems | **NOT CLICKED** (the menu is not visible to the test tooling); the same ingredients were checked by command and were fine |
| Fn-Space tap, type, Escape; hold Fn-Space and speak | **NOT RUN** (needs the Fn key and a voice) |
| Quit Muse leaves no stray servers on :8765 | **PASS.** After `osascript -e 'tell application "Muse" to quit'`, nothing was listening on :8765. |
| Muse.dmg (v0.1-test, 0.1 MB), inspected, not installed | Ad-hoc signed, arm64, `MuseRepo` empty, `setup.sh` read (asks before every download, no sudo) but not run. Right-click Open not exercised (the file came by `gh`, which adds no quarantine flag). |

## Anything in harness/ that broke or behaved oddly

- **Two window servers on one profile give a confusing failure.** With a round-1 window still holding `~/.harness/profile`, "Who wrote Frankenstein?" returned "Not found after 3 search(es) and 13 page(s) (13 unreadable)". Another process holding the profile made every Wikipedia page unreadable and gave no hint.
- **Raw Playwright error in an answer.** A draft "yes" with the profile locked returned the full launch log ("Failed to create a ProcessSingleton for your profile directory ...").
- **Dead event loop after a failed launch.** After that failed launch, the next harness call in the same process returned "It looks like you are using Playwright Sync API inside the asyncio loop"; only restarting the window helped. A later commit in `harness-email` (`session.py`) appears to fix this.
- **Web answers are saved automatically.** Off-topic or misheard questions ("Elena asked me", "What did everyone ask me?") ran the web route, returned a random page (a Facebook post, a conversation-topics site) and filed it into the bank as "your notes"; later questions then answered from it. (Fixed in main afterwards: web answers are saved only on a yes.)
- **`app_open` and `draft.reply` as called by the app:** `app_open` works (Calendar). `draft.reply` is blocked by the test-account guard on this Mac, so its success path was not run.
- **Environment note:** Calendar.app offered only iCloud for new calendars ("On My Mac" was not enabled), so the "Muse demo" calendar was created in iCloud and deleted again afterwards.
