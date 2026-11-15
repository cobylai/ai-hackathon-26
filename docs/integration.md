# Integration: running both halves together

Branch `integration` = main (llm/, sufficiency/, bank/) + the partner's four
`feature/*` branches (harness/). Every model call goes to local Bonsai 2 4B.

## Setup (once, while online)

Run from the repo root (or a worktree of it).

```bash
# 1. Python env for harness/ (uv picks Python >= 3.12; tested on 3.14.6)
uv sync

# 2. The Chromium build the locked Playwright (1.65.2) needs: chromium-1255
uv run playwright install chromium

# 3. Ad filter lists into ~/.harness/filters (optional; browser works without)
uv run python scripts/fetch_filters.py

# 4. One-time visible sign-in to Gmail in the harness profile (~/.harness/profile)
uv run python -m harness login https://mail.google.com
```

Bonsai models and their venv live in the main checkout at
`samples/bonsai-models/mlx/{models,.venv}` (gitignored, already downloaded).

## Run

```bash
# Bonsai 2 4B on http://localhost:8080/v1 (one server at a time; reuse a running one)
curl -s localhost:8080/v1/models || scripts/serve_bonsai.sh 4B

# Tests (harness tests/ and our sufficiency tests are separate runs)
uv run pytest -q
uv run python -m pytest -q sufficiency/tests

# Live: typed questions through gather with the partner's browser
uv run python scripts/live_gather.py "What is the capital of Australia?"
```

## Offline readiness (Wi-Fi off)

- Bonsai: `serve_bonsai.sh` sets HF offline flags and never downloads.
- Chromium: `~/Library/Caches/ms-playwright/chromium-1255` and
  `chromium_headless_shell-1255` downloaded on 2026-11-14 (only 1248 was there
  before, which the locked Playwright does not use).
- Filters: `~/.harness/filters/easy{list,privacy}.txt` downloaded 2026-11-14.
- With Wi-Fi off, web search and Gmail return BLOCKED/ERR text; `open_page`
  answers only from its 24 h cache. The offline demo answers from bank/.

## Model calls: localhost only

`harness/llm.ask` now calls `llm.client.chat`. A repo search
(`git grep` for chat/completions, anthropic, openai, lmstudio, ollama,
httpx.post/Client, urlopen, requests.post, outside samples/) finds one model
caller, `llm/client.py`, which raises unless `BONSAI_BASE_URL` is localhost.
The only other HTTP code is `scripts/fetch_filters.py` and
`scripts/fetch_ubol.py`, which download ad-block lists, not model calls.

## Merges and conflicts

