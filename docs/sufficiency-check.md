# Sufficiency check

`sufficiency/` decides whether a page answers a question, and searches again with a reworded query when it doesn't. Every model call goes to local Bonsai 2 4B through `llm/client.py`. The plan is in `docs/plans/sufficiency-check.md`.

## Use

```python
from sufficiency import judge, rephrase, gather

v = judge("Is the gym open on Thanksgiving?", page_text, url=url, today=date.today())
# Verdict: enough, answer, evidence, reason, url, chunk, chunks, seconds

q = rephrase(question, tried_queries)            # str, or None after two repeats

r = gather(question, search_fn, open_fn, max_results=10, max_rephrases=2, max_seconds=60)
# GatherResult: found, answer, evidence, source (Hit: title/url/snippet),
#               queries, opened, verdicts, message
```

- `search_fn(query)` returns `[{"title", "url", "snippet"}, ...]`. `open_fn(url)` returns `{"title", "text"}`. A plain string is also accepted from `open_fn`. These shapes are assumed only in `_hits()` and `_page()` in `sufficiency/gather.py`.
- If `open_fn` raises or returns empty text, that URL is skipped.
- `reason` is one of `answered`, `no_answer`, `quote_not_in_page`, `bad_json`, and `not_this_question` (only when `CHECK_ANSWER` is on).
- `max_seconds` (default 60, `None` for no limit) is checked before each search, each page and each rephrase. Once the time has passed, gather returns the normal not-found result, and its message starts "Ran out of time (60s)." A judge call that has already started is not cut off, so a slow page can run past the limit by one call.

## How it judges

1. The model is asked to answer from the page and copy the exact line it used, as JSON `{"answer", "quote"}`. It is never asked for an enough / not enough label.
2. Code sets `enough=True` only if both fields are present and the quote is found in the page. The check ignores case, runs of whitespace, curly versus straight quotes, dash types, and punctuation at the ends of the quote. A quote joined with "..." or a line break is split into pieces. Every piece of 8 or more characters must match, and at least one such piece must exist.
3. Pages over `PAGE_BUDGET = 6000` tokens are split with `split_to_budget` and judged chunk by chunk, stopping at the first chunk that answers.
4. Judging and rephrasing run at temperature 0.2. The other preset values are unchanged. This uses the new `sampling=` argument on `chat`, `complete` and `complete_json` in `llm/client.py`, which is the only change to `llm/`.

### Final judge prompt (the shipped `original` variant)

System: `You answer questions using only the web page you are given. You never use outside knowledge and never guess.`

User:
```
Today is {today}.

QUESTION: {question}

PAGE ({url}):
{page}

If the page answers the question, even in different words, give the answer and copy the exact line from the page that supports it. If the page does not answer it, set answer and quote to null.

Reply with only a JSON object, no prose and no code fence, matching this shape:
{"answer": "short answer, or null", "quote": "exact text copied from the page, or null"}
```
The last paragraph is added by `complete_json`. Settings: `max_tokens=300`, thinking off. The rephrase prompt is in `sufficiency/prompts.py`.

## Check on 4B

Run `python -m sufficiency.eval.run_check --runs 3 --variant <v>` with the venv Python, against a 4B server. "Today" is Friday 13 November 2026, the same date as the original check.

**Fixtures**
- **Originals:** p01–p08, read in place from `llm/eval/fixtures/` and unchanged.
- **New:** s01–s08, written once and not tuned against.
- **Added after review:** s09 needs two items in the answer. s10 is a pointer page ("for grading weights … consult the syllabus"), worded unlike s03 and written before any results were seen.
- **Pointer fixtures:** p07, s03, s04 and s10.

**Scoring**
- A fixture marked "enough" needs the right label and the expected evidence text.
- s09 is scored on the answer naming both items.

**Bar (thinker 0):** 8/8 on the originals, every pointer fixture right, and no "enough" fixture lost, on each of 3 runs.

### Results: 4 variants, 3 runs each, all identical across runs

