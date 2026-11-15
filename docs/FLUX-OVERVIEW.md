# Flux: what it is and what it is supposed to do

Read from `cobylai/ai-hackathon-26` (`main`, plus the branch list and the partner-testing branches) on 2026-11-15, about 01:45 ET. The submission is due **noon today**.

**What I read:** `README.md`, `docs/submission.md`, `docs/reasoning-layer.md`, `docs/PARTNER-UPDATE.md`, the Air round-2 results on `partner-testing-air`, and the file and commit listings. **What I did not read:** the Python and Swift source, the other docs under `docs/`, or the partner-test branches in full. Anything below about how the code works comes from those docs, not from running it.

## In one paragraph

Flux is a Mac assistant for students. It answers questions about your own mail, coursework, calendar and notes, out loud or typed, **entirely on your Mac, including with Wi-Fi off**. You hold Fn-Space and ask "catch me up", "what's due this week", or "what did Felix ask me", and it answers in about a second. Every model call goes to a local Bonsai 2 4B model, and speech-to-text runs on-device through Argmax. Its main trick: **most questions use no model at all**. Code reads a local "bank" of filed mail, coursework and notes and answers directly in 0.0 s. It was built by Coby Lai and Antranig at the local-AI hackathon (2026-11-14 to 15). It was called Muse until it was renamed Flux.

The demo runs on **sample data** (made-up senders and courses written into real Gmail and Canvas page markup, and a made-up "Flux demo" calendar). No real inbox is shown.

## The problem and the idea

Students live in mail, Canvas and a calendar. Flux files that material into a private local store while you're online, then answers from it when you're offline. A question the bank can't answer is searched on the web while online, answered only with a quoted line from the page, cited, and saved. The same question then works offline later.

## How it fits the hackathon rules

| Rule | How Flux meets it |
|---|---|
| Every LLM call is Bonsai 2 | One client (`llm/client.py`) makes every call and raises unless the server is on localhost. Antranig's `harness/llm.ask` was rewired to use it. A repo search found no other model callers outside `samples/`. |
| Argmax is required | Push-to-talk runs through the Argmax Pro SDK on-device (Whisper large-v3 turbo, loaded from a local folder, downloads off). |
| Runs with Wi-Fi off | Answers come from the local bank and Apple Calendar's local copy. Web and Gmail-draft requests say they're offline, not fail. |
| 32k context | The client counts tokens before every send and raises an error if prompt plus reply would pass 32,768. It never silently truncates. Long mail splits at 6,000 tokens. |
| Right-sizing (Sustainability prize) | Bonsai 4B beat 9B on a side-by-side check (same accuracy on the fixtures, faster, 2.2 GB vs 3.8 GB peak). Due dates, "what did X ask me", calendar, catch-me-up, memory, follow-ups, suggestions and computer-control answers are plain code with no model call. |

Prizes entered: Main track (Argmax voice) and Sustainability.

## What it does

- **Due:** "what's due this week / tomorrow / Friday", mail and Canvas deadlines together, each with its source.
- **People:** "what did Felix ask me", "who is Hugo". Misheard names are handled in code.
- **Calendar:** "what's on my calendar tomorrow", "am I free Monday" (Apple Calendar, one calendar called "Flux demo").
- **Catch me up:** today's calendar, the next three days of deadlines and recent asks, in one answer.
- **Memory:** "remember that my lab is Tuesdays at 2", "what do you know about me", "forget that".
- **Discovery:** up to 10 yes/no questions about you, built from the bank. Only a yes is kept.
- **Web:** a factual question the bank can't answer is searched online, answered with a quoted line and filed.
- **Suggestions:** at most two next steps under an answer, for example "You're free Thursday at 7pm. Draft a yes to Milo?" (it checks the calendar).
- **Drafts:** an editable draft box, and "Open in Mail" hands it to Mail as a new message. **Nothing is ever sent.**
- **Computer control:** "open it", "add Milo's band practice to my calendar", "remind me about homework 9". It shows what it will do and waits for a yes. Text inside an email is never treated as an instruction. The only writes are one event or one reminder.
- **Follow-ups:** "and tomorrow?", "the first one", "open it".
- **Front ends:** a chat window, a terminal loop, and a menu-bar Mac app (Fn-Space to show, hold to talk), with saved chats and optional spoken answers.

## How it is built

```
question (voice via Argmax, or typed)
   -> reason/: code picks the route (the model never chooses a tool)
        due | person | calendar | memory | bank | web | compose | computer ...
   -> bank/: local markdown store of mail, coursework, notes, people
   -> only if needed: Bonsai 2 4B via llm/client.py (localhost only, 32k guard)
   -> sufficiency/: judges whether saved notes or a web page really answer
   -> harness/: hidden browser, web search, Gmail reading and drafts, app control
   -> answer + its source line
```

