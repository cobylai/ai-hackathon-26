# Sufficiency check

`sufficiency/` decides whether a page answers a question, and searches again with a reworded query when it doesn't. Every model call goes to local Bonsai 2 4B through `llm/client.py`. The plan is in `docs/plans/sufficiency-check.md`.

## Use

```python
from sufficiency import judge, rephrase, gather

v = judge("Is the gym open on Thanksgiving?", page_text, url=url, today=date.today())
# Verdict: enough, answer, evidence, reason, url, chunk, chunks, seconds

q = rephrase(question, tried_queries)            # str, or None after two repeats

r = gather(question, search_fn, open_fn, max_results=10, max_rephrases=2)
# GatherResult: found, answer, evidence, source (Hit: title/url/snippet),
#               queries, opened, verdicts, message
```

- `search_fn(query)` returns `[{"title", "url", "snippet"}, ...]`. `open_fn(url)` returns `{"title", "text"}`. A plain string is also accepted from `open_fn`. These shapes are assumed only in `_hits()` and `_page()` in `sufficiency/gather.py`.
- If `open_fn` raises or returns empty text, that URL is skipped.
- `reason` is one of `answered`, `no_answer`, `quote_not_in_page`, `bad_json`.

## How it judges

1. The model is asked to answer from the page and copy the exact line it used, as JSON `{"answer", "quote"}`. It is never asked for an enough / not enough label.
2. Code sets `enough=True` only if both fields are present and the quote is found in the page. The check ignores case, runs of whitespace, curly versus straight quotes, dash types, and punctuation at the ends of the quote. A quote joined with "..." or a line break is split into pieces. Every piece of 8 or more characters must match, and at least one such piece must exist.
3. Pages over `PAGE_BUDGET = 6000` tokens are split with `split_to_budget` and judged chunk by chunk, stopping at the first chunk that answers.
4. Judging and rephrasing run at temperature 0.2. The other preset values are unchanged. This uses the new `sampling=` argument on `chat`, `complete` and `complete_json` in `llm/client.py`, which is the only change to `llm/`.

### Final judge prompt (unchanged from the plan)

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

Run with `python -m sufficiency.eval.run_check --runs 3`, using the venv Python, against `scripts/serve_bonsai.sh 4B`. "Today" is Friday 13 November 2026, the same date as the original check.

- **Originals:** p01–p08, read in place from `llm/eval/fixtures/` and unchanged.
- **New:** s01–s08 in `sufficiency/eval/fixtures/`, written once and not tuned against, plus s09 (an answer that needs two items, added after review).
- **Scoring:** a fixture marked "enough" passes only if the label is right and the evidence also contains the expected text.

Two sets of runs used the same final prompt. The first was on an idle server. The second happened while worker 5 was also sending requests to the same server, so its times are slower.

| set | run | originals p01–p08 | new s01–s08 | s09 (two items) | median s per judge |
|---|---|---|---|---|---|
| A (idle server) | 1 | **8/8** | **7/8** | not yet written | 0.83 |
| A | 2 | **8/8** | **7/8** | — | 0.81 |
| A | 3 | **8/8** | **7/8** | — | 0.86 |
| B (shared server) | 1 | **8/8** | **7/8** | pass | 1.51 |
| B | 2 | **8/8** | **7/8** | pass | 1.12 |
| B | 3 | **8/8** | **7/8** | pass | 1.08 |

- **Target met on all 6 runs.** The target was all 8 originals and at least 7 of 8 new on each run. On the idle server, the median judge call took 0.83 s.
- **Old misses now pass.** The old label prompt scored 5/8 on the originals, wrongly calling p01, p02 and p06 "not enough". All three pass on every run.
- **s09, two items.** The question is "what do I bring to the prelim". It is scored on the answer naming both the ID and the pencil. It passed every run, and the model quoted both lines as a list. p02 also lists both due items and quotes both lines on every run, so multi-item answers already work with this prompt.
- **The one miss, s03 (every run).** The question is "When does the chess club meet this week?", and the page says "Meeting times are posted on our Instagram". The model gives that pointer as the answer and quotes it. The quote really is in the page, so the quote check can't catch it. I left the scoring as it is. s04 ("room assignments will be emailed") is the same kind of case and passed.
- **s07 and s08 passed every run.** These are the "similar but different question" fixtures. The pre-agreed fallback, a second yes/no call asking "does this answer this exact question", was therefore not added.
- **s05, the long page.** It is 7,510 tokens, so it splits into 2 chunks; the plan estimated about 9k. The second chunk answered every run, taking 11–14 s in total.
- **Short answers.** p06's `answer` was just "NO", while its evidence was the CLOSED line. Show `evidence` with `answer`.

### Prompt wordings tried and rejected

Both of these were tried on the shared server, 3 runs each. Results are in `results/rejected_*`.
- **"Give the full answer, including every item if there are several, and copy every line…", with the quote hint as a list.** The originals dropped to 7/8 on every run, because p07 ("Office hours are posted weekly on the course calendar") was accepted as an answer. s01–s08 went to 8/8 and s09 passed. That trades a miss on an original for a miss on a new fixture, which fails the target, and it isn't needed for multi-item answers.
- **The same, plus "A line that only says where the information can be found is not an answer."** Worse: 7/8 and 7/8, missing both p07 and s03. I stopped tuning there.

Pointer pages (p07, s03) are the remaining weak spot. The fix that follows from this is the second yes/no call above, aimed at pointers rather than at similar questions. It is not built.

Results are in `sufficiency/eval/results/4B_run{1,2,3}.json` (set B, which overwrote set A). Set A's numbers are in the table above and in git history at bf5630d.

### Live gather and rephrase

`python -m sufficiency.eval.live_gather` uses stub search and open functions over the saved fixture pages, with live 4B for judging and rephrasing. Output is in `sufficiency/eval/results/4B_live_gather.txt`.
- **Found on the first search:** the gym hours page.
- **Found after one rephrase:** the dining hall page, reached via the query "What time does the dining hall close for dinner on Friday, November 13, 2026?".
- **Gave up:** after 3 searches and 4 pages, with every query listed in the message.
- **Rephrase on its own:** it returned a new query that wasn't a repeat.

## Tests (no server)

`python -m unittest discover -s sufficiency/tests -t .` runs 30 tests with a stubbed client. They cover:
- the quote check, a list of quotes, and the case where every "..." piece is under 8 characters, which must fail
- judge verdicts, the date passed in, and the sampling setting
- chunking and stopping at the first chunk that answers
- rephrase rejecting repeats
- the gather loop: found on the first search, found after a rephrase, giving up, never reopening a URL, skipping failed opens, `max_results` and title ordering, and the adapter shapes
- the `sampling=` merge in `llm/client.py`

## Not run

- Real browser functions. No `search` or `open` exist yet, so gather has only been tested with stubs over saved pages.
- 2B and 9B.
- Thinking mode.
- Pages larger than 2 chunks on the live model.