| variant (`--variant`) | originals | s01–s08 | s09 | s10 | pointers | enough fixtures | misses | median s / judge* |
|---|---|---|---|---|---|---|---|---|
| **original** (shipped default) | **8/8** | 7/8 | pass | pass | 3/4 | **9/9** | s03 | 1.33–1.61 |
| everyline | 7/8 | **8/8** | pass | pass | 3/4 | **9/9** | p07 | 1.25–1.97 |
| rule (everyline + pointer sentence) | 7/8 | 7/8 | pass | pass | 2/4 | 9/9 | p07, s03 | 1.23–2.01 |
| check (everyline + A/B check call) | 5/8 | 8/8 | pass | pass | **4/4** | 6/9 | p01, p02, p06 | 2.23–2.42 |

\* These runs shared the server with worker 5's evals, so their times are inflated. On an idle server, the original prompt took a median of **0.83 s** per judge call over 3 runs (8/8 and 7/8; commit bf5630d).

**No variant meets the bar.** I am shipping `original` (`EVERY_LINE = USE_POINTER_RULE = CHECK_ANSWER = False` in `sufficiency/prompts.py`). It loses no real answers, keeps all 8 originals, and handles multi-item answers: s09 and p02 list every item and quote every line. Its one miss is s03.

- **The pointer miss.** In s03 ("Meeting times are posted on our Instagram") and p07 ("Office hours are posted weekly on the course calendar"), the model gives the pointer as its answer and quotes it. The quote really is in the page, so the quote check can't catch it. Which of the two fails depends on the wording: the original prompt misses s03, and the every-line wording misses p07. s04 and s10 pass in every variant.
- **The pointer sentence** (the thinker's wording, my one allowed attempt) didn't help: both p07 and s03 still failed. An earlier attempt with my own wording got the same result (`results/rejected_multiline_pointer_prompt/`). I stopped rewording after that.
- **The check call** is a second short model call that sees only the question, the answer and the quote.
  - As a yes/no question it backfired: the model answered the question itself. "Is the gym open?" plus "CLOSED" got the reply "no". It rejected 6 of 9 real answers (`results/rejected_check_yesno/`).
  - Asked as A/B ("gives the information" vs "only says where to find it, or is about something else"), it gets every pointer right. But it rejects p01, p02 and p06 on every run. Those are the three that need date reasoning: "tomorrow" means Saturday, "this week" means Nov 9–13, and Thanksgiving falls on Thu Nov 26. The checker doesn't connect the date words. It also roughly doubles the time per judge call.
- **s05, the long page.** It is 7,510 tokens, so it splits into 2 chunks; the plan estimated about 9k. The second chunk answers, taking about 11–14 s in total.
- **Show `evidence` with `answer`.** For p06 the `answer` is just "NO", while its evidence is the CLOSED line.

All result files are in `sufficiency/eval/results/`: `4B_<variant>_run{1,2,3}.json`, plus the `rejected_*` folders from earlier tries.

### Live gather and rephrase

`python -m sufficiency.eval.live_gather` uses stub search and open functions over the saved fixture pages, with live 4B and the shipped prompt. Output is in `results/4B_live_gather.txt`.
- **Found on the first search:** the gym hours page.
- **Found after one rephrase:** the dining hall page.
- **Gave up:** after 3 searches and 4 pages, with every query in the message.
- **Rephrase on its own:** it returned a new query that wasn't a repeat.

## Tests (no server)

`python -m unittest discover -s sufficiency/tests -t .` runs 36 tests with a stubbed client. They cover:
- the quote check, a list of quotes, and the case where every "..." piece is under 8 characters, which must fail
- judge verdicts, the date passed in, the sampling setting, the check call and the prompt switches
- chunking and stopping at the first chunk that answers
- rephrase rejecting repeats
- the gather loop: running out of `max_seconds`, found on the first search, found after a rephrase, giving up, never reopening a URL, skipping failed opens, `max_results` and title ordering, and the adapter shapes
- the `sampling=` merge in `llm/client.py`

## Known limits

- **Pointer pages.** A page that only says where the answer is ("Meeting times are posted on our Instagram") can be accepted as the answer. Its quote is real, so the quote check passes. This is s03 with the shipped prompt. Thinker 0 ruled no further prompt work. The A/B check call (`CHECK_ANSWER = True`) catches these pointers but rejects answers that need date reasoning, so it is off.
- **Short answers.** The `answer` text can be terse ("NO"). Show `evidence` with it.

## Not run

- Real browser functions. No `search` or `open` exist yet, so gather has only been tested with stubs over saved pages.
- 2B and 9B.
- Thinking mode.
- Pages larger than 2 chunks on the live model.
