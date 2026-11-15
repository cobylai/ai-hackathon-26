# Muse interfaces: guide for the partner's agents

Last updated: 2026-11-14, against main `d118285`. Each item below is marked **built**, **planned** or **undecided**. "Planned" means a worker has written a plan that hasn't been built yet, so names can still change. Update this file when you change an interface.

## 1. Ground rules

- **The app:** Muse, a local assistant. The user types (or later speaks) a question. Muse checks what it already knows, uses a built-in Chromium browser if it needs more, and answers.
- **Hackathon rules:**
  - Every LLM call must go to **local Bonsai 2, 4B**.
  - Argmax is the only allowed speech model.
  - The demo runs with **Wi-Fi off**.
  - The context limit is **32k tokens**.
  - Due: **noon Sun 2026-11-15**.
- **Shape:** one codebase on one Mac. There are no services and no localhost APIs between the two halves; Coby's code imports the browser code and calls it directly.
- **Language:** Python 3.12. The venv is at `samples/bonsai-models/mlx/.venv` in the main checkout. Don't use the system `python3`, which is Anaconda 3.9.
- **Git:**
  - One branch per feature, named for what it does.
  - Don't commit to main directly.
  - Don't commit real email, personal data or keys. Keys live in Bitwarden.
- **Who owns what:**

| Area | Owner | Folder |
|---|---|---|
| Browser (search, scrape, uBlock Origin), email access | Partner | `browser/` (**undecided**, proposed) |
| Bonsai client | Coby | `llm/` |
| Sufficiency check | Coby | `sufficiency/` |
| Context store | Coby | `bank/` |
| Reasoning layer, UI, voice input | Coby | not started |
| Computer control | **undecided** | |

## 2. Browser contract (what the partner provides) — **planned, needs Coby and partner to agree**

Coby's side calls the browser through exactly two functions. Both are passed in as arguments, never imported by name, so this contract can change in one adapter (`sufficiency/gather.py`).

```python
def search(query: str) -> list[dict]:
    """Run a web search. Return hits in ranked order, at least the first 10."""
    # each hit: {"title": str, "url": str, "snippet": str}

def open(url: str) -> dict:
    """Load the page in the isolated Chromium and scrape its visible text."""
    # returns {"title": str, "text": str}
```

- `text` is plain visible text with no HTML, and should include the whole page. Coby's side splits long pages itself, so don't truncate.
- On failure (timeout, blocked page), either raise an exception or return empty `text`. The caller skips that URL and moves on.
- **Email reading is `open()` on a mail page** after the browser is logged in. No connector is needed. How the partner logs in and finds messages is up to them.
- The browser is isolated from the user's own Chrome. It never shares cookies or profiles with it.

**Offline plan ("sync online, answer offline"):** while Wi-Fi is on, the browser scrapes email (and later Canvas) and hands each item's text to the context store (§5). With Wi-Fi off, Muse answers only from the store.

## 3. Bonsai client — **built** (`llm/`, on main)

All model calls go through it. No other provider, and nothing outside localhost.

Start the server once (stop it with Ctrl-C):

```bash
scripts/serve_bonsai.sh 4B
```

It serves `http://localhost:8080/v1`. Only one server can run at a time on port 8080, so check whether one is already running before starting another.

```python
from llm.client import complete, complete_json, chat, ServerDown, BonsaiError, JSONReplyError
from llm.tokens import count, split_to_budget, trim_to_budget, BudgetError

complete(prompt, system=None, max_tokens=None, json_schema_hint=None, thinking=False) -> str
complete_json(prompt, system=None, max_tokens=None, json_schema_hint=None, thinking=False) -> dict | list
    # retries once on invalid JSON, then raises JSONReplyError
chat(messages, max_tokens=None, thinking=False) -> Reply
    # Reply has .text, .prompt_tokens, .completion_tokens, .seconds, .finish_reason, .reasoning

count(text) -> int                               # offline, uses the model's tokenizer.json
split_to_budget(text, budget_tokens) -> list[str]  # breaks on paragraphs, then lines, then sentences
trim_to_budget(text, budget_tokens) -> str
```

