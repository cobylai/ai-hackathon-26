# Muse interfaces: guide for the partner's agents

Last updated: 2026-11-14 late, when everything was landed on `main`. Each item below is marked **built**, **planned** or **undecided**. Everything is now built and merged on `main`. The old feature branches (sufficiency-check, context-store, reasoning-layer, voice-input, integration) are history. Update this file when you change an interface. To set up and test, see `docs/PARTNER-TESTING.md`; for what changed in `harness/`, see `docs/PARTNER-UPDATE.md`.

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
| Reasoning layer (decision tree) | Coby | `reason/` |
| UI, voice input | Coby | not started |

## 2. Browser contract — **built** (adapters on Coby's side, merged on `main`)

Built as described below, with two differences from the original sketch:
- **Search:** `sufficiency/websearch.py` is the `search_fn`. It tries `harness.search.engine.search` and, when that comes back BLOCKED/empty, reads Bing in the same hidden browser.
- **Email sync:** `scripts/sync_email.py` (uses `read.open_thread` + `read.read_messages`). `harness/llm.py` calls `llm.client.chat`.

The web route is being reworked now (worker 10, size-limit fix).

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

## 4. Sufficiency check — **built** (`sufficiency/`, on `main`)

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

## 5. Context store — **built** (`bank/`, on `main`)

A store of everything Muse has read, kept as markdown files. This is what the Wi-Fi-off demo answers from. Full details are in `docs/context-store.md`.

```python
from bank import ingest, search, by_person, due, rebuild_index

ingest(text, source, kind, *, sender_name=None, sender_address=None, sent_date=None, subject=None)
    # kind = "email" | "page". Needs the Bonsai server. The keywords win over anything in the text.
    # With none of them and no header lines: model sender + first "Name <addr>" + first dated line;
    # no date found -> ingest date, sent_date_guessed=True.
    # -> {"status": "added" | "duplicate", "path": str, "entry": dict, "raw": [model replies]}
search(query, limit=10)          # -> [entry]; keyword score, subject/sender hits count double, ties newest first
by_person(name)                  # -> [entry]; part-word match on sender name or address, newest first
due(start_date, end_date)        # -> [{"date", "time", "phrase", "entry"}]; inclusive, sorted by date then time
rebuild_index()                  # -> path of data/bank/index.md (every ingest also rebuilds it)
```

- **Readers are offline:** `search`, `by_person` and `due` never call the model or the network, and never import `llm`.
- **Entry:** one file at `data/bank/{course,person,other}/<sent_date>-<subject-slug>-<id12>.md`.
  - The front matter, as JSON values, is `id`, `kind`, `folder`, `source`, `sender_name`, `sender_address`, `sent_date`, `subject`, `ask`, `deadlines`, `course`, `topic`, `sent_date_guessed` and `ingested_at`.
  - `deadlines` is a list of `[{"phrase", "date", "time"}]`. `date` is `YYYY-MM-DD` or null, and `time` is `HH:MM` or null.
  - The body is a one or two sentence summary.
  - An `entry` dict holds those fields plus `body` and `path`.
- **Index:** `data/bank/index.md` has one line per entry: `date | from | folder | summary | deadlines | file`. It is capped at 20k tokens so it can be handed to Bonsai whole.
- **Duplicates:** an item with the same `source` is skipped, with the content hash as a fallback. Pass a stable id such as the `thread_id` as `source`.
- **Partner's side:** the sync loop in §2 calls `ingest(body, source=thread_id, kind="email", sender_name=..., sender_address=..., sent_date=..., subject=...)`. For a page, it calls `ingest(text, source=url, kind="page")`.
- **Data location:** `data/bank/` by default, or `$MUSE_BANK_DIR` if that is set. It is gitignored (`data/`) because it will hold real email.
- **Preload:** `python -m bank.load <folder> --kind email|page`.

## 6. Reasoning layer — **built** (`reason/`, on `main`)

One entry point for typed and spoken questions. Code picks the route, never the model. Full details are in `docs/reasoning-layer.md`.

```python
from reason import answer
answer(question, today=None) -> Answer
    # Answer: text (ends with "Source: sender, Nov 12" or the url), route, sources, seconds
    # route: "due" | "calendar" | "person" | "bank" | "web" | "offline" | "not_found"
```

