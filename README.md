# ai-hackathon-26

Short text tools that let a small local model use a hidden browser: no screenshots, no
raw HTML, no vision. Every tool returns plain text that starts with `OK`, `BLOCKED`,
`LOGIN` or `ERR` and stays under 1,500 characters, so a small model can branch on the
first word and answer with a number instead of a selector.

## What is in here

| Path | What it does |
|---|---|
| `harness/browser/` | Persistent headless Chromium: numbered clickable elements, main-text extraction, ad blocking, page classification |
| `harness/search/` | Web search without an API: Google results, DuckDuckGo HTML fallback, BM25 chunk ranking, the `research` loop, SQLite page cache |
| `harness/llm.py` | One call to an OpenAI-compatible endpoint (`ask`), with optional constrained answers and real token usage |
| `harness/registry.py` | `TOOLS` / `GROUPS` (`web`, `search`, `email`, `computer`) for the reasoning layer to pick from |
| `docs/plan/` | The plan per feature and the findings notes (bot walls, benchmark, search evaluation) |
| `docs/log/` | One-line-per-change log per feature branch |

## Setup

```bash
uv sync
uv run playwright install chromium
```

## Packaging

```bash
uv build                                            # dist/harness-0.1.0-py3-none-any.whl
pip install dist/harness-0.1.0-py3-none-any.whl
python -m harness --help
```

The wheel carries `harness/browser/elements.js`, which the browser tools read at import
time; without it an installed package fails on `import harness`. `tests/test_packaging.py`
guards the declaration, and builds a real wheel when `HARNESS_BUILD_TEST=1`.

## Use it from the command line

```bash
uv run python -m harness goto https://example.com
uv run python -m harness read 2
uv run python -m harness search "berlin wall fall date"
uv run python -m harness research "when did the Berlin Wall fall?"
```

`research` runs the whole loop: search, pick results, read the best chunks of each page,
take short notes, ask itself whether the notes are enough, rewrite the query if not (at
most three rounds, two pages per round), then answer in at most 120 words with a numbered
`Sources:` line.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `LLM_BASE_URL` | `http://127.0.0.1:8080/v1` | OpenAI-compatible chat endpoint |
| `LLM_MODEL` | `local` | Model name to send |
| `LLM_REASONING_EFFORT` | unset | Set to `none` for reasoning models that otherwise return empty content |
| `HARNESS_PROFILE_DIR` | `~/.harness/profile` | Chromium profile; set it to run a second process alongside the first |
| `HARNESS_CACHE_DB` | `~/.harness/cache.db` | Page cache (24-hour TTL, keyed by URL) |

Point it at a local runtime (llama.cpp server, `mlx_lm.server`, LM Studio) or at a hosted
model; swapping is a config change, not a code change.

CI runs the suite on Python 3.12 (`uv sync`, then `uv run pytest -q`).

## Tests and the live evaluation

```bash
uv run pytest -q          # offline: fixtures, fake model, local fixture pages

LLM_BASE_URL=http://127.0.0.1:1234/v1 LLM_MODEL=your-model LLM_REASONING_EFFORT=none \
uv run python scripts/eval_search.py --pause-seconds 20 --json /tmp/eval.json
```

The evaluation is live: it uses the real web and records bot walls as `BLOCKED` rather
than working around them. Twelve questions, an expected substring each, and a table of
pass/fail, rounds, pages, blocked pages, input tokens and seconds. Results and what they
taught us are in [docs/plan/notes-search-eval.md](docs/plan/notes-search-eval.md).

## Ground rules the code follows

- Output cap: 1,500 characters per tool result, status word first.
- Numbers, not selectors: lists are numbered and the model replies with a number.
- Code decides what code can decide: ranking, caps, retries and deduplication happen in
  Python; the model only picks numbers, says yes/no, rewrites a query or writes the answer.
- No wall is bypassed. A challenge page is reported as `BLOCKED`.

Start with [docs/plan/00-overview.md](docs/plan/00-overview.md).
