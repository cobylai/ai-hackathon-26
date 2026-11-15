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
- `.gitignore`: union (above).

## Live gather result (2026-11-14, online, Bonsai 2 4B, max_seconds=60)

| Question | Answer | Source | Seconds |
|---|---|---|---|
| What is the capital of Australia? | Canberra | worldatlas.com/articles/what-is-the-capital-of-australia.html | 5.4 |
| When did the Berlin Wall fall? | 9 November 1989 | en.m.wikipedia.org/wiki/Fall_of_the_Berlin_Wall | 8.1 |
| Who wrote the novel Frankenstein? | Mary Shelley | en.m.wikipedia.org/wiki/Frankenstein | 7.6 |

Search caveat: from this Mac, Google answered /sorry/ and DuckDuckGo served
its duck challenge, so `engine.search` returned BLOCKED for every query. No
challenge was solved. `scripts/live_gather.py` (ours, not in harness/) then
reads Bing results in the same hidden browser; pages were opened with the
partner's `open_page`. harness/search itself has no Bing engine.

## Not run yet

- Email sync into bank/ (waits for context-store and a Gmail login).