| Merge | Conflict | Resolution |
|---|---|---|
| feature/browser-core | `.gitignore` (add/add) | union of both sides |
| feature/web-search | none | |
| feature/email-gmail | `harness/registry.py`, `tests/test_tools.py` | kept every tool and group (web, search, email); registry test uses email-gmail's subset check |
| feature/computer-control | `harness/registry.py`, `tests/test_tools.py` | kept both imports; GROUPS keeps search + email and sets `computer: list(COMPUTER_TOOLS)`; registry test keeps the subset check (plus computer-control's `GROUPS["computer"]` assert) |
| sufficiency-check (2a7af5a) | none | |
| context-store (82a70a5) | `.gitignore` | union, keeps `data/` |
| main 99000fa (final context-store 6cec2f6) | none | |

## Changes made inside harness/ (and the partner's tests, scripts, docs)

- `harness/registry.py`: merge resolution only (above). No tool changed.
- `harness/llm.py`: `ask()` keeps its signature, `last_usage`, `_coerce` and
  `FakeLLM`, but calls `llm.client.chat` instead of `httpx.post`. Removed
  `base_url()`, `model()` and the `LLM_BASE_URL` / `LLM_MODEL` /
  `LLM_REASONING_EFFORT` env vars (server and size now come from
  `BONSAI_BASE_URL` / `BONSAI_SIZE`). With `choices`, the prompt now ends
  "Reply with exactly one of: A, B." instead of a JSON-schema enum. Errors
  still return "" but are printed to stderr. Sampling is the client's
  non-thinking preset (temperature 0.7), not temperature 0.
- `tests/test_prompts.py`: the seven `llm.ask` tests now patch
  `llm.client.chat` instead of `httpx.post`; the endpoint-URL and
  reasoning-effort tests were replaced by a "goes through the Bonsai client" test.
- `tests/test_tools.py`: merge resolution only (above).
- `scripts/eval_search.py`: docstring no longer points at LM Studio.
- `docs/plan/00-overview.md`: removed "point it at Claude (claude-haiku)".
- `.gitignore`: union (above), plus `data/` from context-store.

A Bing fallback was briefly added to harness/search (ed93e1c) and then
reverted (next commit) on thinker's ruling to keep harness/ untouched; it now
lives on our side in `sufficiency/websearch.py`. Net change to harness/search: none.

## Web search for gather: `sufficiency/websearch.py` (ours)

`search(query) -> [{title, url, snippet}]`: the partner's
`harness.search.engine.search` (Google, then DuckDuckGo) first; when that
returns nothing (on this Mac it says BLOCKED: Google /sorry/, DuckDuckGo duck
challenge), Bing results read in the same hidden browser. No bot check is
solved or bypassed. `websearch.last_engine` says which one answered. This is
the `search_fn` for gather; pages are opened with the partner's `open_page`.

## Live gather result (2026-11-14, online, Bonsai 2 4B, max_seconds=60)

Via `scripts/live_gather.py` -> `sufficiency.websearch.search` (all Bing, harness said BLOCKED):

| Question | Answer | Source | Seconds |
|---|---|---|---|
| Who painted the Mona Lisa? | Leonardo da Vinci | en.wikipedia.org/wiki/Mona_Lisa | 7.9 |
| What year did Apollo 11 land on the Moon? | 1969 | en.m.wikipedia.org/wiki/Apollo_11 | 7.2 |
| What is the boiling point of water in Fahrenheit? | 212 °F | en.wikipedia.org/wiki/Boiling_point | 7.8 |

Earlier run (same path, inline in the script): capital of Australia ->
Canberra (worldatlas.com, 5.4 s); Berlin Wall -> 9 November 1989 (wikipedia,
8.1 s); Frankenstein -> Mary Shelley (wikipedia, 7.6 s).

## Email -> bank sync

```bash
# live: last 7 days of the signed-in Gmail (keep the bank outside the repo)
MUSE_BANK_DIR=~/muse-bank uv run python scripts/sync_email.py 7
# saved thread instead of live mail
MUSE_BANK_DIR=/tmp/bank uv run python scripts/sync_email.py --fixture tests/pages/gmail_thread.html
```

`email_search(days=N)` rows -> `read.open_thread` + `read.read_messages` ->
`bank.ingest(body, source="gmail:<thread_id>#<i>", kind="email", sender_name,
sender_address, sent_date (ISO), subject)` as kwargs. Read paths only: no
compose, draft or send. One search page, so at most 10 threads per sync.
Fixture run on final context-store: 3 messages -> 3 entries in 9.1 s, senders
and dates right, `sent_date_guessed: false`; re-run adds 0 (dedup).

Live run (test account ilovelocalai@gmail.com, Bonsai 4B, 2026-11-14):
5 threads (Coby's demo emails 1, 3, 5, 7 plus Google's welcome mail) -> 5
entries in 28.2 s; re-run 0 added in 13.0 s. Senders, sent dates and the
three deadlines (Mon 11/16 23:59, Thu 11/19, Fri 11/20 12:00) came out right.
Live Gmail shows dates as "14 Nov 2026, 22:24", now parsed (fixture used
"Thu, Nov 12, 2026, 4:30 PM"). Gmail sign-in: after `harness login`, quit
Chrome for Testing with Cmd+Q; closing the window leaves it holding the
profile lock and the hidden browser cannot start.

Known issue, no fix (thinker ruling): Google's welcome mail is filed with
course "LLC 1600", read from its "Google LLC, 1600 Amphitheatre" footer.

## Test threads: many senders without sending mail (brief N)

```bash
# once: save one single-message thread page from the test account as the template
#   -> data/templates/thread.html (gitignored; it has the real sender in it)
uv run python scripts/make_test_threads.py 30            # -> data/test-threads/*.html + truth.json
MUSE_BANK_DIR=data/bank-test uv run python scripts/sync_test_threads.py
MUSE_BANK_DIR=data/bank-test uv run python scripts/make_test_mail.py check data/test-threads
```

`make_test_threads.py` takes brief M's emails (`scripts/make_test_mail.py`
`build()`, same senders, text and seed) and writes each into a copy of the
saved Gmail message markup: sender name and address, date (live format
"14 Nov 2026, 22:33"), subject and body. Gmail's scripts are dropped, and the
template's real sender is scrubbed from every output (the script stops if any
remains). `sync_test_threads.py` opens each page as a local file in the
partner's browser (his `Session`, on a scratch profile `data/test-profile` so
it never competes with the signed-in Gmail profile; non-file requests are
aborted), reads it with his `read_messages`, and files it with the live sync's
`file_thread` -> `bank.ingest`. It refuses to run unless MUSE_BANK_DIR is a
test bank. Everything it writes is under data/ (gitignored). If this bank
appears in the demo or video, say it is sample mail.

Result (2026-11-14, Bonsai 4B): brief M's generator has 20 emails, so 20
threads, not 30. 20 filed in 75 s; **20/20** match sender name, address,
sent date and subject. Brief M's check on that bank: **32/37 right** (person
10/14, no-match 2/2, due 15/15, bank 5/6). Wrong: Tess and Jonah "don't say"
(their asks are "confirm ... by" / "book a study room"); Felix and Ivy given
an ask from a no-ask email; the hackathon team-name question missed the bank
and timed out on the web route (the check ran online).

## Not run yet

- Re-sync after the partner's demo emails 2, 4, 6, 8 are sent.
