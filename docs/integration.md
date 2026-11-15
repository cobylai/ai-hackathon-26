# Integration: running both halves together

**Use `main`.** The `integration` branch landed on main at 0e65978 and is
retired. main holds both halves: ours (llm/, sufficiency/, bank/, reason/,
voice/) and the partner's harness/ (his four `feature/*` branches). Every
model call goes to local Bonsai 2 4B. For a partner's step-by-step setup,
see `docs/PARTNER-TESTING.md`.

## Setup (once, while online)

Run from the repo root.

```bash
# 1. Python env (uv picks Python >= 3.12; tested on 3.14.6)
uv sync

# 2. The Chromium build the locked Playwright (1.65.2) needs: chromium-1255
uv run playwright install chromium

# 3. Ad filter lists into ~/.harness/filters (optional; the browser works without)
uv run python scripts/fetch_filters.py

# 4. Only for live Gmail: one-time visible sign-in on the harness profile (~/.harness/profile).
#    Sign in to the test account, then QUIT Chrome for Testing with Cmd+Q. Closing the
#    window leaves it running, holding the profile lock, and the hidden browser cannot start.
uv run python -m harness login https://mail.google.com
```

Bonsai models and their venv live in the main checkout at
`samples/bonsai-models/mlx/{models,.venv}` (gitignored, already downloaded).

## Run

```bash
# Bonsai 2 4B on http://localhost:8080/v1 (one server at a time; reuse a running one)
curl -s localhost:8080/v1/models || scripts/serve_bonsai.sh 4B

# The demo: chat window on the sample-mail bank (see "Demo bank" below)
FLUX_BANK_DIR=~/flux-demo-bank uv run python -m reason.web

# Tests: harness tests/ and our packages are separate runs
uv run pytest -q
uv run python -m pytest -q bank/tests sufficiency/tests reason/tests
```

## Demo bank: `~/flux-demo-bank`

The demo answers from sample mail (brief M's 20 fake emails from 13 made-up
senders, written into real Gmail thread markup), not from live sends. The
video says it is sample mail.

- Bank: `~/flux-demo-bank` (outside every checkout).
- Pages, truth.json and the saved template: `~/flux-demo-threads/`.
  `template.html` is a saved Gmail page with a real sender in it; keep it out of git.

Regenerate for the recording day (one command; set DAY to that day; Bonsai up):

```bash
DAY=2026-11-15; rm -rf ~/flux-demo-bank && uv run python scripts/demo/make_test_threads.py 99 --extra --today $DAY --template ~/flux-demo-threads/template.html --out ~/flux-demo-threads && FLUX_BANK_DIR=~/flux-demo-bank uv run python scripts/demo/sync_test_threads.py ~/flux-demo-threads && FLUX_BANK_DIR=~/flux-demo-bank uv run python scripts/demo/make_test_mail.py check ~/flux-demo-threads --today $DAY --offline
```

The chat window uses the real clock, so build the bank for the day you record.
`--today` moves the generator's "today": sent and due dates are offsets from
it, and `check` computes "this week" / "next week" / "tomorrow" with the same
weekend rule as `reason.route`.

How it works: `scripts/demo/make_test_threads.py` writes each email into a copy of
the saved message markup (sender name and address, date in the live format
"15 Nov 2026, 09:12", subject, body), drops Gmail's scripts, and scrubs the
template's real sender (it stops if any trace remains).
`scripts/demo/sync_test_threads.py` opens each page as a local file in the
partner's browser (his `Session`, on the scratch profile `data/test-profile`,
with every non-file request aborted), reads it with his `read_messages`, and
files it the way the live sync does. It refuses any bank folder without
"test" or "demo" in its name.

**Current result** (built for Sun 2026-11-15, Bonsai 4B, offline): 20/20
threads match sender, address, date and subject. Brief M's check: **37/38**
(person 14/14, no-match 2/2, due 16/16, bank 5/6). The one miss: "What are
the team name options for the hackathon?" -> "I don't have that saved".
"What's due this week?" lists 7 rows (Mon 11/16 to Sun 11/22); "What's due
tomorrow?" lists Hugo's vote (Mon 11/16 5pm).

Person questions for the video (names speech-to-text is unlikely to garble;
all right in the check): Felix, Hugo, Ivy (no ask: the newsletter), Jonah,
Greta, Omar, Lena, Milo. Avoid Nina (two of them), Tess, Kiri and Rafe.

Earlier runs, superseded: 32/37 on `data/bank-test` before worker 9's
person-route fix (brief P), then 36/37 after it, matching the text bank.

## Email -> bank sync (live Gmail)

```bash
FLUX_BANK_DIR=~/flux-bank uv run python scripts/sync_email.py 7     # last 7 days, signed-in account
FLUX_BANK_DIR=/tmp/bank uv run python scripts/sync_email.py --fixture tests/pages/gmail_thread.html
```

`email_search(days=N)` rows -> `read.open_thread` + `read.read_messages` ->
`bank.ingest(body, source="gmail:<thread_id>#<i>", kind="email", sender_name,
sender_address, sent_date (ISO), subject)` as kwargs. Read paths only: no
compose, draft or send. One search page, so at most 10 threads per sync. Keep
the bank outside the repo.

