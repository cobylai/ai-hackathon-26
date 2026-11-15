# Partner test report (Antranig's side), 2026-11-14

Tested `main` at 0e65978 (`origin/main` has since moved 7 commits; not retested) in a fresh worktree on branch `partner-testing`. Mac: Apple Silicon, macOS 27. Every model call went to local Bonsai 2 4B on localhost:8080. Web search and gather were skipped as asked.

## What we need from you

| # | Item | Result |
|---|---|---|
| 1 | Setup from the guide alone | PASS with 3 gaps (below) |
| 2 | Test runs | PASS |
| 3 | Demo questions, typed | PASS (11/11 as expected) |
| 3 | Demo questions, spoken | PASS for routing, with one real bug (see Voice and problem 7) |
| 4 | Wi-Fi-off run | PASS for typed answers (see Wi-Fi-off run); voice while offline not captured |
| 5 | Own code inside the merge | PASS for email reading and computer control; draft tools not run live (see below) |

## Test counts

| Suite | Expected | Got |
|---|---|---|
| `uv run pytest -q` | 271 passed, 3 skipped | **274 passed, 0 skipped** (the 3 skips are the uBlock Origin Lite tests; they ran because the extension is installed here) |
| `python -m unittest discover reason/tests` | 30 OK | 30 OK |
| `python -m unittest discover bank/tests` | 49 OK | 49 OK |
| `python -m unittest discover sufficiency/tests` | 41 OK | 41 OK |

## Demo bank check

`make_test_mail.py check ... --offline` with DAY set to 2026-11-14 (the real date on this Mac): **37/38** (person 14/14, nomatch 2/2, due 16/16, bank 5/6). The one miss is the known one: "What are the team name options for the hackathon?" returned "I don't have that saved, and the Mac is offline" (route offline).

## Demo questions, typed (POST /ask on the running window, 20 items in bank)

| Question | Route | Answer |
|---|---|---|
| What did Felix ask me? | person | cabin packing list: bring a sleeping bag; $35 cabin share |
| What did Hugo ask me? | person | finish two demo slides; vote on team name |
| What did Ivy ask me? | person | "no ask" (garden club newsletter) |
| What did Jonah ask me? | person | book a study room for MATH 3320 by Tue Nov 24, 5pm |
| What did Greta ask me? | person | library book hold: "Pick it up" |
| What did Omar ask me? | person | photo of the bike; sign up for intramural soccer by Sun Nov 22 noon |
| What did Lena ask me? | person | outline by Mon Nov 23 noon; review session moved (no ask); problem set 7 by Wed Nov 18 |
| What did Milo ask me? | person | add two songs to the band playlist |
| What's due this week? | due | 8 rows, Sun Nov 15 to Sun Nov 22, 0.0 s |
| What's due tomorrow? | due | Sun Nov 15: Hugo's vote |
| What did Zelda ask me? | person | "I have nothing from Zelda." |

## Own code inside the merge

