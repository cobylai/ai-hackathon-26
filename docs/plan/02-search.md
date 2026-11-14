# 02. Web search (`feature/web-search`)

Read [00-overview.md](00-overview.md) first. Needs browser-core tasks B1 to B7 merged in.

## Goal

Answer a question from the web without any search API: search, read titles, open the promising ones, keep short notes, check whether the notes answer the question, rephrase and retry if not.

## Design choices

- **Engine:** Google results page first, read through the hidden browser. If Google returns a consent page or a bot wall, fall back to DuckDuckGo's plain HTML results page. Both are ordinary web pages, not APIs.
- **The model reads little.** Each opened page is split into chunks and ranked against the question with BM25 (`rank-bm25`, pure Python, no model). Only the top 2 chunks go to the model. This is the main saving over "scrape the whole page and feed it back".
- **Hard caps.** At most 3 rounds of queries, at most 3 pages opened per round, at most 10 results listed. The loop always ends.
- **Model questions, all small:** pick result numbers; pull the useful sentence from a chunk; enough or not; rewrite the query; write the final answer.

## Loop

```
query = question (first round: used as is)
repeat up to 3 rounds:
    results = search(query)                      # numbered titles
    picks   = model picks up to 3 numbers
    for each pick:
        page   = open, extract text (BLOCKED -> skip)
        chunks = top 2 by BM25 against the question
        note   = model: one or two sentences that help, or NONE
    if model says notes are ENOUGH: stop
    query = model rewrites the query (told what was missing)
answer = model writes the answer from the notes, citing source numbers
```

## Tools this branch delivers

| Tool | Args | Returns |
|---|---|---|
| `search` | `query` | numbered results: `n. title (domain) snippet` |
| `open_result` | `n` | status line and the best chunks of that page |
| `research` | `question` | final answer with source list (runs the whole loop) |

`research` is what the decision tree normally calls. The other two are for manual use and tests.

## Tasks

### S1. Google results parser
- **Files:** `harness/search/google.py`, `tests/test_google.py`, `tests/pages/google_results.html`
- **Steps:** `parse(html) -> list[Result]` with `title`, `url`, `domain`, `snippet` (cut to 120 characters). Find organic results as links that contain an `h3`. Drop ads, "People also ask" and duplicate domains beyond 2. Save one real results page by hand as the fixture.
- **Done when:** the fixture yields 8 to 10 results, each with a title and an `http` URL.
- **Note:** SearXNG's `searx/engines/google.py` is a good reference for which parts of the page to read.

### S2. DuckDuckGo fallback and engine switch
- **Files:** `harness/search/ddg.py`, `harness/search/engine.py`, `tests/test_ddg.py`, `tests/pages/ddg_results.html`
- **Steps:** same `parse` for `html.duckduckgo.com/html/?q=`. `engine.search(query) -> list[Result]` loads the Google URL through the browser session; if `classify` says `BLOCKED`, or zero results parse, it uses DuckDuckGo. It remembers the fallback for 10 minutes.
- **Done when:** fixture test passes, and a test with a fake blocked Google page shows the fallback being used.

### S3. `search` and `open_result` tools
- **Files:** `harness/search/tools.py`, `harness/registry.py` (add entries), `tests/test_search_tools.py`
- **Steps:** `search` formats results as numbered lines within the 1500-character cap and stores them for the session. `open_result(n)` opens result `n` and returns the status line plus text.
- **Done when:** tests pass against fixtures, including the shared output-cap check.

### S4. Chunk ranking
- **Files:** `harness/search/rank.py`, `tests/test_rank.py`
- **Steps:** `top_chunks(text, question, k=2, size=600) -> list[str]`. Split on paragraphs into chunks of about 600 characters, score with BM25 against the question's words (lowercased, stop words removed), return the best `k` in page order.
- **Done when:** on a long fixture article, the chunk containing the known answer sentence is in the top 2.

### S5. Model helpers
- **Files:** `harness/llm.py`, `harness/search/prompts.py`, `tests/test_prompts.py`
- **Steps:** `llm.ask(prompt, choices=None, max_tokens=64)` posts to `LLM_BASE_URL` (OpenAI-compatible chat endpoint). When `choices` is given, constrain the reply to those strings. Add a `FakeLLM` for tests. In `prompts.py` write four functions, each with a prompt under 120 words plus its data: `pick(question, results) -> list[int]`, `note(question, chunk) -> str | None`, `enough(question, notes) -> bool`, `rewrite(question, query, notes) -> str`.
- **Done when:** tests with `FakeLLM` cover each function, including bad replies (out-of-range numbers, empty string) being handled without a crash.
- **Seam:** `llm.py` is shared with the reasoning layer. Agree on its shape with the teammate before changing it.

### S6. The `research` loop
- **Files:** `harness/search/loop.py`, `harness/search/tools.py` (add `research`), `tests/test_loop.py`
- **Steps:** implement the loop above with the caps. Keep notes as a list of `(source_number, domain, text)`. Skip pages that are `BLOCKED` or `ERR`. Final answer: at most 120 words, then `Sources:` with numbered domains. If nothing was found after 3 rounds, say so plainly.
- **Done when:** with `FakeLLM` and fixture pages, tests show: stops early when enough, rewrites when not, never exceeds the caps, survives a blocked page.

### S7. Page cache
- **Files:** `harness/search/cache.py`, `tests/test_cache.py`
- **Steps:** SQLite file at `~/.harness/cache.db` keyed by URL, storing extracted text and fetch time. Reuse for 24 hours. `open_result` and the loop check it first.
- **Done when:** a second open of the same URL does not hit the browser (assert with a counter).

### S8. Live evaluation (live)
- **Files:** `scripts/eval_search.py`, `tests/eval/questions.jsonl`, `docs/plan/notes-search-eval.md`
- **Steps:** 12 questions with an expected substring each (a weather lookup, a date, a definition, a recent event, a how-to). Run `research` on each. Log pass or fail, rounds, pages opened, total model input characters, seconds.
- **Done when:** the notes file has the table. Target: 9 of 12 pass, median under 20 seconds, median model input under 8000 characters per question.

## Later, not now

- SearXNG as a self-hosted engine if both engines block.
- Site-specific readers (Reddit old layout, Wikipedia summary).
- Embedding-based ranking in place of BM25.
