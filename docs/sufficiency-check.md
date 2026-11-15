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

## Web search: off-topic Bing results (2026-11-14)

The reported "character limit" was not a limit. The page text is never capped:
`open_page` returns the whole page, and judge splits it into 6000-token chunks.
A 77,150-character page took 6 chunks and answered in 7.5 s, with no BudgetError.
The real fault was in search. Google and DuckDuckGo show a bot check to the hidden
browser, so every search falls back to Bing, and Bing sometimes returns
off-topic results to it. "First president of Kenya" got ten visitprague.cz
pages, and "speed of light in km per second" got speed-test sites. Gather then
judged 17-20 junk pages and gave up after about 40 s.

Fix in `sufficiency/websearch.py`. A hit is dropped unless it shares at least
half of the query's content words (`relevant()`). When fewer than 3 hits are
left, Wikipedia's public search API adds up to 5 more. No bot check is bypassed
and the user agent is unchanged. `last_engine` notes any drops, e.g.
`bing (harness said BLOCKED), 10 off-topic dropped, + wikipedia`.

Live, `python -m reason`, online, Bonsai 2 4B, fresh bank:

| Question | Answer | Source | Seconds |
|---|---|---|---|
| Who was the first president of Kenya? | Jomo Kenyatta | en.wikipedia.org/wiki/President_of_Kenya | 10.3 |
| What is the speed of light in km per second? | 299792458 (m/s, not km/s) | en.wikipedia.org/wiki/Speed_of_light | 11.2 |
| Who won the 2022 FIFA World Cup? | Argentina | en.wikipedia.org/wiki/2022_FIFA_World_Cup_final | 10.2 |
| Who wrote Frankenstein? | Mary Shelley | en.m.wikipedia.org/wiki/Frankenstein | 8.3 |
| When did the Berlin Wall fall? | 9 November 1989 | en.m.wikipedia.org/wiki/Fall_of_the_Berlin_Wall | 8.2 |
| What is the chemical symbol for gold? | Au | en.wikipedia.org/wiki/Gold | 10.5 |
| Who painted The Starry Night? | Vincent van Gogh | en.wikipedia.org/wiki/The_Starry_Night | 8.9 |

Before the fix, Kenya and speed of light came back not found (42.9 s and
37.5 s), and the World Cup question took 59.7 s.

## Bot-check and error pages (2026-11-15, partner test report problem 7)

A misheard question ("Elena asked me") went to the web. Reddit's "Prove your
humanity" page came back as OK, so it was given as the answer and filed in the
bank. `sufficiency/junk.py` now adds a second check on our side:

- gather skips any page whose status isn't OK, as before (`_page` gives empty
  text). It also skips any page of 3000 characters or less that contains a
  bot-check or error-page phrase. Both count as unreadable.
- An answer or quote containing one of those phrases is refused
  (`reason: blocked_page`). The web route in `reason/answer.py` checks again
  before filing, so such a page is never saved.

Tests: `sufficiency/tests/test_junk.py` and `test_web_bot_check_answer_not_filed`
in reason. Live on a copy of the demo bank: "Elena asked me" and "What did
everyone ask me?" came back not found, and nothing was filed.

## Known limits

- **Pointer pages.** A page that only says where the answer is ("Meeting times are posted on our Instagram") can be accepted as the answer. Its quote is real, so the quote check passes. This is s03 with the shipped prompt. Thinker 0 ruled no further prompt work. The A/B check call (`CHECK_ANSWER = True`) catches these pointers but rejects answers that need date reasoning, so it is off.
- **Units.** The judge answers from the quote, so it may not convert units. "Speed of light in km per second" was answered as 299792458, which is the m/s figure.
- **Deadline.** `max_seconds` is checked between pages and, since 2026-11-15, between judge chunks (`judge(..., deadline=)`, reason `out_of_time`). A chunk that has already started still finishes. "What did everyone ask me?" went from 110 s to 70.4 s; the rest is the bank lookup, the search and that last chunk.
- **Short answers.** The `answer` text can be terse ("NO"). Show `evidence` with it.

## Not run

- Real browser functions. No `search` or `open` exist yet, so gather has only been tested with stubs over saved pages.
- 2B and 9B.
- Thinking mode.
- Pages larger than 2 chunks on the live model.