- **Email reading on a real thread (read-only, Antranig's Gmail, no drafts, nothing sent):** `email_search(sender="me", days=7)` OK, 50 results, 5.0 s, 1387 chars. `email_read(n=1)` OK, 1.9 s, 334 chars. `email_asks(sender="me", days=7)` OK, 7 asks, 5.5 s (earlier branch measurement was 28.5 s).
- **Computer control, live (`scripts/eval_computer.py`):** 5/5 TextEdit jobs pass, document closed without saving, 0 documents left open.
- **Draft tools:** not run live (approval was read-only). Their unit tests are in the 274.

## Voice (spoken by Antranig into the window at localhost:8765, online)

Setup worked: Swift build, speech model download (598 MB), Antranig's own key. Spoken results, read from the window:

| Heard | Answer |
|---|---|
| (first press) | "Voice error: recording too short (0.0 s)" |
| "Hey, can you hear me okay? Hope you're doing well." | web route: not found after 3 searches, 20 pages (6 unreachable), 45.6 s |
| What did Felix ask me? | correct (person) |
| "Hugo, ask me." (misheard) | still routed to Hugo, correct |
| What did Ivy ask me? | correct, "no ask" |
| "What did Greta ask me?" | correct |
| What did Omar ask me? | correct |
| What did Lena ask me? | correct (twice) |
| "Elena asked me" (Lena misheard) | **wrong**: web route returned "Prove your humanity" (a Reddit bot-check page) and saved it to the bank |
| What did Milo ask me? | correct (twice) |
| What's due this week? | correct list, Nov 15 to Nov 22 |
| What's due tomorrow? / What's it due tomorrow? | correct, Mon Nov 16 |
| What did Zelda ask me? | correct, "I have nothing from Zelda." |
| What did everyone ask me? | **wrong**: "Prove your humanity" again |

## Wi-Fi-off run (typed, real Wi-Fi off)

A script waited for the network to drop, then asked 14 questions. The app's own status read `online: false`, 20 items in the bank. Every answer matched the online answers: the 11 demo questions, "Where is the review session now?" (Barrow Hall room 112, bank, 1.6 s), "How much is my share for the cabin trip?" (35, bank, 0.94 s). "What's the weather in Ithaca today?" returned "I don't have that saved, and the Mac is offline, so I can't look it up." (route offline). Person and due routes took 0.0 s. Voice with Wi-Fi off was not captured.

## Problems and findings

1. **Setup gap, Bonsai:** the guide says put the model in `samples/bonsai-models/mlx/models/`; in a fresh worktree that folder does not exist. `scripts/serve_bonsai.sh` worked only with `BONSAI_MODELS_DIR` and `BONSAI_VENV` pointing at an existing model folder: `BONSAI_MODELS_DIR=<dir>/models BONSAI_VENV=<dir>/.venv scripts/serve_bonsai.sh 4B`.
2. **Setup gap, voice:** the guide does not say the Whisper model download command. This worked: `hf download argmaxinc/whisperkit-coreml --include "openai_whisper-large-v3-v20240930_626MB/*" --local-dir ~/Documents/huggingface/models/argmaxinc/whisperkit-coreml`.
3. **Setup gap, DAY:** the guide hard-codes `DAY=2026-11-15`; the date here was 2026-11-14, so the check used today's date as the guide says in prose.
4. **Bonsai binds to all interfaces:** `lsof` shows `*:8080` (mlx_vlm.server default), so the model server is reachable from the local network. `reason.web` correctly binds 127.0.0.1:8765. Suggest adding `--host 127.0.0.1` in `scripts/serve_bonsai.sh`.
5. **`email_asks` numbering:** the output prefixes every ask with `2.` instead of 1 to 7. Cosmetic.
6. **Leftover test drafts in the Gmail account** from the earlier harness live runs (including a reply draft sitting in a SignUpGenius thread, plus blank drafts). Drafts only; nothing was sent. Antranig will clean them up.
7. **Bot-check page saved as an answer (real bug).** A mis-heard name ("Elena asked me") or an off-topic question ("What did everyone ask me?") goes to the web route, which returned Reddit's "Prove your humanity" page as the answer and filed it into the bank ("Saved to your notes"). The bank grew to 21 items, and later questions can return it. Reproduced twice. Cause: "prove your humanity" was not in `harness/browser/state.py` `BLOCKED_PHRASES`, so the page was classified OK. Fixed on this branch (one phrase plus a test, `tests/test_state.py`). The web route (Coby's side) should also refuse to save any BLOCKED page. The two bad entries were removed from the demo bank.
8. **Off-topic speech goes to the web:** "Hey, can you hear me okay?" triggered 3 web searches and 20 page loads (45.6 s) and sent the spoken text to search engines. A misheard name does the same. Consider answering "I have nothing from X" for a near-miss of a known name, and not searching for chat.
9. **First voice press** gave "recording too short (0.0 s)". Cosmetic.

