# Context bank: plan

Branch `context-bank`, cut from `d118285` (bonsai-client). New code goes only in `bank/`, plus `docs/context-bank.md` and one `.gitignore` line. Nothing in `llm/` changes.

## Approach

- **Bonsai 4B pulls out text fields only:** sender, subject, summary, ask, deadline phrases copied word for word, course and topic. One `complete_json` call per chunk, thinking off.
- **Code does everything that has to be exact:**
  - Parse the `From:`, `Date:` and `Subject:` headers when they are present. The header value wins over the model's. This fixes the e07 miss, where the model gave a name instead of an address.
  - Resolve each deadline phrase to a date, relative to the sent date.
  - Find the course code with a regex. The model's course field is the fallback.
  - Classify the entry.
  - De-duplicate.
  - Write the files and the index.
- **Reading needs no network.** search, by_person and due only parse markdown files on disk. They never import `llm`.
- **Standard library only.** Tests use `unittest`. Everything runs with the Bonsai venv Python 3.12.

## File layout

```
bank/
  __init__.py      ingest, search, by_person, due, rebuild_index, bank_dir
  extract.py       prompt, header parsing, model call, merging chunks
  dates.py         resolve(phrase, sent, prev=None)
  classify.py      find_course(), is_person(), classify()
  store.py         bank_dir(), content_hash(), write_entry(), read_entry(), all_entries()
  index.py         rebuild_index(), index_line()
  query.py         search, by_person, due
  load.py          python -m bank.load <folder> [--kind email|page]
  eval/fixtures/   o01–o10 (the 10 originals, re-scored on resolved dates) + n01–n06 (new)
  eval/run_extract.py   python -m bank.eval.run_extract --runs 3
  eval/results/    4B_run{1,2,3}.json (synthetic only, so they are safe to commit)
  tests/test_dates.py, test_classify.py, test_store.py, test_query.py   (no model server needed)
```

**Data location:** `data/bank/` by default, or `$MUSE_BANK_DIR`. The layout is `data/bank/{course,person,other}/<sent-date>-<subject-slug>-<hash12>.md`, plus `data/bank/index.md`. `.gitignore` gets `data/`. The tests and the eval write only to a temp directory and never to `data/`.

## Entry format

The front matter is `key: value`, one per line. Values are JSON (strings quoted, `null`, lists inline), so a 10-line parser reads them back without PyYAML. The body is the summary.

```markdown
---
id: "3f9a1c0b7d2e"
kind: "email"
class: "course"
source: "inbox/2026-11-12-reyes.txt"
sender_name: "Prof. Daniel Reyes"
sender_address: "dreyes@univ.example.edu"
sent_date: "2026-11-12"
subject: "ENGRD 2700 project extension"
ask: "Submit the final notebook and a one page reflection on the course site."
deadlines: [{"phrase": "Monday 11:59pm", "date": "2026-11-16", "time": "23:59"}]
course: "ENGRD 2700"
topic: "project 2 deadline extension"
ingested_at: "2026-11-14T15:02:11"
---
Project 2 is now due Monday 11:59pm because of the server outage. No more extensions will be given.
```

The `id` is the first 12 hex characters of the sha256 of the text, with whitespace collapsed and leading and trailing space stripped. The same content gives the same id, so ingesting it again is skipped.

## Functions

```python
ingest(text: str, source: str, kind: Literal["email", "page"]) -> dict
  # -> {"status": "added" | "duplicate", "path": str, "entry": Entry}
search(query: str, limit: int = 10) -> list[Entry]
  # case-insensitive; drops stopwords; scores = number of distinct query terms found in
  # fields + body (subject/sender hits count double); needs ≥1 hit; ties → newest sent_date
by_person(name: str) -> list[Entry]
  # substring match on sender_name or sender_address, newest first
due(start_date: date | str, end_date: date | str) -> list[dict]
  # inclusive; one row per resolved deadline:
  # {"date": "2026-11-16", "time": "23:59" | None, "phrase": str, "entry": Entry}
  # sorted by date, then time (None last)
rebuild_index() -> Path   # also called at the end of every ingest
```

`Entry` is a dict with the front matter keys, plus `body` and `path`.

**Index line** (one per entry, newest first, summary cut to 100 characters):

```
2026-11-12 | Prof. Daniel Reyes | course ENGRD 2700 | Project 2 now due Monday 11:59pm… | due 2026-11-16 23:59 (Monday 11:59pm) | course/2026-11-12-engrd-2700-project-extension-3f9a1c0b7d2e.md
```

Each line is about 60–70 tokens, so about 300 entries fit in about 20k tokens. If the index goes over 20k tokens, `rebuild_index` writes only the newest entries that fit and adds the line `(N older entries omitted)`, so the file can always be handed to Bonsai whole.

## Date rules (`bank/dates.py`)

The anchor `S` is the sent date. For pages, it is the ingest date. All rules ignore case. The original phrase is always kept. If no rule matches, `date` is `null`, and the entry still shows up in search.

| Phrase | Resolves to |
|---|---|
| today, tonight, this morning/afternoon/evening, end of day, EOD | S |
| tomorrow (morning/night…) | S+1 |
| `<weekday>` / this `<weekday>` / by `<weekday>` / before `<weekday>` | next occurrence strictly after S (same weekday as S → S+7) |
| next `<weekday>` | that weekday in the calendar week (Mon–Sun) after S's week |
| the `<weekday>` after | that weekday strictly after the previous deadline in the same email (`prev`), else after S |
| end of (the) week | the Friday on or after S |
| next week | Monday of next week |
| Nov 20 / November 20th / 20 Nov / 11/20 / 2026-11-20 | that date. Year is S's year; if that is more than 60 days before S, next year |
| the 25th / on the 20th | that day in S's month if ≥ S's day, else next month |
| in N days / in N weeks | S + N days / S + 7N days |

