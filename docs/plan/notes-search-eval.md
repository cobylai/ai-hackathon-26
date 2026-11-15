# S8: live web-search evaluation (2026-11-14)

Model: `qwen/qwen3.5-9b` on LM Studio (`http://127.0.0.1:1234/v1`), `LLM_REASONING_EFFORT=none`
(it is a reasoning model and returns empty content otherwise). Browser: default profile
`~/.harness/profile`, page cache warm from one pre-run smoke test (the Lisbon page).
Twelve questions from `tests/eval/questions.jsonl`, one sequential run.

```
LLM_BASE_URL=http://127.0.0.1:1234/v1 LLM_MODEL=qwen/qwen3.5-9b \
LLM_REASONING_EFFORT=none uv run python scripts/eval_search.py --json /tmp/eval_rows.json
```

## Run 1, all twelve questions

| # | kind | pass | rounds | pages | blocked | model calls | input chars | seconds |
|---|---|---|---|---|---|---|---|---|
| q01 | weather | yes | 1 | 3 | 1 | 6 | 5443 | 18.2 |
| q02 | date | NO | 3 | 3 | 0 | 11 | 11560 | 21.1 |
| q03 | date | yes | 3 | 5 | 0 | 12 | 10172 | 20.7 |
| q04 | definition | NO | 2 | 4 | 0 | 10 | 8550 | 16.3 |
| q05 | definition | yes | 3 | 6 | 0 | 14 | 15603 | 35.5 |
| q06 | definition | yes | 3 | 6 | 0 | 13 | 11150 | 19.6 |
| q07 | recent | NO | 3 | 0 | 0 | 2 | 731 | 2.8 |
| q08 | recent | NO | 3 | 0 | 0 | 2 | 723 | 2.9 |
| q09 | howto | NO | 3 | 0 | 0 | 2 | 728 | 2.9 |
| q10 | howto | NO | 3 | 0 | 0 | 2 | 678 | 2.6 |
| q11 | fact | NO | 3 | 0 | 0 | 2 | 712 | 2.4 |
| q12 | fact | NO | 3 | 0 | 0 | 2 | 721 | 2.8 |

**pass 4/12** (target 9/12), median 9.6 s, median 3,087 chars, 1 blocked page.
Those medians are flattered by six fast failures: questions 7 to 12 never reached a page.

Same twelve, restricted to the six that actually found the web (q01 to q06):

- **pass 4/6**
- median **20.1 s** (target under 20 s, missed by a tenth of a second)
- median **10,661 chars** of model input, mean 10,413 (target under 8,000, missed by ~30%)
- 62,472 chars in total, roughly 15.6k tokens at 4 chars per token
- 27 pages opened, 1 BLOCKED (3.7%)

## Run 2, questions 7 to 12 again in a fresh process (~6 minutes later)

| # | pass | rounds | pages | blocked | input chars | seconds |
|---|---|---|---|---|---|---|
| q07 | NO | 3 | 0 | 0 | 731 | 3.2 |
| q08 | NO | 3 | 0 | 0 | 723 | 2.7 |
| q09 | NO | 3 | 0 | 0 | 728 | 2.7 |
| q10 | NO | 3 | 0 | 0 | 678 | 2.6 |
| q11 | NO | 3 | 0 | 0 | 712 | 2.4 |
| q12 | NO | 3 | 0 | 0 | 721 | 2.6 |

Identical failure, so it is the walls, not the questions.

## What happened at question 7

Google answered `/sorry/` to the browser (correctly classified `BLOCKED`), so the engine
fell back to DuckDuckGo. DuckDuckGo's HTML endpoint then served its own bot challenge:

```
DuckDuckGo Unfortunately, bots use DuckDuckGo too. Please complete the following challenge
to confirm this search was made by a human. Select all squares containing a duck: Submit
```

That page has no captcha iframe and none of `state.BLOCKED_PHRASES`, so `classify` says
`OK`. Nothing parses, so `engine.search` returns `[]` and the loop reports "no useful
results" instead of `BLOCKED`. The fallback is then remembered for ten minutes, so every
later query in that process goes straight back to the same challenged page: 18 searches,
0 pages, about 2.5 s per question. No wall was worked around; it is recorded as it was.

## Content misses (q02, q04)

Both stopped honestly rather than inventing an answer:

- q02 ("when did the Berlin Wall fall?"): "Note [1] explicitly states that the specific date of the fall is not mentioned, and Note [2] describes the event and its context but does not provide a date."
- q04 ("what does HTTP stand for?"): "None of the cited sources contain the definition of the acronym HTTP; they only list version numbers, connection details, or explicitly state that the definition is missing."

The sentence existed on some opened page but not in the two BM25 chunks that were read,
or it was dropped at the note step. Definition and date answers usually sit in a page's
opening chunk, which BM25 does not favour when the question words are all over the page.

