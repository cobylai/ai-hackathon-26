# Reasoning layer

`reason/` takes a question and returns an answer. It checks the bank first and uses the browser only when the bank falls short. Code picks the route; the model never chooses a tool. Every model call goes to local Bonsai 2 4B. Plan: `docs/plans/reasoning-layer.md`.

## Use

```python
from reason import answer
a = answer("what is due Monday", today=None)   # today: date, "YYYY-MM-DD" or None (= date.today())
a.text      # the answer; ends with its source
a.route     # "due" | "person" | "bank" | "web" | "offline" | "not_found"
a.sources   # bank entry paths, or [url] on the web route
a.seconds
```

Typed chat loop (a thin wrapper, so voice can call `answer()` the same way):

```bash
MUSE_BANK_DIR=~/muse-bank uv run python -m reason --today 2026-11-14
```

## Routes, checked in this order

1. **Due.** The question contains the word `due`, `deadline` or `deadlines`. Code works out the date range, calls `bank.due`, and writes the list itself, with no model call. Each line carries its own source (sender, sent date).

   | Phrase | Range |
   |---|---|
   | today, tonight | today |
   | tomorrow | today + 1 |
   | Monday … Sunday | the next such day, or today if today is that day |
   | next Friday (etc.) | that day in next week (Mon–Sun) |
   | this week | today to Sunday |
   | this weekend | Saturday (or today, if later) to Sunday |
   | next week | next Monday to next Sunday |
   | Nov 20, November 20th, 11/20, 2026-11-20, on the 20th | that day (`bank.dates.resolve_date`) |
   | nothing | today to today + 6 ("in the next 7 days") |

2. **Person.** A question word matches a sender's name word. Name words come from every email entry's `sender_name` and the part of the address before `@`. They are 3+ letters, titles (Prof, Dr…) are dropped, and senders with an automated word (Office, Club, Library, Dining…) are skipped entirely.
   - If the question has a capitalized word other than its first word, only capitalized words are tried ("what did Will say" → Will).
   - Otherwise every word is tried except a stoplist of common words that are also names: "will it rain" doesn't match Will, but "what did emily ask" matches Emily.
   - `bank.by_person` returns the entries, and the newest 8 go to Bonsai with the question. The model returns `{"answer", "used": [numbers]}` at temperature 0.2, and the used entries become the sources (all 8 if `used` is bad).

3. **Everything else.**
   - `bank.search(question, limit=5)`. The entries are written as numbered note blocks and passed to `sufficiency.judge` once. If it's enough, the route is `bank`, and the source is the block that holds the judge's quote.
   - If it's not enough and the network is up (one TCP connect to www.bing.com:443, 2 s timeout), the route is `web`. That runs `gather(question, sufficiency.websearch.search, harness.search.tools.open_page, max_seconds=60)`. websearch tries the partner's `engine.search` first, then Bing. On success the answer is filed with `bank.ingest(..., source=url, kind="page")`. harness is imported only here, so offline answers never load Playwright.
   - If it's not enough and the network is down, the route is `offline`: "I don't have that saved, and the Mac is offline, so I can't look it up."
   - If gather finds nothing, the route is `not_found`, with gather's message.

**What the web route files (a change from the plan).** The plan said to ingest the page itself. But the bank keeps a one or two sentence summary, not the page. cornell.edu's summary came out as a news item, so asking the same question offline got the offline message. The route now files a short text with the question, the answer and the quoted line, with `subject="<question> <answer>"`. ingest's `subject=` keyword wins over the model. With that change, "When did the Berlin Wall fall?" answered from the bank offline (below). The source is still the page url.

## Live results (2026-11-14, Bonsai 2 4B on :8080 shared with worker 8, `--today 2026-11-14` a Saturday)

Bank: the 16 `bank/eval/fixtures` ingested into a scratch `MUSE_BANK_DIR` outside the repo (`python -m reason.live_check load`, 45.8 s). Offline runs use `python -m reason.live_check offline`, which blocks `socket.connect` for everything except localhost in that process.

