# Sufficiency check: plan

Branch `sufficiency-check`, cut from `origin/bonsai-client` (d118285). All model calls go through `llm/client.py` to local Bonsai 2 4B.

## Approach

1. **Judge by answering, not labelling.** The model gets the question, today's date, and the page. It replies in JSON with `answer` and `quote`. A `quote` is the exact line from the page that it used, or `null` if the page does not answer the question. No "enough / not enough" label.
2. **Code decides `enough`.** It is true only when `answer` is non-empty, `quote` is non-empty, and the normalised quote (lowercase, whitespace collapsed, quotes and dashes unified) is a substring of the normalised page. Otherwise it is false and `reason` says why (`no_answer`, `quote_not_in_page`).
3. **Long pages.** If the page does not fit `PAGE_BUDGET` = 6000 tokens, `split_to_budget` cuts it into chunks. Each chunk is judged in order, stopping at the first one that is enough. The quote is checked against that chunk.
4. **Low temperature for judging.** The one change to `llm/client.py`: `chat()`, `complete()` and `complete_json()` get an optional `sampling: dict | None = None` that is merged over the preset for that call. Judge and rephrase use `{"temperature": 0.2}`. The default stays the same for everyone else.
5. **Rephrase** asks the model for one new query given the question and the queries already tried. Code then rejects a repeat (normalised exact match or same word set). On a repeat it asks once more, showing the repeat. If that also repeats, it returns `None`.
6. **Gather** runs the loop: search, read the titles and snippets, open the results in the search order, judge each, and stop at the first that is enough. Otherwise it rephrases and searches again, up to `max_rephrases`. URLs already opened are skipped. It ends with a clear not-found that lists the queries and URLs tried.

## File layout

```
llm/client.py                 + sampling= override (only change in llm/)
sufficiency/__init__.py       exports judge, rephrase, gather, Verdict, GatherResult
sufficiency/prompts.py        JUDGE_SYSTEM, judge_prompt(), REPHRASE_SYSTEM, rephrase_prompt()
sufficiency/judge.py          judge(), quote_in_page(), normalise()
sufficiency/rephrase.py       rephrase(), is_repeat()
sufficiency/gather.py         gather(), the search/open adapter
sufficiency/eval/fixtures/    s01..s08 new fixtures (same shape as llm/eval/fixtures/p*.json)
sufficiency/eval/run_check.py runs judge on p01..p08 (read in place, unchanged) + s01..s08, N runs
sufficiency/eval/results/     4B_run{1,2,3}.json
sufficiency/tests/test_*.py   unittest, stubbed client, no server
docs/sufficiency-check.md     usage, final prompt, numbers
```

## Signatures and return shapes

```python
@dataclass
class Verdict:
    enough: bool
    answer: str | None      # model's answer, None when not enough
    evidence: str | None    # the quote, only when it was found in the page
    reason: str             # "answered" | "no_answer" | "quote_not_in_page" | "bad_json"
    url: str | None = None
    chunk: int = 0          # which chunk answered (0 if the page fit in one)
    chunks: int = 1
    seconds: float = 0.0    # total model time for this judge call

def judge(question: str, page_text: str, url: str | None = None,
          today: date | str | None = None) -> Verdict
    # today: a date or a pre-formatted string. Default is date.today(), written as "Saturday, 14 November 2026".

def quote_in_page(quote: str, page: str) -> bool
def rephrase(question: str, tried_queries: list[str], today=None) -> str | None

@dataclass
class Hit:    title: str; url: str; snippet: str = ""
@dataclass
class Page:   title: str; text: str

@dataclass
class GatherResult:
    found: bool
    answer: str | None
    evidence: str | None
    source: Hit | None          # title + url of the page that answered
    queries: list[str]          # every query searched, in order
    opened: list[str]           # every url opened, in order
    verdicts: list[Verdict]
    message: str                # e.g. "Not found after 3 searches, 14 pages opened: ..."

def gather(question: str, search_fn, open_fn, max_results: int = 10,
           max_rephrases: int = 2, today=None) -> GatherResult
```