- **Budget:** prompt plus `max_tokens` over 32,768 raises `BudgetError`. The client never truncates silently; callers split first.
- **Errors:** `ServerDown` (its message prints the start command), `BudgetError`, `JSONReplyError`, and `BonsaiError` for anything else, including the wrong model size being loaded.
- **Settings** (in `llm/config.py`, set by environment variable):
  - `BONSAI_SIZE`, default `4B`
  - `BONSAI_BASE_URL`, default `http://localhost:8080/v1`
  - `BONSAI_TIMEOUT_S`, default `300`
  - `BONSAI_MODELS_DIR`
- **Speed on 4B:** about 1.2 s per extraction call and about 0.4 s per short judgement.
- More detail: `docs/bonsai-client.md`.

If the browser side needs a model call (for example, choosing which link to click), use this client. Never call a cloud model from the app.

## 4. Sufficiency check — **planned** (`sufficiency/`, branch `sufficiency-check`)

Decides whether a page answers the question, and if not, searches again with a reworded query. This is the main consumer of the browser contract.

```python
judge(question, page_text, url=None, today=None) -> Verdict
    # enough, answer, evidence (a quote checked to appear in the page), reason, url, chunk, chunks, seconds
rephrase(question, tried_queries, today=None) -> str | None
gather(question, search_fn, open_fn, max_results=10, max_rephrases=2, today=None) -> GatherResult
    # found, answer, evidence, source (title/url/snippet), queries, opened, verdicts, message
```

`gather` searches, reads titles and snippets, opens hits in order, and stops at the first page that's enough. If none is, it rephrases (at most 2 times, so at most 30 pages) and then gives up with a "not found" message. Full plan: `docs/plans/sufficiency-check.md` on that branch.

## 5. Context store — **planned** (`bank/`, branch `context-store`)

A store of everything Muse has read, kept as markdown files. This is what the Wi-Fi-off demo answers from.

```python
ingest(text, source, kind)   # kind = "email" | "page"; Bonsai pulls out the facts, then one .md entry is written
search(query, limit)         # keyword search, offline, no model call
by_person(name)
due(start_date, end_date)    # entries with a deadline in the range
```

- **Partner's side:** after an email or page is scraped, call `ingest(text, source=url, kind="email")`.
- **Data location:** `data/bank/` by default. It's gitignored because it will hold real email.
- **Status:** the exact entry format and function details will be in `docs/plans/context-store.md` once that plan is written.

## 6. Voice input — **tested** (Argmax, branch `argmax-runtime-test`); handoff to Python **planned**

Argmax runs only from Swift, so voice is a small separate Swift program. It turns speech into text, and the text goes into the same entry point as a typed question. Details are in `docs/argmax.md`.

- **What runs today:** the sample CLI, `samples/argmax-pro-sdk/native/.build/release/meeting-scribe file <wav> --no-speakers`, with `ARGMAX_API_KEY` set. It transcribes a 6.7 s clip correctly.
  - Warm process time: 4.5 s, most of it loading the model.
  - Transcription alone: about 1.4 s.
  - Model: Whisper large-v3 turbo, 615 MB, in `~/Documents/huggingface/models/argmaxinc/whisperkit-coreml/`.
- **Offline:** each launch contacts `api.argmaxinc.com`, but a failed check did not stop the run. A real Wi-Fi-off run is still to be done by Coby.
- **Handoff to Python (proposed, not built):** Python starts one long-running Swift process with `subprocess.Popen` and reads its stdout. The Swift side writes one JSON line per finished utterance, for example `{"text": "remind me to buy oat milk", "start": 12.3, "end": 14.1}`, and flushes after each line. Python passes `text` into the same entry point as a typed question. One long-running process avoids paying the ~4.5 s model load per question.
- **Not decided:** whether voice is push-to-talk or always on.

## 7. Not decided yet

- Coby and partner to agree:
  - the browser folder name
  - the final `search`/`open` shapes
  - whether `open` takes a "wait for selector" option for mail pages
  - **a way to list messages.** `open(url)` on the inbox returns the inbox page's text, not the individual emails, so the sync step can't walk the mailbox with `search`/`open` alone. The browser side needs something like `recent_messages(limit) -> list[{"source_id", "text"}]` (each message as plain text with a stable id), and the same later for Canvas.
- Who builds computer control.
- The UI (built last), and the main entry point that typed and spoken questions go into.