- **Due:** the question says due/deadline. Code picks the date range, calls `bank.due` and writes the list. No model call.
- **Calendar:** checked after due. Triggers on "calendar", "schedule", "my/next meeting/event/appointment", "what do I have", "am I free". `applecal.events(start, end)` reads one Calendar.app calendar with osascript (`MUSE_CALENDAR`, default "Muse demo"), over the due route's date ranges or the next upcoming event. Code writes the list. No model call, no network. Details are in `docs/calendar.md`.
- **Person:** a question word is a sender's name.
  - "What did <name> ask / want / need": code lists that sender's newest 8 entries as date, subject and ask (or "no ask" and the summary). No model call.
  - Other person questions: `bank.by_person`, then Bonsai answers from those entries only.
  - A "what did <name> ..." question with no matching sender answers "I have nothing from <name>." and stops.
- **Due rows** carry each entry's summary, so amounts come along. On Sat/Sun, "this week" means today through Sunday.
- **Else:** `bank.search` then `sufficiency.judge`.
  - If that isn't enough and the Mac is online, `gather` runs with `sufficiency.websearch.search` (partner search, then Bing) and `tools.open_page`, and the answer is filed with `bank.ingest(kind="page", source=url)`.
  - If offline, the answer says plainly that it isn't saved and the Mac is offline.
- **Chat loop:** `python -m reason [--today YYYY-MM-DD]`. An empty line records voice; the next Enter stops it.
- **Chat window:** `python -m reason.web [--today] [--port 8765]` serves one local page from the standard library, with no remote assets. It has a type box, hold-to-talk, a source line under each answer, and an "online/offline · N items in bank" label. Clicking the label lists the bank (`GET /bank`).
- **Bank to use:** set `MUSE_BANK_DIR`. The demo uses `~/muse-demo-bank` (sample mail, see `docs/integration.md`).
- **Playbooks** (`playbooks/`): one markdown file per route (`due`, `calendar`, `person`, `bank`, `web`) plus `RULES.md` for every route. Code reads each route's trigger patterns, reply wording, not-found lines and prompt text from its file (`reason/playbook.py`: `say(book, key, **values)`, `prompt(book, key)`, `trigger(book, key)`), read once per start. The order of steps stays in code; `STEPS` in `reason/answer.py` must match each file's numbered steps (a test checks it). **A new route adds its own `playbooks/<route>.md`** in the same sections (listed in `RULES.md`), with examples, and its count in `STEPS`.
- **Checker:** `MUSE_BANK_DIR=~/muse-demo-bank uv run python -m reason.playbook_check [--today 2026-11-15] [--only due]` runs every playbook's examples on a temporary copy of the bank, network blocked. Keep a playbook or prompt change only if it passes and brief M's score (`scripts/make_test_mail.py check`) doesn't drop.

## 7. Voice input — **built** (`voice/`, on `main`)

Argmax runs only from Swift, so voice is a small Swift program, `voice/swift/` → `argmax-voice`. It stays running, and Python drives it through `voice/listen.py`. Push to talk: it records only between start and stop. Details are in `docs/voice-input.md`; the offline findings are in `docs/argmax.md`.

- **Python call:** `from voice.listen import Voice; voice = Voice()` once at startup (≈1.5 s warm). Then `question = voice.listen(wait_for_stop=input)` returns the text. `wait_for_stop` is any blocking function; recording stops when it returns.
- **Errors:** `VoiceError` is raised for a microphone denial, a license or model failure, the process exiting, or a timeout. It never hangs silently.
- **Needs:** `ARGMAX_API_KEY` in the environment (from the vault, loaded before Wi-Fi off), and the built binary (`swift build -c release` in `voice/swift`).
- **Speed:** stop to text is about 1.1–1.25 s for a spoken question. It works with all network denied.
- **Protocol** (if you drive the binary directly): stdin `start`/`stop`/`file <wav>`/`quit`. stdout JSON lines: `ready`, `recording`, `text` (`{"event":"text","text":"...","seconds":2.4}`), `error`.
- **Wired in:** the chat loop and the window use it, via `reason/speech.py` (`MUSE_VOICE_BIN` overrides the binary path). If voice can't start, typing still works.
- **Names:** Whisper spells names its own way ("Coby" came back as "Kobe"), so spoken person questions need easy, single-spelling names.

## 8. Not decided yet

- The app's name: "Muse" vs "Hearth" (Coby's call; no code depends on it; the partner prefers not "Muse").
- Canvas sync: not started. It would follow the same pattern as email.
- Not used by the app: the partner's computer-control, `email_asks` and draft tools, and `research()`.
