# Context store: plan

Branch `context-store`, cut from `d118285`. Code goes in `bank/`, the doc in `docs/context-store.md`, plus one `.gitignore` line. I will not touch `llm/`.

## Approach

- **Bonsai 4B fills in the text fields only.** It gives me the sender, subject, summary, ask, deadline phrases copied word for word, course and topic. That is one `llm.complete_json` call per chunk, with thinking off.
- **Code does everything that has to be exact:**
  - **Sender, date and subject come from the first of these that has them:**
    1. Values the caller passes to `ingest` (`sender_name`, `sender_address`, `sent_date`, `subject`). These win over everything.
    2. `From:`, `Date:` and `Subject:` header lines, when the text has them.
    3. Otherwise:
       - the model's sender and subject;
       - an address in angle brackets in the first lines if the model's address is not in the text;
       - code's own search for a dated line in the first 15 lines, such as "Nov 12, 2026, 3:14 PM (2 days ago)".
  - **No sent date found:** I use the ingest date and mark the entry `sent_date_guessed: true`, because every deadline in it depends on that date.
  - It turns each deadline phrase into a date.
  - It finds the course code.
  - It picks the folder.
  - It spots duplicates.
  - It writes the entry files and the index.
- **Reading never calls the model or the network.** `search`, `by_person` and `due` only read markdown files on disk, and `bank/query.py` never imports `llm`.
- **Long text:** if the text is over 6,000 tokens, `llm.split_to_budget(text, 6000)` splits it and each chunk is extracted on its own.
  - The header fields, summary and ask come from the first chunk that has them.
  - Deadlines are merged across chunks, with repeats removed.
- **Duplicates:** an item counts as already ingested in either of two cases. In both, `ingest` returns `"duplicate"` and writes nothing.
  - **Same source:** an existing entry has the same `source`. The partner's sync passes a stable message id as `source`, and scraped text can change between syncs ("3 minutes ago", for example), so this check comes first.
  - **Same content:** the content id is already in a file name. The id is the first 12 hex characters of the sha256 of the text, with whitespace collapsed. This is the fallback.
- **Data folder:** `data/bank/` by default, or `$MUSE_BANK_DIR` if that is set. The `.gitignore` line is `data/`. Tests and the eval write only to a temp folder.
- Standard library only. It runs on the Bonsai venv's Python 3.12, and the tests use `unittest`.

## File layout

**Code:**

```
bank/__init__.py   ingest, search, by_person, due, rebuild_index
bank/extract.py    prompt, header parsing, the model call, chunk merging
bank/dates.py      resolve(phrase, sent_date, prev_date=None) -> (date | None, "HH:MM" | None)
bank/classify.py   find_course(text), is_person(name, address, model_says), folder_for(entry)
bank/store.py      bank_dir(), content_id(text), write_entry(entry), read_entry(path), all_entries()
bank/index.py      rebuild_index()
bank/query.py      search, by_person, due
bank/load.py       python -m bank.load <folder> --kind email|page
bank/eval/fixtures/*.json, bank/eval/run_extract.py (--runs 3), bank/eval/results/
bank/tests/test_dates.py, test_classify.py, test_store.py, test_query.py
```

**The bank's data folder:**

```
data/bank/
  index.md
  course/2026-11-12-engrd-2700-project-extension-3f9a1c0b7d2e.md
  person/2026-11-12-re-lab-6-a81d0c44e9b2.md
  other/2026-11-11-statement-available-77c2e01f5a93.md
```

**Folder rule:**

- **`course/`** if a course code is found. The code is matched by `\b[A-Z]{2,6} ?\d{4}\b`, in the subject first, then the body, then the model's `course` field.
  - Some prefixes are never a course: months, seasons, ROOM, PIN, CODE, ZOOM, REF and ID. This rejects "FALL 2026", "NOV 2026", "ROOM 1234" and "PIN 4821".
  - A number from 2020 to 2030 after a month or season prefix is a year, and is rejected that way too. Other prefixes keep those numbers, because a course like "CS 2024" is real. Two tests cover this rule.
- **`person/`** otherwise, when the sender is a person. That means the model says `sender_is_person: true`, and neither the address nor the name looks automated.
  - An address looks automated when the part before the @, split on dots, dashes and underscores, has one of these as a **whole word**: `noreply`, `news`, `notifications`, `info`, `office`, `bursar`, `registrar`, `dining`, `club`, `team`, `support` or `alerts`. Whole words only, so "newsome" and "steam" stay people.
  - Automated names contain Office, Club, Dining, Team, Department, Services, Library or University.
