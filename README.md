# Flux

Flux is a Mac assistant for students that answers from your own mail, coursework, calendar and notes, entirely on your Mac. You hold a key and ask out loud ("catch me up", "what's due this week", "what did Felix ask me"), and it answers in about a second with Wi-Fi off, because every model call goes to a local Bonsai 2 4B and speech-to-text runs on-device with Argmax.

By Coby Lai and Antranig. Built at the local-AI hackathon, 2026-11-14 to 15.

> The demo answers from **sample mail and sample coursework** (made-up senders and courses written into real Gmail and Canvas page markup) and a made-up "Flux demo" calendar. No real inbox is shown.

## How it meets the rules

| Rule (2026-11-14 kickoff) | How |
|---|---|
| Every LLM call is Bonsai 2 | One client, `llm/client.py`, makes every model call. It talks only to the local Bonsai 2 server and raises unless `BONSAI_BASE_URL` is localhost. The partner's `harness/llm.ask` was rewired to call it. A repo search for other model callers (chat/completions, anthropic, openai, lmstudio, ollama, httpx/requests/urlopen) finds none outside `samples/` ([docs/integration.md](docs/integration.md), "Model calls: localhost only"). The server script binds 127.0.0.1. |
| Argmax is required | Push-to-talk speech-to-text runs through the Argmax Pro SDK (`voice/swift`, Whisper large-v3 turbo loaded from a local folder, downloads off). |
| Runs with Wi-Fi off | Mail, coursework, notes and web answers are filed into a local bank (markdown files) while online; with Wi-Fi off, Flux answers from the bank and Apple Calendar's local copy. Web and draft requests say they're offline instead of failing. |
| 32k context | Before every send the client counts tokens with Bonsai's own tokenizer and raises `BudgetError` if prompt plus reply would pass 32,768. It never truncates silently. Long mail is split at 6,000 tokens, and web pages are judged in 6,000-token chunks ([docs/bonsai-client.md](docs/bonsai-client.md)). |
| Right-sizing | 4B was picked over 9B after a side-by-side check: same accuracy on our fixtures, faster, 2.2 GB vs 3.8 GB peak memory. Most questions use **no model at all**: due dates, "what did X ask me", calendar, catch me up, remember / what do you know about me, follow-ups, and greetings are answered by code in 0.0 s. Suggestions, free/busy checks, opening things, adding events and reminders are code too. The model is used only to summarise mail when it's filed, to judge whether saved notes or a web page answer a question, for free-form person questions, for discovery's relation guess, and to write a draft body when no code template fits. |

## What it does

- **Due:** "what's due this week / tomorrow / Friday" lists mail and Canvas deadlines together, each with its source.
- **People:** "what did Felix ask me", "who is Hugo"; misheard names ("Elena" → Lena) and "what did everyone ask me" are handled in code.
- **Calendar:** "what's on my calendar tomorrow", "when is my next meeting", "am I free Monday" (Apple Calendar, one calendar named "Flux demo").
- **Catch me up:** today's calendar, deadlines for the next three days and recent asks, in one answer.
- **Memory:** "remember that my lab is Tuesdays at 2", "what do you know about me", "forget that".
- **Discovery:** up to 10 yes/no questions about you built from the bank and calendar; only a yes is kept.
- **Web:** a factual question the bank can't answer is searched online, answered only with a quoted line from the page, and filed, so the same question answers offline later.
- **Suggestions:** under an answer, at most two next steps from that answer's own entries, e.g. "You're free Thursday, Nov 19 at 7pm. Draft a yes to Milo?" (it checks Apple Calendar), "You have Lab then. Draft a reply proposing another time?", "Open the assignment page", "Remind me".
- **Drafts:** "draft a reply to Milo", "write an email to Felix about the cabin" open an editable draft box (To, Subject, body, the entries used). **Open in Mail** hands it to Mail as a new message; nothing is ever sent, and it works offline. (Confirmed send exists but is **off by default**: only with `FLUX_ALLOW_SEND=1`, "send it" shows the exact email with a Send button you must click, to your own or an allowlisted address; see [docs/agent/confirmed-send.md](docs/agent/confirmed-send.md).) "… in Gmail" saves a Gmail draft on the test account instead.
- **Computer control:** "open it" / "open the second one" (the email in Apple Mail, the assignment page, or the event in Calendar), "add Milo's band practice to my calendar", "remind me about homework 9 the day before", "set me up for homework 9", "open my calendar". It always shows what it will do and waits for a yes. Text inside an email is never taken as an instruction, and the only writes are one event or one reminder into "Flux demo".
- **Follow-ups:** "and tomorrow?", "and Hugo?", "the first one", "who sent that?", "open it".
- **Front ends:** a chat window, a terminal chat loop, and a menu-bar Mac app (Fn-Space to show, hold Fn-Space to talk), with saved chats and optional spoken answers (macOS `say`).

