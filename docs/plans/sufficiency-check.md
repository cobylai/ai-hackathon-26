# Plan: sufficiency check

Branch `sufficiency-check`, cut from `origin/bonsai-client` (d118285). Every model call goes to local Bonsai 2 4B through `llm/client.py`.

## Approach

- **Judging by answering.** I will stop asking for an "enough / not enough" label. Instead the model answers the question from the page and copies the line it used. Code then decides `enough`. The old prompt made "not enough" the cautious choice and gave the model no way to show its work. This prompt asks a concrete task the model can do, and reworded answers count as answers.
- **Starting judge prompt.** System: *"You answer questions using only the web page you are given. You never use outside knowledge and never guess."* User: *"Today is {today}. QUESTION: {question} PAGE ({url}): {page} — If the page answers the question, even in different words, give the answer and copy the exact line from the page that supports it. If it does not answer it, set answer and quote to null. Reply with only JSON: {"answer": "short answer, or null", "quote": "exact text copied from the page, or null"}"*. It is sent through `complete_json` with `max_tokens=300` and thinking off.
- **Quote check (the guardrail).** Both the quote and the page are lowercased, runs of whitespace become one space, curly quotes and dashes become plain ones, and leading and trailing punctuation is stripped from the quote. A match means the normalised quote is a substring of the normalised page. If the model joins pieces with "..." or a line break, each piece of 8 or more characters must match, and there must be at least one such piece. If every piece is shorter than 8 characters, the quote fails as `quote_not_in_page`. A missing quote, an empty answer or no match gives `enough=False`.
- **Long pages.** A page over `PAGE_BUDGET = 6000` tokens is cut with `split_to_budget`. Chunks are judged in order, stopping at the first that is enough. The quote is checked against that chunk.
- **Sampling.** Judging and rephrasing use temperature 0.2. The other preset values (top_p 0.8, top_k 20, presence_penalty 1.5) are unchanged. Low temperature cuts the run-to-run variation the brief worries about. I'm not using greedy decoding (0), because the model card warns it causes repetition.
- **The one `llm/client.py` change.** `chat()`, `complete()` and `complete_json()` get an optional `sampling: dict | None = None` argument. It is merged over the preset for that call only. The default behaviour is unchanged.
- **Rephrase.** One model call gets the question and the queries already tried, and returns one query. If the new query normalises to a tried one, or has the same set of words, code asks once more with the repeat shown. A second repeat returns `None`.
- **Gather loop:**
  1. The first query is the question itself.
  2. Call `search_fn(query)` and keep the first `max_results` (10) hits.
  3. Read the titles and snippets. Hits that share no content word with the question move to the end. Nothing is dropped, and this uses no model call.
  4. Skip URLs already opened. Open the rest one at a time in that order and `judge` each. An open that raises an error or returns empty text is recorded and skipped.
  5. Stop at the first verdict with `enough=True` and return it, with the hit as the source.
  6. If none is enough, `rephrase` and go back to step 2, up to `max_rephrases` (2) times. That is at most 3 searches and 30 pages.
  7. Give up when the rephrases are used up or `rephrase` returns `None`. It returns `found=False` with every query tried, every URL opened and a one-line message, for example: *"Not found after 3 searches and 22 pages. Tried: …"*

## File layout

`llm/client.py` (the `sampling=` change only) · `sufficiency/__init__.py` · `sufficiency/prompts.py` (both prompts) · `sufficiency/judge.py` · `sufficiency/rephrase.py` · `sufficiency/gather.py` (loop and adapter) · `sufficiency/eval/fixtures/s01–s08.json` · `sufficiency/eval/run_check.py` (judges p01–p08, read in place and unchanged, plus s01–s08, `--runs 3`) · `sufficiency/eval/results/4B_run{1,2,3}.json` · `sufficiency/tests/test_judge.py`, `test_gather.py`, `test_client_sampling.py` · `docs/sufficiency-check.md`

## Interface

- `judge(question, page_text, url=None, today=None) -> Verdict`. Verdict fields: `enough` (bool), `answer` (str or None), `evidence` (the quote, set only when it passed the check), `reason` (`"answered"`, `"no_answer"`, `"quote_not_in_page"` or `"bad_json"`), `url`, `chunk` (index of the chunk that answered), `chunks` (total), `seconds` (model time). `today` is a `date` or a string. The default is the real date, written like "Saturday, 14 November 2026".
- `quote_in_page(quote, page) -> bool`.
- `rephrase(question, tried_queries, today=None) -> str | None`.
- `gather(question, search_fn, open_fn, max_results=10, max_rephrases=2, today=None) -> GatherResult`. Fields: `found`, `answer`, `evidence`, `source` (a `Hit`: `title`, `url`, `snippet`), `queries` (list of str), `opened` (list of url), `verdicts` (list of Verdict), `message`.
- **Assumed browser shapes**, both kept in one adapter in `gather.py`. `search_fn(query: str)` returns a list of `{"title", "url", "snippet"}` dicts. `open_fn(url: str)` returns `{"title", "text"}`. The adapter also accepts a plain string from `open_fn`.

## Test fixtures

The 8 originals, p01–p08, stay unchanged. The 8 new ones were written once and are not tuned against:

| id | question | expected |
|---|---|---|
| s01_paraphrase_yes | When does the dining hall stop serving dinner? (page: "evening meal service ends at 8:30 PM") | enough |
| s02_paraphrase_yes | Do I need a permit to park on campus overnight? (page: "lots between 2am–6am require an overnight pass") | enough |
| s03_elsewhere_no | When does the chess club meet? (page: "meeting times are on our Instagram") | not enough |
| s04_elsewhere_no | Which room is the CS 2800 final in? (page: "room assignments will be emailed") | not enough |
| s05_long_end_yes | How many guest passes do residents get per semester? (~9k-token handbook, answer in the last section, so 2 chunks) | enough |
| s06_long_end_yes | Can I bring a calculator to the placement exam? (long FAQ, answer is the last item) | enough |
| s07_similar_no | When is the spring add/drop deadline? (page gives only the fall deadline) | not enough |
| s08_similar_no | When are the CS 4110 TA office hours? (page gives the CS 3110 TA's) | not enough |

A fixture marked "enough" passes only if `evidence` also contains the fixture's `expect_evidence` text.

## Done-when

- Tests pass with no server running: `python -m unittest discover sufficiency/tests`. They cover the quote check (including a quote whose "..." pieces are all under 8 characters, which must fail), chunking, rephrase repeats, the gather loop over stub pages (found first try, found after a rephrase, gives up, no URL reopened, open failure skipped) and the `sampling=` merge.
- On live 4B, 3 runs score 8/8 on p01–p08 and at least 7/8 on s01–s08 each time. If they don't, I report where they fail and keep the scoring as it is.
- `docs/sufficiency-check.md` has the numbers per run, the final prompt, the median seconds per judge call, and anything not run.
- Everything is committed and pushed. I report the sha.

## Open questions

1. A quote joined with "..." passes if each piece of 8 or more characters is in the page and there is at least one such piece. **Default: yes.**
2. For p02 ("what's due this week"), quoting one of the two due items counts as enough, even if the answer misses the other. **Default: yes.**
3. All fixtures use Friday 13 November 2026 as "today", the date the original check used. **Default: yes.**