| Network | Question | Route | Answer (abridged) | Seconds |
|---|---|---|---|---|
| blocked | what is due Monday | due | Due Mon Nov 16: 11:59pm submit final notebook + reflection (Prof. Daniel Reyes, Nov 12); bring a calculator (Prof. Lena Ortiz, Nov 11) | 0.00 |
| blocked | what's due next week | due | Due next week (Nov 16 to Nov 22): 8 rows, from the Reyes notebook on Mon Nov 16 to Wei Zhang's HW 9 on Fri Nov 20 11:59pm | 0.00 |
| blocked | what did Marcus ask me | person | Push your part of the circuit analysis to the shared doc; also scope screenshots from Tuesday. Source: Marcus Bell, Nov 12 | 0.98 |
| blocked | which sections does the MATH 2940 homework cover | bank | sections 5.1 to 5.3. Source: Wei Zhang, Nov 14 | 1.20 |
| blocked | what is the capital of Peru | offline | I don't have that saved, and the Mac is offline, so I can't look it up. | 0.02 |
| blocked | is the gym open on Thanksgiving | offline | (same message) | 0.01 |
| online | When did the Berlin Wall fall? | web | 9 November 1989, "Date \| 9 November 1989". Source: en.m.wikipedia.org/wiki/Fall_of_the_Berlin_Wall. Saved to your notes. | 10.76 |
| blocked | When did the Berlin Wall fall? (asked again) | bank | 9 November 1989. Source: en.m.wikipedia.org/wiki/Fall_of_the_Berlin_Wall | 1.23 |
| online | Who wrote the novel Frankenstein? (after merging integration 4af9140, `websearch.search`) | web | Mary Shelley, "Author \| Mary Shelley". Source: en.m.wikipedia.org/wiki/Frankenstein. Saved to your notes. | 9.87 |
| blocked | Who wrote the novel Frankenstein? (asked again) | bank | (answered from the bank) | 0.72 |
| — | `python -m reason`: what did aisha ask me to do | person | Aisha asked you to take the slides for the group project. Source: Aisha Rahman, Nov 13 | 1.0 |

The web seconds include gather (the partner's engine.search and open_page) and the ingest call.

**A wrong web answer, kept on record.** Before the filing change, "What year was Cornell University founded?" took the web route in 54.5 s. It answered **1868**, quoting an Ezra Cornell line dated 1868 on cornell.edu. Cornell was founded in 1865 and opened in 1868. That is the judge accepting a related year. I did no tuning on sufficiency/.

## Tests (no model server, no network)

```bash
uv run python -m unittest discover -s reason/tests -t .
```

18 pass. They cover:
- every row of the date table, plus Sunday "this weekend"
- the due words
- person matching: capitals, lowercase, `'s`, "will it rain" and "Will it rain in Ithaca?" against a sender named Will, titles and automated senders
- the due answer for one day, a week, and nothing due, with a model call failing the test
- the person route with only that person's entries in the prompt, and a bad `used`
- the bank route (and no network check when it answers)
- the offline message, with judge skipped when search finds nothing
- the web route filing the answer under the url, and not_found
- a child process checking that the due route imports neither harness nor playwright

## Not run / known gaps

- **Wi-Fi was not actually turned off.** The stand-in is the per-process `socket.connect` block, with Bonsai on localhost. The partner's browser was not started in the offline runs.
- **Real email:** only the synthetic fixtures were used; no Gmail sync went into this bank.
- **Few web questions:** Berlin (harness engine.search, ed93e1c), Frankenstein (sufficiency.websearch, 4af9140), and Cornell before the filing change. gather's pointer-page weak spot applies here unchanged.
- **The online check is DNS plus one connect to www.bing.com.** A captive portal would count as online, and then gather fails into `not_found`, not `offline`.
- **Person route:**
  - a sender whose only name word is in the stoplist (a lone "Will", all lowercase) is never matched
  - with two senders who share a first name, `by_person` returns both
- **Due route:** a question that mentions "due" but is really about something else ("why was the quiz moved, it was due Friday") takes the due route.
- **Duplicate rows:** an entry with two deadlines in range is listed twice with the same ask, as Aisha's was.