- **`other/`** for everything else. Pages are never filed under `person/`.

**Example entry:** `data/bank/course/2026-11-12-engrd-2700-project-extension-3f9a1c0b7d2e.md`

The front matter values are JSON, so the parser is a few lines and needs no PyYAML. The body is the summary.

```markdown
---
id: "3f9a1c0b7d2e"
kind: "email"
folder: "course"
source: "inbox/reyes.txt"
sender_name: "Prof. Daniel Reyes"
sender_address: "dreyes@univ.example.edu"
sent_date: "2026-11-12"
subject: "ENGRD 2700 project extension"
ask: "Submit the final notebook and a one page reflection on the course site."
deadlines: [{"phrase": "Monday 11:59pm", "date": "2026-11-16", "time": "23:59"}]
course: "ENGRD 2700"
topic: "project 2 deadline extension"
sent_date_guessed: false
ingested_at: "2026-11-14T15:02:11"
---
Project 2 is now due Monday 11:59pm because of the server outage. No more extensions will be given.
```

**Example index line** (`data/bank/index.md`, one line per entry, newest first):

```
2026-11-12 | Prof. Daniel Reyes | course ENGRD 2700 | Project 2 now due Monday 11:59pm… | due 2026-11-16 23:59 (Monday 11:59pm) | course/2026-11-12-engrd-2700-project-extension-3f9a1c0b7d2e.md
```

- The summary is cut to 100 characters.
- A line is about 65 tokens, so 300 entries come to about 20k.
- Above 20k tokens, `rebuild_index` keeps the newest lines that fit and ends with `(N older entries omitted)`. That way the index can always be handed to Bonsai whole.

## Interface

```
ingest(text, source, kind, *, sender_name=None, sender_address=None, sent_date=None, subject=None)
  -> {"status": "added" | "duplicate", "path": str, "entry": dict}
  kind is "email" or "page".
  The entry dict holds the front matter fields, plus body and path.

search(query, limit=10) -> [entry, ...]
by_person(name) -> [entry, ...]
due(start_date, end_date) -> [{"date", "time", "phrase", "entry"}, ...]
rebuild_index() -> path of index.md
```

- **`ingest`** rebuilds the index at the end of every call.
- **`search`** ranks results like this:
  - Case is ignored and stopwords are dropped.
  - The score is the number of distinct query words found in the fields or the body.
  - A hit in the subject or the sender counts double.
  - An entry needs at least one hit to be returned.
  - Ties go to the newest `sent_date`.
- **`by_person`** matches the name as part of `sender_name` or `sender_address`, ignoring case. Results come newest first.
- **`due`** takes dates as `date` objects or as `YYYY-MM-DD` strings, and both ends count. It returns one row per resolved deadline, sorted by date, then by time, with rows that have no time last. The time is `"HH:MM"` or `None`.

**JSON asked of Bonsai** (passed as `json_schema_hint`):

```json
{"sender_name": "name in the From line, or null", "sender_address": "email address in the From line, or null",
 "sender_is_person": true, "subject": "subject line or page title",
 "summary": "one or two sentences", "ask": "one sentence, or null",
 "deadlines": ["each phrase exactly as written"], "course": "course code or null", "topic": "a few words"}
```

**Starting prompt.** The system line is: *You extract facts from emails and web pages for a student's notes. You copy words exactly and never invent information.* The user message is:

```
Read the {kind} below and fill in the JSON.
Rules:
- sender_address: the email address in the From line. Never a name.
- ask: the one thing the reader is asked to do. A bill or statement that says payment is due
  asks the reader to pay. Newsletters, announcements and generic lines like "visit the
  website", "questions? contact us" or "have a great week" are not asks: use null.
- deadlines: every time by which the reader must do something, copied exactly as written,
  including relative words like "tomorrow morning", "Friday at 5pm", "before Tuesday",
  "the 25th". Do not turn them into dates. Event days in a newsletter are not deadlines.
- course: a course code like "CS 3110" if the text names one, else null.
{KIND}:
{text}
```

I will not give the model today's date, so it has nothing to do date arithmetic with.