- **"before X" resolves to X**, not X−1. The phrase is kept, so the reader sees "before".
- **Time** is pulled separately: `5pm`, `5:00pm`, `11:59 pm`, `noon` (12:00), `midnight` (23:59). Otherwise it is `null`. "Morning", "night" and similar give no time.
- **Checked against the originals:** o01 Fri→11-13 17:00, o03 Tue→11-17, o04 tomorrow→11-13, o06 Mon→11-16 23:59, o07 Thu noon→11-12 12:00, o09 the 25th→11-25 17:00, o10 Sun→11-15, Wed→11-18 14:30, "the Friday after"→11-20.

## Classification

- `course` when a course code is found: regex `\b[A-Z]{2,6} ?\d{4}\b`, searched in the subject first and then the body, and normalized to `"CS 3110"`. If there is no match, the model's `course` field is used only when it passes the same regex.
- Otherwise `person` when the sender looks like a person:
  - the model says `sender_is_person: true`;
  - and the address local part does not match `noreply|no-reply|news|notify|notifications|info|admin|office|bursar|registrar|dining|club|team|support|alerts`;
  - and the name does not contain Office, Club, Dining, Team, Department, Services, Library or University.
- Otherwise `other`. Pages are always `course` or `other`.
- **Expected for the originals:** o01, o06, o10 → course; o03, o04, o07, o08 → person; o02, o05, o09 → other.

## Long text

- If the text is longer than 6,000 tokens (the `llm.tokens` count), `llm.split_to_budget(text, 6000)` splits it and each chunk is extracted on its own.
- Headers, sender and subject come from chunk 1. The summary is chunk 1's.
- The ask comes from the first chunk that has one. Deadlines are the union over chunks, de-duplicated on (date, phrase).
- No extra summarizing call.

## Starting prompt

System: `You extract facts from emails and web pages for a student's personal notes. You copy words exactly and never invent information.`

User:

```
Read the {kind} below and fill in the JSON.

Rules:
- sender_address: the email address in the From line. Never a name.
- ask: the one thing the reader is asked to do, in one sentence. A bill or statement that
  says payment is due asks the reader to pay. Newsletters, announcements and generic lines
  like "visit the website", "questions? contact us" or "have a great week" are not asks:
  use null.
- deadlines: every time by which the reader must do something, copied exactly as written,
  including relative words such as "tomorrow morning", "Friday at 5pm", "before Tuesday",
  "the 25th". Do not convert them to dates. Event days in a newsletter (menus, hours)
  are not deadlines. Empty list if none.
- course: a course code like "CS 3110" if the text names one, else null.

{KIND}:
{text}
```

Hint:

```json
{"sender_name": "name in the From line, or null", "sender_address": "email address, or null",
 "sender_is_person": true, "subject": "subject line, or page title",
 "summary": "one or two sentences", "ask": "sentence or null",
 "deadlines": ["phrase as written"], "course": "code or null", "topic": "a few words"}
```

`max_tokens` is 400 and the presets are the client defaults. The prompt does not tell the model today's date, because it is not allowed to do date math.

## Fixtures and scoring

- **o01–o10:** the 10 existing emails, copied unchanged. The expected values gain `sender_address`, `sent_date`, `ask_keywords`, `deadline_dates` (the resolved dates as a set), `class` and `course`.
- **n01–n06:** six new synthetic fixtures, written and committed **before** the first model run and never tuned against afterwards:
  - **n01:** a course TA email with an explicit "Nov 20 at 11:59pm". Course.
  - **n02:** an automated library overdue notice, "return by 11/18". Other, ask = return.
  - **n03:** a friend asking for notes "tonight". Person.
  - **n04:** a professor announcement with a "next Monday" quiz and no course code in the subject, only in the body. Course.
  - **n05:** a course web page (kind = page) listing "PS5 due Nov 24" and "Final project due Dec 4". Course, no sender.
  - **n06:** a club email, "RSVP by end of day Wednesday". Other, ask = RSVP.
- **An entry is right when all of these match:**
  - `sender_address` and `sent_date` are exact.
  - The ask keywords hit, or the ask is null when none is expected.
  - The set of deadline dates is exact.
  - `class` and `course` are exact.
- The summary is checked only for being non-empty.
- **What gets reported:** the raw model field accuracy (before the header override) and the final entry accuracy, per run, for 3 runs. The target is ≥9/10 originals and ≥5/6 new on every run. Failures are reported as they are; the scoring is not loosened.

## Server

The eval needs `:8080` with 4B loaded. Check first (`curl -s localhost:8080/v1/models`). If it is already up, reuse it. If it is not, start it with `scripts/serve_bonsai.sh 4B` and tell worker 4. Never stop a server I did not start.

## Open questions (my default in brackets, and I proceed with it unless told otherwise)

1. Do the `From:`/`Date:` headers override the model? [Yes. Both numbers are reported, so the model's own accuracy stays visible.]
2. Is "before Tuesday" stored as Tuesday? [Yes, with the phrase kept.]
3. Is the index capped at 20k tokens, newest first? [Yes.]
4. Do pages use the ingest date as the anchor, unless the page states a date? [Yes.]
5. The bank does not answer questions with Bonsai itself. It exposes the index and the readers, and the answering layer belongs to someone else. [Out of my lane unless told.]