## Run 3, after the five fixes (cold cache, 20 s between questions)

The five fixes below were applied first, one commit each: DDG challenge classified `BLOCKED`,
fallback remembered only on success, opening chunk always read, two pages per round, real prompt
tokens from `ask`. The page cache was cleared before the run (backup kept outside the repo), so it
is cold like Run 1. `--pause-seconds 20` between questions; still no wall workaround.

| # | kind | pass | rounds | pages | blocked | model calls | input chars | prompt tokens | seconds |
|---|---|---|---|---|---|---|---|---|---|
| q01 | weather | yes | 2 | 2 | 0 | 9 | 7827 | 2411 | 16.2 |
| q02 | date | yes | 3 | 5 | 0 | 13 | 13399 | 3687 | 25.3 |
| q03 | date | yes | 3 | 4 | 0 | 12 | 10583 | 3177 | 18.9 |
| q04 | definition | yes | 2 | 4 | 0 | 10 | 7368 | 1897 | 11.7 |
| q05 | definition | yes | 3 | 4 | 0 | 13 | 12689 | 3606 | 27.9 |
| q06 | definition | yes | 3 | 4 | 0 | 11 | 8827 | 2382 | 14.7 |
| q07 | recent | yes | 3 | 5 | 0 | 15 | 14513 | 4423 | 28.2 |
| q08 | recent | yes | 3 | 4 | 0 | 11 | 9320 | 2776 | 18.3 |
| q09 | howto | yes | 3 | 6 | 0 | 12 | 10479 | 2909 | 22.4 |
| q10 | howto | yes | 3 | 3 | 1 | 11 | 8163 | 2270 | 19.2 |
| q11 | fact | yes | 3 | 3 | 0 | 12 | 12028 | 3497 | 24.2 |
| q12 | fact | yes | 3 | 3 | 0 | 11 | 8922 | 2620 | 17.2 |

- **pass 12/12** (target 9/12, met)
- median **19.0 s** (target under 20 s, met)
- median **9,900 chars** of model input, median **2,842 real prompt tokens** (target under 8,000 chars, missed by 24%)
- 47 pages opened, **1 BLOCKED** (2.1%), 140 model calls, 124,118 chars / 35,655 tokens in total
- rounds: two questions finished in 2 rounds, ten used all 3
- the six questions that had reached the web in Run 1 now score **6/6** at median 17.5 s and 9,705 chars (Run 1: 4/6, 20.1 s, 10,661 chars)

No search-level wall appeared this run: Google answered every query, so the wall fixes were
exercised by their tests rather than live. The single BLOCKED page (q10) was one result behind a
bot check; the loop skipped it and answered from the others.

## The five fixes, applied

1. **Classify the DDG challenge as `BLOCKED`** (`a09c632`). "bots use duckduckgo too", "confirm this search was made by a human" and "select all squares containing" are now in `state.BLOCKED_PHRASES`; `search` reports `BLOCKED` instead of "0 results".
2. **Remember the fallback only when it works** (`b58c9bc`). The ten-minute window is set only when DuckDuckGo returns results, and cleared when both engines fail or a remembered fallback stops answering.
3. **Always read the page's opening chunk** (`6d0271e`). With k=2 the first chunk keeps one slot and BM25 fills the other; this is what turned q02 and q04 from failures into passes. k=1 still returns the single best chunk.
4. **Two pages per round** (`6a5ae4c`). Each round now opens at most two pages. Median model calls per question is unchanged (11.5, the same as Run 1's productive six) because every question now reaches three rounds, but the per-round cost is bounded lower: the worst question needed 15 calls and 28.2 s (Run 1: 14 calls, 35.5 s).
5. **Real token counts** (`a207a97`). `ask` leaves the server's `prompt_tokens`/`completion_tokens` in `llm.last_usage`, and the eval reports them instead of chars/4.

## Still open

- **Input is still 24% over the 8,000-char target.** The note calls dominate: up to 4 chunks per round at ~600 chars plus prompt text. Options: one chunk per page once the opening chunk has scored, a smaller results listing, or accept the real-token metric (median 2,842) as the budget instead of characters.
- **The char target should probably become a token target**, now that exact tokens exist; 8,000 chars was only ever a stand-in for about 2,000 tokens.
- **Record which engine answered each query.** Run 1 walled Google after ~25 searches, Run 3 saw none, so "pass rate" depends on Google's mood; an engine column (google/ddg) would say which.
- **Three rounds is the common case** (10 of 12). The second page per round is cheap, but a stop rule such as "enough after a round that added two notes" might cut a round without losing answers.

Measurement: input chars = `len(llm.SYSTEM) + len(prompt)` for every `ask` call, which is
what the model is sent, not counting the browser's page text that never reached it.
