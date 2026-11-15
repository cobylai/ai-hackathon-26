# Status for the teammate (and their AI): where the harness stands

Written 2026-11-14. Read this first, then `docs/plan/00-overview.md` for the rules. This file is the hand-off; the overview is the design.

## One-paragraph summary

We built a Python package, `harness`, of short text tools that a small local model can call: a hidden browser, web search, Gmail search/drafting, and macOS app control. Four feature branches exist on GitHub, each branched from `plan/harness-task-breakdown`, each fully tested. What is not done is **integration**: the branches are not merged into one, the tool registry differs per branch, and nothing is yet wired to the reasoning layer (decision tree) or to the real local model.

## Branches (all pushed; every commit auto-pushes)

| Branch | Contains | State |
|---|---|---|
| `feature/browser-core` | B1-B10: hidden Chromium, ad/request blocking, text paging, numbered elements, page-state detection (OK/BLOCKED/LOGIN/ERR), sign-in command, notes on bot walls, timing, uBlock Origin Lite | done |
| `feature/web-search` | browser-core plus S1-S8: Google/DuckDuckGo parsers, `search`, `open_result`, `research` loop, BM25 chunk ranking, page cache, live eval | done; live eval 12/12 (Run 3) |
| `feature/computer-control` | browser-core plus C1-C7: pyobjc accessibility layer, policy and action log, numbered controls, click/type | done; live check 5/5 |
| `feature/email-gmail` | browser-core plus E1-E9: selector map, query builder, `email_search`, `email_read`, `email_asks`, drafts only (no send path exists) | built; live re-verification in progress |
| `plan/harness-task-breakdown` | all plan docs, this file | current |

Each feature branch already contains browser-core. They do not contain each other.

## Tools by group

- `web` (browser-core): `goto`, `read`, `elements`, `click`, `type`, `back`
- `search`: `search`, `open_result`, `research`
- `email`: `email_search`, `email_read`, `email_asks`, `email_draft`, `email_reply_draft`
- `computer`: `ui`, `ui_click`, `ui_type`, `app_open`, `file_find`, `file_open` (see `harness/computer/tools.py`)

Every tool returns plain text of at most 1500 characters whose first line starts `OK`, `BLOCKED`, `LOGIN` or `ERR`.

## The integration problem you will hit first

`harness/registry.py` exists on every branch with a different `GROUPS` dict (`search`, `email` and `computer` are each filled on only one branch). Merging all four will conflict there. Resolution: keep one `TOOLS` dict containing every tool and one `GROUPS` dict with all four groups. Nothing else should conflict.

## Seams with the reasoning layer

- **Registry:** `harness/registry.py` exposes `TOOLS: dict[str, Tool]` and `GROUPS: dict[str, list[str]]`. A `Tool` has `name`, `desc` (one line), `args` (flat, at most 3, str or int) and `run(**args) -> str`. The decision tree picks a group; the model sees only that group's tools.
- **Model call:** `harness/llm.py` exposes `ask(prompt, choices=None, max_tokens=64) -> str` against any OpenAI-compatible endpoint (`LLM_BASE_URL`, `LLM_MODEL`; `LLM_REASONING_EFFORT=none` for reasoning models that otherwise return empty content). `llm.last_usage` has the server's real token counts.
- The search `research` loop already calls `llm.ask` with constrained choices for picks and yes/no.

## Results so far

| Area | Result | Where |
|---|---|---|
| Browser speed | warm page 0.03-0.16 s; cold start about 1.4 s; about 635 MB across processes | `docs/plan/notes-bench.md` |
| Bot walls | plain Playwright is enough; `patchright` removed no real wall | `docs/plan/notes-botwalls.md` |
| uBlock Origin Lite | loads headless; opt-in only; cosmetic filtering limited | `docs/plan/notes-ubol.md` |
| Web search | Run 1: 4/12 (search engines blocked the browser). After five fixes and 20 s pacing, Run 3: 12/12, median 19 s, median 2,842 prompt tokens. Input still about 24% over the 8,000-character target. No search-level wall appeared in Run 3, so the wall handling was only tested on fixtures. | `docs/plan/notes-search-eval.md` |
| Computer control | 5/5 TextEdit jobs, about 1.6 s total, 1,901 characters to the model, zero confirmations | `docs/plan/notes-computer-eval.md` |
| Email | search+read about 7 s, 1,809 characters total for one flow; `email_asks` about 28 s (being optimized) | `docs/plan/notes-email-eval.md` |

Tests: roughly 110-120 per branch; they run offline except the live scripts under `scripts/`.

## Things that went wrong, so you do not repeat them

1. **Google sign-in:** it must be done once in a plain visible window (`uv run python -m harness login https://mail.google.com`), not in the automated browser. Both the sign-in window and the hidden session use Chromium's mock keychain, so cookies match and macOS never asks for the real keychain. Never choose "Reset To Defaults" on a keychain prompt.
2. **Gmail draft safety:** the first live email run reused a leftover existing draft (it had Bcc recipients) instead of starting a blank one. `harness/email/draft.py` now refuses a restored draft and checks that To is exactly the requested address with no Cc or Bcc. Live tests must address drafts only to the test account and must never send. The code has no send function; keep it that way.
3. **Search engines:** Google and DuckDuckGo challenged rapid automated queries. The DuckDuckGo challenge page now classifies as `BLOCKED`. We pace requests and do not try to get past walls.
4. **Page state:** Google sign-in pages are classified `LOGIN`; Cloudflare "Just a moment" interstitials are `BLOCKED`.
5. **Shared browser profile:** only one process can use `~/.harness/profile` at a time. Do not run two live checks together.

## Not done

- Merging the four branches into one (suggested: an `integration` branch).
- Wiring the registry to the decision tree and to the real local model (Bonsai 4B and the search agent's `qwen/qwen3.5-9b` through LM Studio are the candidates; the harness has only been exercised against the latter).
- Email: five-request evaluation table, `email_asks` speed, live re-verification of the draft safety checks (in progress).
- Search: shrink model input (consider a token target, not characters).
- Computer control: the live checks used TextEdit only; other apps and the confirmation prompts for risky actions were tested with mocks.
- Final project name (the package is still called `harness`; candidates are in the overview).
- `tests/test_extensions.py` has one test that fails intermittently in a full-suite run and passes alone.

## Rules that must survive integration

Drafts only (no send path). App allowlist and confirmation for risky computer actions. Output cap of 1500 characters with a status line first. Numbers, not selectors. No screenshots. Never try to get past bot walls or CAPTCHAs.

## How to run

```
git clone https://github.com/cobylai/ai-hackathon-26 && cd ai-hackathon-26
git checkout feature/browser-core        # or any feature branch
uv sync && uv run pytest -q
uv run python -m harness goto https://example.com
```