Each route's wording and triggers live in markdown playbooks (`playbooks/`), which the code reads, so behaviour can be changed by editing a file.

| Part | Folder | Built by |
|---|---|---|
| Bonsai client, 32k guard | `llm/` | Coby |
| Bank, sufficiency judge, routing and answers, playbooks, window | `bank/`, `sufficiency/`, `reason/`, `playbooks/` | Coby |
| Argmax voice, Apple Calendar, mock Canvas reader, discovery | `voice/`, `applecal/`, `canvas/`, `discover/` | Coby |
| Mac app and DMG | `app/` | Coby |
| Hidden browser, web search, Gmail reading and drafts, computer control | `harness/` | Antranig |

Antranig's four `feature/*` branches are merged into `main`, with one change: `harness/llm.ask` now calls the shared Bonsai client.

## Results on record

- Many-sender check on the demo bank (20 sample emails, 13 senders), offline: **37/38**.
- Sample coursework: 24/24 assignments matched.
- Playbook examples: 69/69 with the network blocked (since extended with more examples).
- First partner test (other Mac): setup from the guide, all test suites, 11/11 typed demo questions, and a real Wi-Fi-off run where every typed answer matched the online one.
- Voice with the network denied (`sandbox-exec`): "What's due this week?" heard exactly, answered in 0.0 s.
- Second partner test, a MacBook Air (M1, 8 GB, tested remotely over SSH): all suites pass (pytest 272 passed, 3 skipped), demo bank check 37/38, model answers 2.8 to 4.2 s (about 3x slower than the first Mac), plain-code answers still 0.0 s. Wi-Fi-off check passed ("I don't have that saved, and the Mac is offline"). **Web search failed on the campus network** (IPv6 broken). Voice, the Mac app, calendar rows and Canvas were not testable remotely. The calendar-related playbook examples failed there (80/106) because that Mac had no "Flux demo" calendar or Canvas templates.

## Known limits (from the README)

- **Sample data only.** Not checked on a real inbox. Live Gmail sync works on a test account (at most 10 threads); Canvas is read from saved pages, not live.
- **The full Wi-Fi-off run with voice has not been recorded.** Typed answers were checked with real Wi-Fi off, and voice only under `sandbox-exec`, which isn't the same.
- **Names by voice:** Whisper can mishear a name ("Coby" became "Kobe"). Easy names work (Felix, Hugo, Ivy, Jonah, Greta, Omar, Lena, Milo).
- **Bank summaries lose details**, for example a question about team-name options misses.
- **Web search** depends on Bing and Wikipedia answering the hidden browser; Google and DuckDuckGo bot-wall it, and no bot check is bypassed. One known wrong web answer is on record (Cornell's founding year).
- **Calendar:** one calendar; repeating events show only once.
- **Mac app:** Developer ID signed, **notarization pending** (right-click and Open the first time). Each Mac needs its own Argmax key.
- **Release page:** built but not deployed; link still to come.

## What is left before the noon deadline

From `docs/submission.md`:
- **Post to Discord:** both names, a one-sentence description, prizes, repo link, and a video of 2 minutes or less.
- **Record the demo video.** A beat-by-beat script is in `docs/submission.md`. It needs the demo bank rebuilt for today, the calendar set up, and one full rehearsal offline.
- **The full Wi-Fi-off voice run**, end to end, has not been done. The submission pack calls it an open risk.
- **Check the repo is reachable by the judges.** It is currently **private**.
- **Privacy review of git history** (decisions for Coby): Antranig's Cornell address is in the author field of his commits, and real course codes and email subjects from a real mailbox remain in a test fixture (`tests/pages/gmail_list.html`) and some eval notes. The docs were scrubbed in the current tree, but history was not rewritten. No keys or tokens were found.
- **Notarization** of the Mac app and the **release page** link.

Also unfinished: the final partner test round (`docs/PARTNER-TESTING-FINAL.md`) has no results in the repo yet, and the repo's own docs still mention "Flux or Hearth, undecided" even though everything has been renamed to Flux.

## How this connects to the earlier harness work

The `harness/` package is the part Antranig built: the hidden browser, web search, Gmail reading and drafting, and app control, all on the four feature branches. The Flux app calls it through `harness/registry.py` and `harness/llm.py`. The "integration" problem noted in my earlier hand-off document (merging the four branches and wiring the registry) is **already done on `main`**. What the repo says is open there is mainly the privacy cleanup and the Wi-Fi-off voice run above, not the harness features.
