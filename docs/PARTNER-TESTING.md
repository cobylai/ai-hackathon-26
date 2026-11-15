# Testing guide for Antranig's agents (2026-11-15)

Start from `main` (45db04f or later). Read `docs/PARTNER-UPDATE.md` first: it says
what changed in your code (only `harness/llm.py`) and what we added.

**Web search is ours.** Coby's side is fixing the web route (a size limit),
so skip web search and `gather` testing. Test everything below.

## What we need from you

1. Setup works on your Mac from this file alone. Note any step that fails.
2. The test runs below pass, or a list of what failed, with output.
3. The demo questions below, typed and then spoken, with what came back.
4. A run with **Wi-Fi actually off** (we only blocked the network in a sandbox).
5. Your own code still behaves inside the merge: email reading on a real
   thread, and tools that we don't call (computer control, email_asks, drafts).

Report back to Coby: one line per item, pass or fail, with the output for
failures. Don't push to `main`; use a branch, e.g. `partner-testing`.

## Setup (online, once)

```bash
git checkout main && git pull
uv sync
uv run playwright install chromium            # chromium-1255, what the locked Playwright uses
```

`.python-version` pins Python 3.12 for `uv`. Under 3.14 the Playwright tests hang. If an old `.venv` was made with 3.14, delete it and run `uv sync` again.

**Bonsai 2 4B (every model call).** The models are not in git. Get
`bonsai2-4b-mlx` into `samples/bonsai-models/mlx/models/` and make the venv,
per `samples/bonsai-models/mlx/README.md` (Python 3.12+; mlx needs 3.10+). Then:

```bash
curl -s localhost:8080/v1/models || scripts/serve_bonsai.sh 4B    # one server at a time, :8080
```

`llm/client.py` refuses any URL that isn't localhost (`BONSAI_BASE_URL`).

**Voice (Argmax), optional; skip it if you only test typing.**
- You need your own runtime key (`ax_...`, one per application, from Argmax at
  the event) as `ARGMAX_API_KEY`, and the Argmax registry login for the Swift
  package (`docs/argmax.md`). Don't use or paste Coby's key.
- The model folder: `~/Documents/huggingface/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB`
  (or set `ARGMAX_MODEL_FOLDER`). Download it while online.
- Build: `cd voice/swift && swift build -c release && cd ../..`
- First launch compiles for about **250 s** (cache in `~/Library/Caches/argmax-voice`).
  Allow the Keychain and microphone prompts for your terminal app.
- Check: `python -m voice.listen` (Enter to start, Enter to stop).
- More: `docs/voice-input.md`.

## Test runs

```bash
uv run pytest -q                                               # your harness tests: expect 271 passed, 3 skipped
for d in reason bank sufficiency; do uv run python -m unittest discover $d/tests; done
                                                               # expect 30 / 49 / 41 OK (no model server needed)
```

## Demo bank (fake inbox, 20 emails, 13 made-up senders)

The demo answers from sample mail, not anyone's real inbox. Build it outside
the repo, with "today" set to the day you test (dates are offsets from it):

```bash
DAY=2026-11-15
rm -rf ~/muse-demo-mail ~/muse-demo-bank
uv run python scripts/make_test_mail.py write ~/muse-demo-mail --today $DAY
MUSE_BANK_DIR=~/muse-demo-bank uv run python -m bank.load ~/muse-demo-mail --kind email
MUSE_BANK_DIR=~/muse-demo-bank uv run python scripts/make_test_mail.py check ~/muse-demo-mail --today $DAY --offline
```

The check scores 38 questions. Ours: **37/38** (the one miss is listed below).

(Coby's demo bank went through Gmail pages instead: `scripts/make_test_threads.py`
and `sync_test_threads.py`, which need a saved Gmail thread page as a template.
See "Demo bank" in `docs/integration.md`. Same emails, same score.)

## Run the app

```bash
MUSE_BANK_DIR=~/muse-demo-bank uv run python -m reason.web      # http://localhost:8765
MUSE_BANK_DIR=~/muse-demo-bank uv run python -m reason          # chat loop in the terminal; empty line = talk
```

Voice needs `ARGMAX_API_KEY` in the same shell. Without it, typing still
works and the window says voice is unavailable. Click "N items in bank" for
the list of what's saved.

**Demo questions** (type them, then speak them; note any it mishears):
- What did Felix ask me? / Hugo / Ivy (should say "no ask") / Jonah / Greta / Omar / Lena / Milo
- What's due this week? / What's due tomorrow?
- What did Zelda ask me? -> "I have nothing from Zelda." (no such sender)

Use easy names when speaking. Whisper heard "Coby" as "Kobe". Avoid Nina
(there are two), Tess, Kiri and Rafe.

**Wi-Fi-off run:** start Bonsai and the window while online, turn Wi-Fi off,
then ask the list again. Expect the same answers. Anything that needs the web
says "I don't have that saved, and the Mac is offline".

## What works (checked on Coby's Mac)

- Every model call goes to local Bonsai 2 4B on :8080. No cloud anywhere.
- Routes, from `reason.answer(question, today)`:
  - **due**: dated list, plain code, about 0.0 s. On Sat/Sun, "this week" runs
    today to Sunday. Each row shows its summary (amounts come along).
  - **person** ("what did X ask/want/need"): each entry's ask, listed by code,
    no model. An unknown name says "I have nothing from X".
  - **bank**: search plus judge, about 1 to 1.5 s.
  - **offline**: the message above.
- Voice: about 1.1 to 1.25 s from stop to text, correct with the network
  blocked, in both the chat loop and the window.
- Live Gmail sync into the bank (`scripts/sync_email.py`), with your reader, on
  a test account. No duplicates on a re-run. Gmail's "14 Nov 2026, 22:24"
  date format is parsed.
- Your harness tests: 271 pass in the merged tree.

## What doesn't work / known limits

- **Web route** (Coby's side is on it): over a size limit. Bing is used when
  Google/DDG are BLOCKED. Online check = one connect to www.bing.com, so a
  captive portal counts as online.
- Bank miss: "What are the team name options for the hackathon?" The bank keeps
  a 1 to 2 sentence summary, and the summary dropped the options.
- Questions with "due/deadline/when" get the dated list, not a one-line answer.
- Person names must come back from Whisper spelled like the sender's name.
- Two senders with the same first name are both listed.
- "What did X say about Y" still uses the model, so it can misread.
- Google's welcome mail is filed with course "LLC 1600" (from its address footer).
- Not tested: a real Wi-Fi-off run; your computer-control, email_asks and
  draft tools inside the merge (the app doesn't call them).
- Gmail sign-in: after `uv run python -m harness login https://mail.google.com`,
  quit Chrome for Testing with Cmd+Q. A closed window keeps the profile lock.
