# Tool harness plan: overview

Written 2026-11-14. Covers the four pieces on this side of the split: hidden browser, web search, email search and drafting, computer control. Context management and the reasoning layer (decision tree) belong to the other teammate and are only touched at the seams listed below.

We are **not** using Muse. We are building our own harness that does what it does, tuned for a small local model.

## What we are building

A Python package (`harness/`) of tools that a small local model calls. The model never sees a screenshot or raw HTML. It sees short plain text, picks a number or writes a short string, and code does the rest.

```
user question
   -> reasoning layer (teammate) picks a tool group
   -> local model sees 3 to 5 tools, calls one
   -> harness tool runs (browser / search / email / computer)
   -> short text result (capped) goes back to the model
```

## Branches

| Branch | Doc | Depends on |
|---|---|---|
| `plan/harness-task-breakdown` | all of `docs/plan/` | nothing |
| `feature/browser-core` | [01-browser.md](01-browser.md) | nothing |
| `feature/web-search` | [02-search.md](02-search.md) | browser-core B1 to B7 |
| `feature/email-gmail` | [03-email.md](03-email.md) | browser-core B1 to B8 |
| `feature/computer-control` | [04-computer-control.md](04-computer-control.md) | browser-core B1 only (scaffold) |

Build order: browser-core first. Search, email and computer control can then run in parallel. Merge browser-core into the other three branches once B7 lands. Never commit to `main` directly.

## Rules that make it cheap for a local model

These apply to every tool in every branch. Tests enforce the first three.

1. **Output cap.** Every tool returns plain text of at most 1500 characters (about 400 tokens). Longer content is cut and ends with `[more: call read(page=2)]`.
2. **Status line first.** Line 1 of every result is `OK ...`, `BLOCKED ...`, `LOGIN ...` or `ERR ...`, so the model (or plain code) can branch without reading the rest.
3. **Numbers, not selectors.** Lists are numbered `1.` to `N.`. The model answers with a number. It never writes a CSS selector, a URL it was not shown, or coordinates.
4. **Code decides what code can decide.** Regex, ranking and fixed steps run before the model is asked anything. The model is only asked small questions: pick numbers, yes or no, rewrite a query, write the final answer.
5. **Constrained answers.** Model replies for picks and yes/no are forced with a grammar or JSON schema (llama.cpp GBNF, or the OpenAI-compatible `response_format`), so a small model cannot return broken output.
6. **Stable prompt prefix.** System prompt and tool list never change mid-session, and history is append-only, so the local runtime reuses its cache. Old page text is replaced by a one-line note once used.
7. **Few tools at a time.** Each tool has a one-line description. A tool group is at most 5 tools and at most 400 tokens of description.
8. **No screenshots, no vision.** Text only.

## Seams with the teammate's reasoning layer

Agree on these two before either side builds much.

- **Tool registry.** `harness/registry.py` exposes `TOOLS: dict[str, Tool]` and `GROUPS: dict[str, list[str]]` (`web`, `email`, `computer`). Each `Tool` has `name`, `desc` (one line), `args` (flat, at most 3, all strings or ints) and `run(**args) -> str`. The decision tree picks a group; the model sees only that group.
- **Model call.** `harness/llm.py` exposes `ask(prompt, choices=None, max_tokens=64) -> str`. It talks to any OpenAI-compatible endpoint (`LLM_BASE_URL`, `LLM_MODEL`). Local runtimes (llama.cpp server, `mlx_lm.server`) speak that protocol. Until the local model is wired in, point it at Claude (`claude-haiku-5-5`). Swapping is a config change, not a code change.

## How to run a task (instructions for the worker model)

Each feature doc is a list of tasks with IDs (B1, S3, E2, C4). One task is one session.

1. Read this overview and the one feature doc. Read nothing else unless the task names it.
2. Do only the task you were given. Touch only the files it lists.
3. Run the task's "Done when" command. If it fails, fix it or stop and say what failed. Do not mark it done.
4. Commit on the feature branch with the task ID first: `B4: page text reader with paging`.
5. Add at most 5 lines to `docs/log/<branch>.md`: what was built, anything surprising, anything left open.
6. Tasks marked **SPIKE** end in a short written finding, not code. Tasks marked **HUMAN** need the user at the keyboard (sign-in, permission prompts).

Tooling: Python 3.12+, `uv` for the environment, `pytest` for tests. Tests must pass offline unless the task is marked `live`.

## What we reuse and what we change

| Piece | Open-source work to lean on | What we do differently |
|---|---|---|
| Browser driving | Playwright (bundled Chromium); browser-use for the numbered-element idea | Skip browser-use's agent loop and prompts, which are sized for large cloud models. Keep only the numbered list. |
| Page text | trafilatura (main-text extraction) | Add paging and a hard character cap. |
| Ad blocking | Brave's `adblock` filter engine with EasyList, applied at the network layer | Classic uBlock Origin can no longer be loaded: Chromium removed the old extension format (Manifest V2) in 2026. We add uBlock Origin Lite (Manifest V3) as a second, optional layer on top (task B3b). |
| Search | SearXNG's result-page parsers; local research loops such as GPT Researcher | Rank page chunks with BM25 so the model reads 2 chunks, not a whole page. |
| Email | gmail.js (maps Gmail's page structure) | Page structure instead of fixed window coordinates. Drafts only; no send function exists in the code. |
| Computer control | Hermes Agent (MIT) and trycua's cua-driver; macOS accessibility API | Same numbered-text pattern as the browser, on the accessibility tree. App allowlist and confirmations. |

Not verified yet, each checked by a SPIKE task in the feature doc: how Hermes wires computer use (reported to call cua-driver over MCP, C1); whether Google still accepts a first sign-in in a bundled Chromium profile (B8, E1; fallback is Outlook web); whether uBlock Origin Lite loads in headless Chromium (B3b); and how often plain Playwright hits bot walls compared with the `patchright` fork (B9).

## Name ideas

"Muse" is someone else's product, so the project needs its own name. `harness` is the placeholder package name.

- **Hearth**: it lives at home, on your own machine. First choice.
- **Lantern**: small, local, lights up what you ask about.
- **Burrow**: private, digs things up for you.
- **Homebody**: an assistant that never leaves the laptop.
- **Tether**: short leash, guardrails, stays on device.
- **Porchlight**: on when you need it, at your own house.
- **Kiln**: small models, fired locally.

## Sharing work

Every commit on a `feature/*` or `plan/*` branch is pushed to GitHub automatically by a `post-commit` hook in the shared clone (`.git/hooks/post-commit`; push errors go to `.git/autopush.log`). Teammates can `git fetch` and build on any branch at any time. `main` is never pushed to automatically. The hook is local to that clone: on another machine, copy the file or push by hand.