**Adapter** (in gather.py, one place): `_hits(raw)` turns whatever `search_fn(query)` returns into `list[Hit]`. It accepts dicts with `title/url/snippet` or tuples. `_page(raw)` turns `open_fn(url)` into a `Page`, accepting a dict with `title/text` or a plain string. An `open_fn` exception or empty text counts as unreadable, gets skipped, and is recorded in `opened` with a mark. The first query is the question itself.

**Title reading:** the order stays as search returned it (no extra model call to rank). Hits whose title and snippet share no content word with the question are pushed to the end, not dropped. This is cheap and needs no model.

## Starting prompt

System:
> You answer questions using only the web page you are given. You never use outside knowledge and never guess.

User:
> Today is {today}.
> QUESTION: {question}
> PAGE ({url}):
> {page}
>
> If the page answers the question, even in different words, give the answer and copy the exact line from the page that supports it. If the page does not answer it, set answer and quote to null.
> Reply with only JSON: {"answer": "short answer, or null", "quote": "exact text copied from the page, or null"}

`max_tokens=300`, temperature 0.2, thinking off. `complete_json` is used, so invalid JSON gets one retry; a second failure gives `reason="bad_json"`, enough=false.

Rephrase user prompt:
> Today is {today}. We are searching the web to answer: {question}
> Queries already tried (do not repeat them or reword them trivially): {tried}
> Write one new search query that is more likely to find a page with the answer. Reply with only the query.

## Fixtures (new, s01–s08, written once and not tuned against)

| id | case | expected |
|---|---|---|
| s01_paraphrase_yes | "When does the dining hall stop serving dinner?" / page: "Evening meal service ends at 8:30 PM" | enough |
| s02_paraphrase_yes | "Do I need a permit to park on campus overnight?" / page: "Vehicles left in campus lots between 2am and 6am must display a valid overnight pass" | enough |
| s03_elsewhere_no | right club page, "Meeting times are listed on our Instagram" | not enough |
| s04_elsewhere_no | right course page, "Exam room assignments will be emailed" | not enough |
| s05_long_end_yes | a ~9k-token handbook page, the answer is in the last section (forces 2 chunks) | enough |
| s06_long_end_yes | a long FAQ, the answer is the last Q&A (fits in one chunk, near the end) | enough |
| s07_similar_no | asks for the spring add/drop deadline, page gives only the fall one | not enough |
| s08_similar_no | asks for the 4110 TA's office hours, page gives the 3110 TA's | not enough |

The scorer in `run_check.py` checks `verdict.enough == expected`. A "yes" also needs `evidence` to contain a short `expect_evidence` substring from the fixture, so a right label with the wrong quote still counts as a miss. Three runs at 4B. Target: p01–p08 8/8 and s01–s08 ≥ 7/8 on each run.

## Tests (no server, `python -m unittest discover sufficiency/tests`)

- quote check: whitespace, case and curly quotes all match; a made-up quote is rejected; an empty quote is rejected.
- judge with a stubbed `complete_json`: a good quote gives enough; a bad quote gives not enough and `quote_not_in_page`; null gives `no_answer`.
- chunking: a long page with a tiny `PAGE_BUDGET` gives several chunks, stops at the first enough one, and reports `chunk`/`chunks`.
- rephrase: a repeat triggers a second ask, and a second repeat returns None.
- gather: stub search/open over saved pages. Covers found on the first query, found after a rephrase, not found after the limit (queries and opened listed), a URL not reopened, and an open failure skipped.
- client: `sampling=` is merged into the request body (patch `_request`).

## Server

Check port 8080 first and reuse it if it is up. Otherwise run `scripts/serve_bonsai.sh 4B` and tell worker 5 when I start and stop it.

## Open questions

1. **Quote must be one exact span.** If the model joins two lines ("Rain likely after 1pm ... high 47F"), the check fails. Plan: accept it if every part, split on "..." or newlines, appears in the page. Is that OK, or should it be strictly one span?
2. **The p02 "this week" question has two due items.** Is quoting one line enough, or must the answer list both? Plan: one supporting quote is enough. The doc will note that the answer text may be incomplete.
3. **Today's date for p01/p02.** The original check used Friday 13 Nov 2026, so I'll pass that same date for p01–p08 and the new fixtures, not the real today.