Live run (test account ilovelocalai@gmail.com, 2026-11-14): 5 threads (Coby's
demo emails 1, 3, 5, 7 plus Google's welcome mail) -> 5 entries in 28 s;
re-run 0 added. Senders, sent dates and deadlines came out right. Live Gmail
shows dates as "14 Nov 2026, 22:24"; the sync parses that and the fixture's
"Thu, Nov 12, 2026, 4:30 PM". The live-send demo (docs/demo-emails.md) was
dropped for the sample-mail bank; the partner's four emails were never synced.

Known issue, no fix (thinker ruling): Google's welcome mail is filed with
course "LLC 1600", read from its "Google LLC, 1600 Amphitheatre" footer.

## Web search for gather: `sufficiency/websearch.py`

`search(query) -> [{title, url, snippet}]`: the partner's
`harness.search.engine.search` (Google, then DuckDuckGo) first; when that
returns nothing, Bing results read in the same hidden browser. On this network
Google answered /sorry/ and DuckDuckGo served its duck challenge every time; no
bot check is solved or bypassed. `websearch.last_engine` says which one
answered. Pages are opened with the partner's `open_page`.

Live gather on Bonsai 4B, online, 60 s limit (`scripts/live_gather.py`, all via
Bing): Mona Lisa -> Leonardo da Vinci 7.9 s; Apollo 11 -> 1969 7.2 s; boiling
point of water -> 212 °F 7.8 s (all Wikipedia). An earlier run gave Canberra,
9 November 1989 and Mary Shelley in 5 to 8 s.

## Offline readiness (Wi-Fi off)

- Bonsai: `serve_bonsai.sh` sets HF offline flags and never downloads.
- Chromium: `~/Library/Caches/ms-playwright/chromium-1255` and
  `chromium_headless_shell-1255`, downloaded 2026-11-14.
- Filters: `~/.harness/filters/easy{list,privacy}.txt`, downloaded 2026-11-14.
- With Wi-Fi off, web search and Gmail return BLOCKED/ERR; `open_page` answers
  only from its 24 h cache. The demo answers from the bank.

## Model calls: localhost only

`harness/llm.ask` calls `llm.client.chat`. A repo search (`git grep` for
chat/completions, anthropic, openai, lmstudio, ollama, httpx.post/Client,
urlopen, requests.post, outside samples/) finds one model caller,
`llm/client.py`, which raises unless `BONSAI_BASE_URL` is localhost. The only
other HTTP code is `scripts/fetch_filters.py` and `scripts/fetch_ubol.py`,
which download ad-block lists.

## Merges and conflicts (integration branch, now on main)

| Merge | Conflict | Resolution |
|---|---|---|
| feature/browser-core | `.gitignore` (add/add) | union of both sides |
| feature/web-search | none | |
| feature/email-gmail | `harness/registry.py`, `tests/test_tools.py` | kept every tool and group (web, search, email); registry test uses email-gmail's subset check |
| feature/computer-control | `harness/registry.py`, `tests/test_tools.py` | kept both imports; GROUPS keeps search + email and sets `computer: list(COMPUTER_TOOLS)`; registry test keeps the subset check (plus computer-control's `GROUPS["computer"]` assert) |
| sufficiency-check (2a7af5a) | none | |
| context-store (82a70a5) | `.gitignore` | union, keeps `data/` |
| main 99000fa (final context-store 6cec2f6) | none | |
| reasoning-layer | none | |

## Changes made inside harness/ (and the partner's tests, scripts, docs)

- `harness/registry.py`: merge resolution only (above). No tool changed.
- `harness/llm.py`: `ask()` keeps its signature, `last_usage`, `_coerce` and
  `FakeLLM`, but calls `llm.client.chat` instead of `httpx.post`. Removed
  `base_url()`, `model()` and the `LLM_BASE_URL` / `LLM_MODEL` /
  `LLM_REASONING_EFFORT` env vars (server and size come from
  `BONSAI_BASE_URL` / `BONSAI_SIZE`). With `choices`, the prompt ends
  "Reply with exactly one of: A, B." instead of a JSON-schema enum. Errors
  still return "" but are printed to stderr. Sampling is the client's
  non-thinking preset (temperature 0.7), not temperature 0.
- `tests/test_prompts.py`: the `llm.ask` tests patch `llm.client.chat`
  instead of `httpx.post`; the endpoint-URL and reasoning-effort tests were
  replaced by a "goes through the Bonsai client" test.
- `tests/test_tools.py`: merge resolution only (above).
- `scripts/eval_search.py`: docstring no longer points at LM Studio.
- `docs/plan/00-overview.md`: removed "point it at Claude (claude-haiku)".
- `.gitignore`: union (above), plus `data/`.

A Bing fallback was briefly added to harness/search (ed93e1c) and reverted in
the next commit, on the thinker's ruling to keep harness/ untouched. Net
change to harness/search: none.

## Not done

- 30 test threads: brief M's generator has 20 emails, so the test and demo
  banks hold 20.
- Voice run of the video's person questions on `~/flux-demo-bank` (needs Coby).