Routes and how each one answers are written as markdown playbooks in `playbooks/`; code reads their wording and triggers.

## Who built what

| Part | Folder | Built by |
|---|---|---|
| Bonsai client, 32k guard | `llm/` | Coby |
| Bank (local store of mail, coursework, notes, people) | `bank/` | Coby |
| Sufficiency judge and web gather | `sufficiency/` | Coby |
| Routing, answers, playbooks, window, chat loop | `reason/`, `playbooks/` | Coby |
| Argmax voice | `voice/` | Coby |
| Apple Calendar | `applecal/` | Coby |
| Mock Canvas reader | `canvas/` | Coby |
| Discovery | `discover/` | Coby |
| Mac app and DMG | `app/` | Coby |
| Hidden browser, web search, Gmail reading and drafts, computer control | `harness/` | Antranig |

## Setup (once, online, Apple Silicon Mac)

```bash
uv sync                                   # Python 3.12 is pinned (.python-version)
uv run playwright install chromium        # the hidden browser (Chromium build 1255)
uv run python scripts/fetch_filters.py    # ad filter lists (optional)
```

- **Bonsai 2 4B** lives in `samples/bonsai-models/mlx/models/` with its own venv in `samples/bonsai-models/mlx/.venv` (gitignored). In a fresh checkout or worktree, point at an existing copy with `BONSAI_MODELS_DIR=<dir>/models BONSAI_VENV=<dir>/.venv`.
- **Voice:** your own Argmax `ax_` key, the Argmax registry login ([docs/argmax.md](docs/argmax.md)), then:

```bash
hf download argmaxinc/whisperkit-coreml --include "openai_whisper-large-v3-v20240930_626MB/*" --local-dir ~/Documents/huggingface/models/argmaxinc/whisperkit-coreml
cd voice/swift && swift build -c release && cd ../..
```

- **Calendar:** in Calendar.app, File > New Calendar under "On My Mac", named **Flux demo**, with a few made-up one-off events (the demo adds a "Lab" event Wed 1:30–3:30pm for the busy case).
- **Demo bank** (sample mail, then sample coursework; set DAY to the day you record, Bonsai running): see "Demo bank" in [docs/integration.md](docs/integration.md) and [docs/canvas.md](docs/canvas.md).

## Run

```bash
scripts/serve_bonsai.sh 4B                                   # Bonsai 2 4B on 127.0.0.1:8080 (leave running)
export ARGMAX_API_KEY=ax_...                                 # for voice; typing works without it

FLUX_BANK_DIR=~/flux-demo-bank uv run python -m reason.web   # chat window at localhost:8765
FLUX_BANK_DIR=~/flux-demo-bank uv run python -m reason       # terminal chat loop (empty line = talk)
```

**Mac app:**

```bash
app/build.sh && open app/build/Flux.app     # menu bar; Fn-Space shows it, hold Fn-Space to talk
app/make_dmg.sh                             # app/dist/Flux.dmg: drag-to-Applications; Set Up Flux installs the rest
```

The app is signed with a Developer ID (hardened runtime); notarization is pending. On first launch an 8-screen setup window walks through the Argmax key (kept in the Keychain), Accessibility (for Fn-Space), the microphone, and Calendar, Reminders and Mail. It starts Bonsai and the window server itself if they aren't running. The first voice start on a new Mac takes several minutes (one-time Neural Engine compile). Details: "Mac app" in [docs/window.md](docs/window.md).