**Deadline phrasings the code resolves.** Each phrase resolves against S, the sent date from the `Date:` line. For a page, S is the ingest date. The original phrase is always kept beside the date.

| Phrase | Date |
|---|---|
| today, tonight, this morning / afternoon / evening, end of day, EOD | S |
| tomorrow, tomorrow morning / night | S + 1 |
| Monday … Sunday, this Friday, by Friday, before Tuesday | first such day on or after S (the same weekday as S means S itself) |
| next Friday | Friday of the week after S's week (weeks run Mon–Sun) |
| the Friday after | first Friday after the previous deadline in the same item, else after S |
| end of the week, end of week | Friday on or after S |
| next week | Monday of next week |
| Nov 20, November 20th, 20 Nov, 11/20, 2026-11-20 | that date. The year is S's year, or the next year if that would be more than 60 days before S |
| the 25th, on the 20th | that day in S's month if it is not already past, else next month |
| in 3 days, in 2 weeks | S + 3 days, S + 14 days |

- **Times** come out separately and can appear anywhere in the phrase, so "by 5pm Friday" gives Friday and 17:00. The forms are `5pm`, `5:00 pm`, `11:59pm`, `noon` (12:00) and `midnight` (23:59). Morning and night give no time.
- **Known ambiguity:** a bare weekday that falls on the same weekday as S resolves to S itself. For example, "by Friday" in an email sent on a Friday means that same Friday.
- **"Before Tuesday"** is stored as Tuesday. The phrase keeps the word "before".
- **A phrase no rule matches** is kept with `date: null` and `time: null`. It shows up in search and in the index, but never in `due`.

## Test fixtures

`bank/eval/fixtures/`:

- **`o01`–`o10`:** the 10 existing emails, unchanged. They are now scored on resolved dates, folder and course.
- **`n01`–`n06`:** six new synthetic fixtures. I will write and commit them before the first model run, and never tune against them.

| Fixture | Tests |
|---|---|
| `n01_ta_explicit_date` | course email, "Nov 20 at 11:59pm" becomes 11-20 23:59, folder course |
| `n02_library_overdue` | automated notice, "return by 11/18", ask is to return, folder other |
| `n03_friend_tonight` | friend asks for notes "tonight", which is the sent date, folder person |
| `n04_prof_next_monday` | course code only in the body, "next Monday" quiz, folder course |
| `n05_course_page` | kind page, no sender, "PS5 due Nov 24" and "Final project due Dec 4", folder course |
| `n06_club_rsvp` | club email, "RSVP by end of day Wednesday", ask is to RSVP, folder other |
| `n07_scraped_friend` | scraped webmail with no header lines: "Name <addr>" line, "Nov 12, 2026, 3:14 PM (2 days ago)", "by Monday", folder person |
| `n08_scraped_mailroom` | scraped webmail, automated `mailservices-noreply` sender, "Tue, Nov 10, 2026, 9:02 AM", "by Nov 17", folder other |

An entry counts as right when all of these hold:

- `sender_address` and `sent_date` are exact.
- The ask keywords hit, or the ask is null when none is expected.
- The set of deadline dates is exact.
- `folder` and `course` are exact.

The tests need no model server. They cover every row of the phrasing table, the folder rule, duplicates, search ranking and `due` ranges.

## Done-when

- Ingesting all 18 fixtures into a temp bank puts the right entries in the right folders, and the index is current.
- `due("2026-11-16", "2026-11-20")` returns the right rows with the server stopped.
- `python -m unittest discover bank/tests` passes.
- On 4B, each of 3 runs gets at least 9 of 10 originals and at least 5 of 6 of n01–n06 right, and n07–n08 scored the same way and reported. I will report failures as they are and not loosen the scoring.
- `docs/context-store.md` has the numbers per run, the final prompt and the entry format.
- Everything is committed and pushed as `context-store`. I will check that the `:8080` server is up and reuse it, start one only if none is running, and tell worker 4 when I do.

## Open questions

1. Should the `From:`/`Date:` lines win over what the model says? Default: yes, and I will report the model's own accuracy too.
2. Should "before Tuesday" be stored as Tuesday rather than Monday? Default: Tuesday, with the phrase kept.
3. Should a page be dated by the ingest date? Default: yes, unless its text has a `Date:` line.
4. Is answering questions with Bonsai out of my lane, with the bank only providing the index and the readers? Default: yes, out of my lane.
