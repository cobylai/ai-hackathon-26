# Muse interfaces: guide for the partner's agents

Last updated: 2026-11-14, after the partner code review. Each item below is marked **built**, **planned** or **undecided**. "Planned" means a worker has written a plan that hasn't been built yet, so names can still change. Update this file when you change an interface.

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
| Browser (hidden Chromium, ad-blocking, login), web search, Gmail reading, computer control | Partner | `harness/` |
| Bonsai client | Coby | `llm/` |
| Sufficiency check (the search loop) | Coby | `sufficiency/` |
| Context store, plus the email sync loop | Coby | `bank/` |
| Reasoning layer (decision tree), UI, voice input | Coby | not started |

## 2. Browser contract — **agreed shape, adapters not built yet** (thinker ruling 2026-11-14; Coby to confirm with partner)

The partner's code already exists in `harness/` (Python 3.12, uv, Playwright). Coby's side uses it as it is, through small adapters on Coby's side. The partner doesn't need to change his return types.

**Web search and pages:** the partner provides these, and Coby's adapter lives in `sufficiency/gather.py`:

```python
harness.engine.search(q) -> [Result(title, url, domain, snippet)]    # live Google, DDG fallback
harness.search.tools.open_page(url) -> (status, full_text)           # status "OK" | "BLOCKED" | "LOGIN" | "ERR"; 24 h cache
```

The adapter turns those into the shapes `gather()` takes:
- `search_fn(q)` returns `[{"title", "url", "snippet"}]`.
- `open_fn(url)` returns `{"title": "", "text": full_text}` when the status is OK, and `{"title": "", "text": ""}` otherwise.

**The search loop is Coby's `gather()`, not `harness` `research()`.** `gather()` has the quote check and has been tested on Bonsai 4B. `research()` stays unused for the core tasks.

**Email:** the partner provides these, and Coby's sync loop lives in `bank/`:

```python
email_search(sender=None, text=None, days=N) -> numbered rows, each with a thread_id
read_messages(...) -> [("Name <addr>", date, body), ...]
```

Sync is a short loop on Coby's side:
1. `email_search(days=N)`
2. Read each row.
3. `bank.ingest(body, source=thread_id, kind="email", sender_name=..., sender_address=..., sent_date=..., subject=...)`. The name and address are split from `"Name <addr>"`.

The partner doesn't need to build a separate `recent_messages()` call.

**Who picks the tool:** Coby's decision tree calls the partner's tools directly for the core tasks, as agreed in the team plan. The partner's tool registry (`TOOLS`/`GROUPS`) stays the list of available tools; the model doesn't choose from it for the core tasks.

**Model calls in `harness/`:** `harness/llm.py`'s `ask()` must call `llm.client.complete` with the same signature. That gives it the 32k guard and real errors instead of `""`. Nothing in `harness/` may reach a model that isn't on localhost, so **no Claude Haiku stand-in in the shipped app.**

**Offline plan ("sync online, answer offline"):** while Wi-Fi is on, the sync loop reads email into the context store (§5). With Wi-Fi off, search and `open_page` return BLOCKED/ERR, and Muse answers only from the store.

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

## 4. Sufficiency check — **built** (`sufficiency/`, branch `sufficiency-check`)

Decides whether a page answers the question, and if not, searches again with a reworded query. This is the main consumer of the browser contract (§2). Details and numbers are in `docs/sufficiency-check.md` on that branch.

```python
from sufficiency import judge, rephrase, gather

judge(question: str, page_text: str, url: str | None = None, today: date | str | None = None) -> Verdict
    # Verdict: enough: bool, answer: str | None, evidence: str | None (quote checked to be in the page),
    #          reason: "answered" | "no_answer" | "quote_not_in_page" | "bad_json"
    #                  | "not_this_question" (only with the optional check call, off by default),
    #          url: str | None, chunk: int, chunks: int, seconds: float
rephrase(question: str, tried_queries: list[str], today=None) -> str | None   # None after two repeats
gather(question: str, search_fn, open_fn, max_results: int = 10, max_rephrases: int = 2,
       today=None, max_seconds: float | None = 60) -> GatherResult
    # GatherResult: found: bool, answer: str | None, evidence: str | None,
    #               source: Hit(title, url, snippet) | None, queries: list[str],
    #               opened: list[str] (urls), verdicts: list[Verdict], message: str
```

- **Judge.** The model answers from the page and quotes the lines it used. Code sets `enough` only if the quote is found in the page, ignoring case, whitespace, quote and dash styles, and punctuation at the ends of the quote.
- **Long pages.** Pages over 6,000 tokens are judged chunk by chunk.
- **Sampling.** Judging runs at temperature 0.2, using the new `sampling=` argument in `llm/client.py`.
- **Gather.** It searches with the question itself, keeps the first 10 hits, and moves hits whose title or snippet shares no word with the question to the end. It opens each URL once and stops at the first page that's enough. If none is, it rephrases at most 2 times, so at most 3 searches and 30 pages. Then it returns `found=False` with every query and URL it tried.
- **Failed pages.** If `open_fn` raises or returns empty `text`, that URL is skipped.
- **Time limit.** `max_seconds` (default 60, `None` for no limit) stops the loop and returns the normal not-found result, with a message starting "Ran out of time". A judge call already running is not cut off.
- **Known weak spot.** A page that only says where the answer is ("posted on our Instagram") can be accepted as the answer.

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

## 6. Voice input — **planned** (Argmax, branch `argmax-runtime-test`)

Argmax runs only from Swift, so voice is a small separate Swift program. It turns speech into text, and the text goes into the same entry point as a typed question. How the Swift program hands text to Python is **undecided**; it will be in `docs/argmax.md` once the runtime test reports.

## 7. Not decided yet

- **Integration, planned for tonight:** once sufficiency-check and context-store land, one worker merges main and the partner's branches into an integration branch. The partner flags a `registry.py` conflict. Done means:
  - a typed question runs `gather()` against his real browser on Bonsai 4B
  - one real email goes through `read_messages` into the bank
- The app's name: "Muse" vs "Hearth" (Coby's call; no code depends on it).
- The UI (built last), and the main entry point that typed and spoken questions go into.
- Canvas sync, later, on the same pattern as email.
