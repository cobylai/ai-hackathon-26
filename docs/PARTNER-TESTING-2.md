# Testing round 2 for Antranig's agents (2026-11-15)

Round 1 is `docs/PARTNER-TESTING.md` (your round 1 report is `docs/PARTNER-TEST-REPORT.md`; its fixes are in progress). Do its setup first if you haven't. This
round covers what landed since. Start from `main` (a8ecbca or later).

## What changed since round 1

- **Python 3.12 is pinned** (`.python-version`). If your `.venv` was built on
  3.14, delete it and run `uv sync`: Playwright tests hang on 3.14.
- **Web search fix**: off-topic Bing hits are dropped, and Wikipedia's public
  search fills in. Web questions now answer in about 8 to 11 s.
- **Playbooks** (`playbooks/`): one markdown file per question kind, plus
  `RULES.md`. The code reads the wording, triggers and prompts from them.
  `python -m reason.playbook_check` scores the examples in each file.
- **Apple Calendar** (`applecal/`): reads one Calendar.app calendar, "Flux demo".
- **Memory**: "remember that ...", "what do you know about me", "forget that".
  **Person pages** have an API for discovery (`bank.people`).
- **Discovery** (`discover/`): the window's Discover button (or "discover") asks yes/no questions about you and only keeps confirmed facts. Try yes, no, skip, and a second run.
- **Mock Canvas** (`canvas/`, `scripts/*canvas*`): kind="canvas" bank entries
  with due dates from the page.
- **Acting** (`reason/act.py`): "open my calendar", "draft a reply to X saying
  yes", "open the assignment page". It always asks for a yes and never sends.
  It calls your `app_open` and `draft.reply`, and nothing in `harness/` changed.
- **Catch me up**: "catch me up" / "what's my day" puts today's calendar, the
  next two days of deadlines and recent asks in one answer.

- **Whole-word bank search**: "book" no longer matches "notebook", and
  questions about you ("my lab") rank your own notes first.
- **Window redesign** (`python -m reason.web`): answers read like a document,
  with dates in tables, a grouped bank sidebar (mail, coursework, about you,
  people), Yes/Cancel shown inline, and a talk control with three states.
- **Mac app** (`app/`): a menu-bar app with a Spotlight-style panel.
  **Fn-Space** tap shows it; hold to talk (it asks for Accessibility once). It asks once for your own
  Argmax key (kept in the Keychain) and checks the setup at launch. See
  "Mac app" in `docs/window.md`.

- **Follow-ups** (`reason/session.py`): "and tomorrow?", "what about Friday?", "and Felix?", "the first one", "who sent that?", "open it" (asks for a yes). Answered by code from the last answer.
- **Speak button** (window) / `--speak` (chat loop): reads answers aloud with macOS `say`. Off by default; talking stops it.
- **No web for chit-chat**: greetings, mic checks, misheard names and "what did everyone ask me" now stay off the web (your round 1 bug 8). Bot-check and error pages are never saved (bug 7).
- **Bank** is now a right-side slide-over (bank button, Done, Escape or ⌘B).
- **Install on another Mac**: `Flux.dmg` (ask Coby): drag Flux to Applications, open it, and its Set Up window installs the parts. See "Ship to another Mac" in `docs/window.md`.

Still being built, so don't test these yet: saved chats on the left, bigger computer control (Mail/Settings/Chrome), and suggested replies.

## Setup additions

```bash
git checkout main && git pull
rm -rf .venv && uv sync            # only if your .venv is 3.14 (uv run python --version)
```

**Calendar:** in Calendar.app, File > New Calendar, put it under "On My Mac",
and name it **Flux demo**. Add 5 or 6 made-up events over the next week, with
a title, time and location. The first calendar question triggers a macOS
Automation prompt for your terminal app; click Allow.

**Demo bank:** rebuild it with today's date, the same way as in round 1
(`make_test_mail.py write ... --today <today>`, then `bank.load`).