**Tests** (no model server, no network):

```bash
for d in reason bank sufficiency applecal canvas; do uv run python -m unittest discover $d/tests; done
uv run pytest -q                                              # harness
FLUX_BANK_DIR=~/flux-demo-bank uv run python -m reason.playbook_check   # every playbook example, network blocked
```

## Results on record

- Many-sender check on the demo bank (20 sample emails, 13 made-up senders), offline: **37/38** (person 14/14, unknown person 2/2, due 16/16, bank 5/6).
- Sample coursework: 24/24 assignments match course, title, due date and link.
- Playbook examples: 69/69 with the network blocked (run before computer control and drafts landed; those playbooks add more examples).
- Antranig's first test round on another Mac: setup from the guide, all test suites, 11/11 typed demo questions, and a real Wi-Fi-off run where every typed answer matched the online one.
- Voice with the network denied (`sandbox-exec`): "What's due this week?" heard exactly and answered in 0.0 s.

## Known limits

- **Sample data only.** Answers were checked on made-up mail and coursework, not a real inbox. Live Gmail sync works on a test account (at most 10 threads per sync); Canvas is read from saved pages, not live.
- **The full Wi-Fi-off run with voice has not been recorded yet.** Typed answers were checked with real Wi-Fi off (Antranig); voice was checked with the network denied by `sandbox-exec`, which isn't the same as Wi-Fi off. The calendar can't be read under `sandbox-exec`, so calendar-offline rests on the real Wi-Fi-off run.
- **Names by voice:** Whisper can misspell a name ("Coby" → "Kobe"); the answer is then "I have nothing from Kobe." Easy names work: Felix, Hugo, Ivy, Jonah, Greta, Omar, Lena, Milo.
- **Bank summaries lose details:** "What are the team name options for the hackathon?" misses, because the summary dropped the options.
- **Web search** depends on Bing and Wikipedia's public search answering the hidden browser (Google and DuckDuckGo bot-wall it; no bot check is bypassed). Only web questions run and checked beforehand are used in the demo. One known wrong web answer is on record (Cornell's founding year).
- **Calendar:** one calendar; repeating events show only once.
- **Free/busy and drafts** need the meeting email's day and time to be readable; otherwise the suggestion is a plain "Draft a reply". Apple Mail opens only messages in the test account.
- **Mac app:** Developer ID signed, notarization pending (until then, right-click → Open the first time). Each Mac needs its own Argmax key.
- **Final partner test round** ([docs/PARTNER-TESTING-FINAL.md](docs/PARTNER-TESTING-FINAL.md)), including Wi-Fi off by voice, has no results in the repo yet.
- **Release page:** built on a cobydev branch, not deployed; link to come.

## Hackathon rules (from the 2026-11-14 kickoff)

- Due noon Sun 2026-11-15 in the Discord submissions channel: both names, a one-sentence description, the prizes entered, a repo link, and a demo video of 2 minutes or less. Finalist demos start around 12:30.
- Every LLM call at submission time must be Bonsai 2 (2B/4B/9B).
- Argmax is required for main-track eligibility.
- It must run with Wi-Fi off. Finalists demo it offline.
- Bonsai has a 32k context; chunk or summarise long pages. Sustainability judging rewards right-sizing the model.

## Samples

`samples/` is a copy of [iBrushC/local-ai-hackathon-samples](https://github.com/iBrushC/local-ai-hackathon-samples) @ `5c72a8d`, with two fixes so the Argmax sample builds against SDK 3.1.8: `Package.swift` declares tools-version 6.0 (with 5.10, `.macOS(.v15)` fails to compile), and `LiveCommand.swift` awaits `speakerKit.makeStreamSession` with `try await`. The Bonsai sample server (`samples/bonsai-models/mlx/start.sh`) also works, but `scripts/serve_bonsai.sh` is what Flux uses: headless, offline flags, localhost only.
