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

## What I would change, in order

1. **Classify the DDG challenge as `BLOCKED`** (add "bots use duckduckgo too" / "confirm this search was made by a human" to `state.BLOCKED_PHRASES`). Then `search` tells the model `BLOCKED` instead of "0 results", and the tool status is honest.
2. **Only remember the fallback when it works.** Set the ten-minute window only if DuckDuckGo returned results; when both engines fail, clear it (or retry Google after a minute) so a dead DDG cannot poison the rest of the session.
3. **Always rank the page's opening chunk**, or use k=3 at size 400, for definition and date questions. That is where "HTTP stands for Hypertext Transfer Protocol" and "the wall fell in 1989" usually are.
4. **Spend fewer model calls.** q05 used 14 calls and 15.6k chars for one answer; two pages per round would have roughly halved it without changing the result.
5. **Report real tokens.** `ask` throws away the `usage` block; returning it would replace the chars/4 estimate with exact prompt tokens.

Measurement: input chars = `len(llm.SYSTEM) + len(prompt)` for every `ask` call, which is
what the model is sent, not counting the browser's page text that never reached it.