**Canvas:** the generator needs saved Canvas pages as templates
(`scripts/demo/save_canvas_pages.py <your canvas url>`, which saves them under `data/`,
gitignored). This is optional. If you skip it, test Canvas through the unit
tests only.

## Test runs

```bash
for d in reason bank sufficiency applecal canvas; do uv run python -m unittest discover $d/tests; done
                      # expect about 93 / 65 / 48 / 9 / 10 OK (or more, if main moved)
uv run pytest -q      # your harness: 271 passed, 3 skipped (on 3.12)
FLUX_BANK_DIR=~/flux-demo-check-bank uv run python -m reason.playbook_check
                      # every example right; calendar examples need your "Flux demo" calendar
```

## Things to try (typed, then spoken)

Run `FLUX_BANK_DIR=~/flux-demo-bank uv run python -m reason` (an empty line
starts talking), or the window `uv run python -m reason.web`.

| Ask | Expect |
|---|---|
| What's on my calendar this week? / When is my next event? / Am I free Monday? | Events from "Flux demo", with "Source: Apple Calendar (Flux demo)" |
| Remember that my lab is Tuesdays at 2. | "Got it. I'll remember: ..." |
| What do you know about me? | That note, "Source: your notes" |
| When is my lab? | "Tuesdays at 2", sourced to your note |
| Forget that. | "Forgotten: ..." |
| Catch me up / What's my day? | Calendar, due soon, and open asks, each with its source |
| Open my calendar, then yes | Calendar.app opens; ~/.harness/actions.log shows ALLOW |
| Open Safari | Refused: it isn't on the allowlist |
| Draft a reply to <a sender> saying yes, then yes (online, Gmail signed in) | "Saved a reply draft ... It was not sent." Check Drafts. |
| The same draft request offline | Says it needs a connection; nothing drafted |
| What's due this week? then "and next week?" then "the first one" | Follow-ups answer from the last list |
| Hey, can you hear me okay? | A short reply, no web search |
| Who wrote Frankenstein? (online) | Mary Shelley, with a source, in about 10 s |
| Edit one line of `playbooks/due.md` wording, restart, ask a due question | The new wording shows (playbooks reload on restart) |

## Wi-Fi-off run (round 1 item 4, now with more routes)

Start Bonsai and the window while online, turn Wi-Fi off, then ask: a due
question, a person question, a calendar question, remember/forget, catch me up,
and "open my calendar". Note anything that hangs, errors or answers
differently than it did online. Web and draft requests should say they're
offline.

## Window and Mac app

- Window: check that each answer type above looks right, the sidebar groups
  and source links work, Yes/Cancel shows inline, and Escape cancels. Try a
  narrow window and full screen.
- Mac app on a spare Mac: the disk image and its install page, see "Ship to another Mac" in `docs/window.md` (`app/make_dmg.sh` → `app/dist/Flux.dmg`).
- Mac app from your checkout: `app/build.sh`, then open `app/build/Flux.app`. On first launch,
  enter your own Argmax key and allow the mic, Calendar and Accessibility prompts. "Check
  setup" in the menu should list no problems. Then, from another app: tap
  Fn-Space, type a question, press Escape; hold Fn-Space, say
  "what's due this week", and let go. Quit Flux should leave no stray
  servers (`lsof -iTCP:8765 -sTCP:LISTEN`). The app runs the servers from the
  checkout recorded at build (yours, when you build it), or the one set with
  `defaults write local.ai-hackathon-26.flux FluxRepo <folder>`.

## Report back

Commit your results on a branch (not `main`), e.g. `partner-testing` with a
file `docs/test-results/antranig-round2.md`:
- one line per row above: pass or fail, plus the output for failures
- the test counts and the playbook_check score
- the Wi-Fi-off results
- anything in `harness/` that broke or behaves oddly now that it's called (app_open, draft.reply)
