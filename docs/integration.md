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
| sufficiency-check (2a7af5a) | none | |
| feature/computer-control | `harness/registry.py`, `tests/test_tools.py` | kept both imports; GROUPS keeps search + email and sets `computer: list(COMPUTER_TOOLS)`; registry test keeps the subset check (plus computer-control's `GROUPS["computer"]` assert) |

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
- `harness/search/bing.py` (new): Bing results parser, same `Result` shape,
  reuses ddg's helpers; unwraps `bing.com/ck/a?u=a1<base64>` links.
- `harness/search/engine.py`: after Google and DuckDuckGo both fail, tries Bing
  (`_bing`, waits for `load` because Bing navigates again after
  DOMContentLoaded). If Bing also has nothing, the earlier status word
  (e.g. BLOCKED) is kept. Bing is not remembered like the DDG fallback, so a
  walled network costs two failed loads per query (~1.5 s). `_run` gained an
  optional `wait_until` argument (default unchanged).
- `tests/test_ddg.py`: the walled-DDG test now expects a third visit (Bing).
- `tests/test_bing.py`, `tests/pages/bing_results.html` (new): parser tests
  on a trimmed real Bing page (result list only).

## Live gather result (2026-11-14, online, Bonsai 2 4B, max_seconds=60)

Run 1 (Bing read by our script, before the engine had Bing):

| Question | Answer | Source | Seconds |
|---|---|---|---|
| What is the capital of Australia? | Canberra | worldatlas.com/articles/what-is-the-capital-of-australia.html | 5.4 |
| When did the Berlin Wall fall? | 9 November 1989 | en.m.wikipedia.org/wiki/Fall_of_the_Berlin_Wall | 8.1 |
| Who wrote the novel Frankenstein? | Mary Shelley | en.m.wikipedia.org/wiki/Frankenstein | 7.6 |

Run 2 (his `engine.search` end to end: Google walled -> DDG walled -> Bing):

| Question | Answer | Source | Seconds |
|---|---|---|---|
| What year did Apollo 11 land on the Moon? | 1969 | en.m.wikipedia.org/wiki/Apollo_11 | 9.7 |
| What is the boiling point of water in Fahrenheit? | 212 °F | en.wikipedia.org/wiki/Boiling_point | 8.2 |
| Who painted the Mona Lisa? | Leonardo da Vinci | en.wikipedia.org/wiki/Mona_Lisa | 7.6 |

From this Mac, Google answered /sorry/ and DuckDuckGo served its duck
challenge on every try. No challenge was solved or bypassed.

## Email -> bank sync

```bash
# live: last 7 days of the signed-in Gmail (keep the bank outside the repo)
MUSE_BANK_DIR=~/muse-bank uv run python scripts/sync_email.py 7
# saved thread instead of live mail
MUSE_BANK_DIR=/tmp/bank uv run python scripts/sync_email.py --fixture tests/pages/gmail_thread.html
```

`email_search(days=N)` rows -> `read.open_thread` + `read.read_messages` ->
`bank.ingest(body, source="gmail:<thread_id>#<i>", kind="email", sender_name,
sender_address, sent_date (ISO), subject)`. Read paths only: no compose,
draft or send. One search page, so at most 10 threads per sync. Fixture run:
3 messages -> 3 entries in 13.1 s; re-run 0 added (dedup).

## Not run yet

- Live Gmail sync (waits for Coby to sign in to the test account).
