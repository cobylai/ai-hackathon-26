# Plan: reasoning layer (`reason/`)

Branch `reasoning-layer` from `origin/integration` ed93e1c. New code only in `reason/`; no change to `bank/`, `sufficiency/`, `llm/` or `harness/`.

## The function

```python
from reason import answer
a = answer("what is due Tuesday", today=None)   # today defaults to date.today()
# Answer: text (ends with the source line), route ("due" | "person" | "bank" | "web" | "offline" | "not_found"),
#         sources (bank entry paths, or one url), seconds
```

## Routing (code, in this order)

**1. Due.** Matches when the question has `due`, `deadline` or `deadlines` as a word. Code picks the range, calls `bank.due`, and writes the list itself. No model call.

| Phrase in question | Range |
|---|---|
| today, tonight | today |
| tomorrow | today + 1 |
| Monday … Sunday (alone, or after on/by/this) | the next such day, today if it is that day |
| next Friday (etc.) | that day in next Mon–Sun week |
| this week | today → this Sunday |
| this weekend | this Saturday → Sunday |
| next week | next Monday → next Sunday |
| a date: Nov 20, November 20th, 11/20, 2026-11-20 | that day |
| none of these ("what's due?") | today → today + 6, and the answer says "in the next 7 days" |

Answer: `Due Tue Nov 17:` then one line per row, `- 11:59pm  Submit your final notebook… (Prof. Daniel Reyes, Nov 12)`. The ask is the line text, else the summary. Empty: `Nothing due Tue Nov 17 in your saved mail.`

**2. Person.** Code builds the sender list from every entry's `sender_name` (and the part of `sender_address` before `@`). Name words of 3+ letters count, minus titles (Prof, Dr, Mr, Ms, Mrs) and automated words (Office, Club, Library, Department, Team, University, Services…). A question word matching one of them (case-insensitive, `'s` stripped) picks this route. Two modes: (a) if the question has a capitalized word other than its first word, only capitalized words are tried, and the stoplist does not apply ("what did Will say" matches Will); (b) otherwise every word is tried except a stoplist of common English words that are also names (will, may, mark, grant, bill, rose, june, art, august, frank, ray, sue, pat, joy, hope, …), so "will it rain" does not match Will but lowercase "what did emily ask" matches Emily. and `bank.by_person(that word)` gives the entries, newest 8. Bonsai gets the question and those entries only (from, date, subject, ask, deadlines, summary), numbered, and returns JSON `{"answer", "used": [numbers]}` at temperature 0.2. Sources are the used entries (all handed entries if `used` is empty or bad).

**3. Everything else.**
- `bank.search(question, limit=5)`. If it returns entries, they are joined into one notes text, one block per entry, and `sufficiency.judge(question, notes, today=today)` runs once. If enough: route `bank`, answer = verdict answer, source = the block whose text holds the quote (else the top entry).
- Not enough, and the network is up: route `web`. `gather(question, search_fn, open_page, max_seconds=60)`. `search_fn` is `sufficiency.websearch.search` (the partner's engine.search, then Bing; integration 4af9140 moved Bing out of harness into this module); `open_fn` is `harness.search.tools.open_page`. gather adapts both shapes. If found, the page text is fetched again with `open_page` (its 24 h cache makes this free) and `bank.ingest(text, source=url, kind="page")` files it. An ingest failure is reported in the answer's last line but does not lose the answer. Not found: route `not_found` with gather's message.
- Not enough, and the network is down: route `offline`, text `I don't have that saved, and the Mac is offline, so I can't look it up.`
- Network check: one `socket.create_connection(("www.bing.com", 443), timeout=2)`. harness is imported only on the web route, so offline answers never load Playwright.

**Source line.** Every answer ends with `Source:` and, per entry, `sender, Nov 12` (a page entry shows its url), or the page url for the web route. The due list carries the source on each line instead.

## Chat loop

`python -m reason [--today YYYY-MM-DD]`: reads a line, prints the answer and `[route, 3.2s]`, repeats until empty line / Ctrl-D. A thin wrapper over `answer()` so voice can call the same function.

## Tests (no model server)

`reason/tests/`, unittest, temp bank via `root=`: every row of the date table; route choice (due beats person; person match, titles and `'s`; "will it rain" with a sender named Will goes to search, "what did Will say" goes to person, lowercase "what did emily ask" goes to person; no match goes to search); due answer text and the empty case; person and bank routes with `llm`/`judge` stubbed; the offline message with the network check stubbed; web route with stub search/open and stubbed ingest.

## Live check

`reason/live_check.py`: loads the 16 bank fixtures' text into a scratch `MUSE_BANK_DIR` (outside the repo) with `bank.ingest`, then in a child process with `socket.connect` blocked for everything except localhost, asks: a due question for one day, a due question for a week, a person question, a bank-search question, and one the bank can't answer (expects the offline message). Then online, one web question through gather and the partner's browser, and checks its page landed in the bank. Answers, routes and seconds go into `docs/reasoning-layer.md`. Reuses worker 8's Bonsai on :8080.

## Not in scope

No model tool-picking, no planning step, no memory between turns, no other routes, no tuning of bank/ or sufficiency/.
