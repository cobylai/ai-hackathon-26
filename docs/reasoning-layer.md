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
a.rows      # what a due / calendar / person answer listed, for follow-ups

from reason.session import Session
s = Session()                                  # one conversation, in memory only
answer("what's due tomorrow", session=s)
answer("and Friday?", session=s)               # due again, for Friday
```

Both front ends are thin wrappers over `answer()`; neither adds logic.

**Chat loop** (terminal):

```bash
FLUX_BANK_DIR=~/flux-demo-bank uv run python -m reason [--today YYYY-MM-DD] [--no-voice]
```

Type a question and press Enter. Press Enter on an empty line to talk, and Enter again to stop; the words heard are printed as `you (spoken)>` and answered like typed text. `quit` or Ctrl-D exits. `--speak` reads each answer aloud with the Mac's `say` (no Source line); talking or a new question stops it.

**Chat window** (one local page, standard library only, nothing loaded from the internet, so it opens with Wi-Fi off):

```bash
FLUX_BANK_DIR=~/flux-demo-bank uv run python -m reason.web [--today YYYY-MM-DD] [--port 8765] [--no-voice] [--no-open]
```

- The conversation, with each answer's `Source:` line in grey under it and the route and seconds under that.
- A type box with Send (Enter also sends).
- "Hold to talk": hold the button, speak, let go. The heard text appears with a 🎤 and is answered.
- A label like "offline · 20 items in bank". Click it for a read-only list of the bank, newest first: date, sender, subject, summary, deadline and ask (`GET /bank`).
- The server is single-threaded on purpose, because the web route drives one Playwright browser.
- Endpoints: `GET /`, `GET /status`, `GET /bank`, `POST /ask`, `POST /listen/start`, `POST /listen/stop`.

**Voice** (`reason/speech.py`) starts `voice/listen.py`'s `Voice` once at launch.
- Needs `ARGMAX_API_KEY` in the same shell, and a built `argmax-voice`. `FLUX_VOICE_BIN` points at a binary built in another checkout; the default is `voice/swift/.build/release/argmax-voice`.
- If voice can't start (no key, no binary, mic denied), both front ends say "Voice is unavailable (<reason>)" and typing still works. The window's button stays disabled, and its tooltip gives the reason.
- **Use easy names when speaking.** The person route needs the spoken name to come back spelled like the sender's name. Whisper heard "Coby" as "Kobe". Names that worked in the demo checks: Felix, Hugo, Ivy, Jonah, Greta, Omar, Lena, Milo. Avoid Nina (two senders), Tess, Kiri and Rafe.

## Playbooks (how each route answers, in markdown)

`playbooks/` holds one file per route plus `RULES.md` (the rules for every route, the shared wording, the file layout and the keep rule). Each file has the same sections: For, Triggers, Steps, May look, May not look, Wording, Not found, Never, Prompt, Examples.

- Code reads the Triggers patterns, the Wording and Not found lines, and the Prompt blocks (`reason/playbook.py`). Edit a file and restart Flux to change how a route answers. Code keeps no second copy of the wording.
- The steps' order is code. `STEPS` in `reason/answer.py` must match each file's numbered steps (`reason/tests/test_playbooks.py`).
- The bank/web judge and rephrase prompts live in `sufficiency/prompts.py`; `bank.md` and `web.md` hold copies, and a test fails if they drift.
- Checker: `FLUX_BANK_DIR=~/flux-demo-check-bank uv run python -m reason.playbook_check` runs every Examples table on a temporary copy of the bank with the network blocked. 27/27 on 2026-11-15 (14 when the playbooks landed, 13 more with remember and people). Brief M's check gave the same output line for line before and after the move (37/38). 69/69 after follow-ups (`followup.md` adds 19, run in order as one conversation; 50 before).

## Routes, checked in this order

-2. **Follow-up** (`reason/session.py`, `playbooks/followup.md`), only when the front end passes a `Session` (the chat loop and the window do; `playbook_check` gives each playbook file one) and no discovery question or action waits for a yes. Code only, no model call.
   - "and tomorrow?", "what about Friday?", "and next week?" (anything the date table below names) after a due or calendar answer: that route again for the new range.
   - "and <name>?" (one to three name-like words) after a person or "who is" answer: the last question with the name swapped. An unknown name gets "I have nothing from <name>."
   - "the first one" … "the tenth one", "the last one", "number 2", "that one": the row, its summary and source. "who sent that?" and "when is it due?" (or "… the second one") answer from the row. With no ordinal: the row picked last, else the only row, else "Which one?". These come back as route `followup` and keep the rows, so "the second one" still works next.
   - "open it" / "open the first one": `act.plan_row` holds an open (the row's link, or Calendar for an event) and asks for a yes; mail without a link says so.
   - Anything else is a new question, and an answer that listed nothing (bank, offline…) ends the rows, so "the first one" after it is a new question too.
   - The session: one per chat loop run, one open chat in the window server (it serves one person; the Mac app shows the same page). Nothing is written to the bank. Each chat is saved as a file outside the repo after every answer (`reason/chats.py`, brief T2), and the window lists them on the left; reopening one restores its follow-ups. It is built to be saved (thinker ruling, for brief T2): `id`, `title`, `started` and `turns` (question, route, text, sources, rows), with `to_dict()` / `Session.from_dict()`.
-1. **Discover** (`discover/`, `playbooks/discover.md`), checked before everything: "discover" starts a run of at most 10 yes/no questions about the user, built by code from the bank and Apple Calendar (Bonsai only guesses a relation). While a question is held, yes / no / skip / stop answer it; any other input ends the run. Only a yes writes (me store or person page). "What have you learned" and "unlearn N" review. The window has a Discover button and Yes / No / Skip / Stop buttons.
0. **Remember, forget, about_me, people** (`reason/me.py`, `playbooks/remember.md`, `playbooks/people.md`). Code only, no model call, checked before due, so "remember the essay is due Monday" becomes a note.
   - **remember:** the sentence starts with "remember (that)", "note that" or "don't forget (that)". A leading dash from voice, "Flux," and "please" are dropped first. A sentence ending in "?" doesn't count, and neither does "do you remember …". The rest is filed in the user's words (`bank.remember`: kind "me", folder `me/`).
   - **forget:** starts with "forget (that/about)". It deletes the note sharing the most words; "forget that" or "forget it" alone deletes the newest. On a tie it deletes nothing and lists the tied notes; with no shared word it says "I don't have a note like that."
   - **about_me:** "what do you know/remember about me", "what have you remembered". It lists the notes, newest first, with "Source: your notes".
   - **people:** starts with "who is", "who's" or "what do you know about", and every remaining word is a sender's name word or a person page's name word. It shows the person page (`bank.people`: relation, facts) and their newest 5 emails. Other names fall through to the routes below ("who is waiting on me" → bank). "Tell me about X" and "what did X say" stay on the person route.
   - Other questions find notes through the bank route ("When is my lab?" → "Tuesdays at 2. Source: your note, Nov 15").
1. **Due.** The question contains the word `due`, `deadline` or `deadlines`. Code works out the date range, calls `bank.due`, and writes the list itself, with no model call. Each line carries its own source (sender, sent date), and the entry's one-line summary goes under it, indented, so details like a bill amount come along without a model call (thinker ruling).

   | Phrase | Range |
   |---|---|
   | today, tonight | today |
   | tomorrow | today + 1 |
   | Monday … Sunday | the next such day, or today if today is that day |
   | next Friday (etc.) | that day in next week (Mon–Sun) |
   | this week | today to Sunday; on Sat/Sun, today to the coming Sunday (thinker ruling) |
   | this weekend | Saturday (or today, if later) to Sunday |
   | next week | next Monday to next Sunday |
   | Nov 20, November 20th, 11/20, 2026-11-20, on the 20th | that day (`bank.dates.resolve_date`) |
   | nothing | today to today + 6 ("in the next 7 days") |

2. **Person.** A question word matches a sender's name word. Name words come from every email entry's `sender_name` and the part of the address before `@`. They are 3+ letters, titles (Prof, Dr…) are dropped, and senders with an automated word (Office, Club, Library, Dining…) are skipped entirely.
   - If the question has a capitalized word other than its first word, only capitalized words are tried ("what did Will say" → Will).
   - Otherwise every word is tried except a stoplist of common words that are also names: "will it rain" doesn't match Will, but "what did emily ask" matches Emily.
   - **Ask questions** (ask / want / need in the question): code lists the sender's newest 8 entries as `date  subject: ask`, or `no ask. <summary>` when an entry has none. No model call (thinker ruling, brief P: the model misread the notes on 4 of 14). With a full name ("Nina Valdez"), only senders matching every name word are listed.
   - **Other person questions** ("what did Emily say about the lab"): `bank.by_person` returns the entries, and the newest 8 go to Bonsai with the question. The model returns `{"answer", "used": [numbers]}` at temperature 0.2, and the used entries become the sources (all 8 if `used` is bad).

2a. **Everyone, and misheard names** (from Antranig's test report, problem 8: "What did everyone ask me?" and a misheard "Elena asked me" went to the web).
   - "everyone / everybody / anyone / anybody / people" with an ask/say/send/want/need verb lists every sender's open asks (deadline today or later, or none), newest first, at most 12, each with the sender. Code only.
   - With an ask/say/send/want/need verb, a word of 4+ letters that is no sender but close to one counts as that sender: one is the other with up to 2 extra letters at the start or end ("elena" ~ "lena"), or one letter off when both have 5+ letters ("Tim" is never guessed as "Tom"). Close to one sender: that sender's asks, under `(I heard "Elena" and took it as Lena Marsh.)`. Close to two or more: `I heard "X". Did you mean A or B?`.

2b. **Unknown person (no-match guard).** A question shaped "what did <name> ask / say / send / want" whose name is no sender in the bank answers "I have nothing from <name>." and stops, never reaching search (thinker ruling: a wrong answer about a person is worse than none). Pronouns ("what did you send") don't count.

2c. **Chat** (`reason/chat.py`, `playbooks/chat.md`). A greeting, mic check or thanks, with almost nothing else said (at most 2 words left after the chat and filler phrases, and no question word), gets a fixed reply: "I can hear you. …", "Hi. …" or "You're welcome." So "Hey, can you hear me okay?" no longer runs 3 web searches. "Hey, what's due tomorrow?" is still a due question.

-0.5. **Compose** (`reason/compose.py`, `playbooks/compose.md`, brief W), checked just before act. "Draft a reply to Greta", "write a reply to Milo saying yes", "write an email (to Felix) (about the cabin)" give a draft box: editable To, Subject and body, then **Open in Mail**, which hands a plain-text `mailto:` to macOS (`open`), so nothing is sent and it works offline. "… in Gmail" stays with act.
   - A reply goes to the person's newest meeting ask, else their newest email with an ask. A meeting ask with a readable day and time uses a code template: yes when free, or no naming the clash with the next free half hour that day. Other bodies come from Bonsai, from that email's summary and ask plus what you said.
   - A new email is written only from bank entries on the topic (that person's first), their person page and your notes. The box lists the entries used.
   - It asks at most two questions: "Who is this to?" (no name, or an unknown one), "Which Nina? …" and "I don't have anything about <topic>. Tell me a little more: what should it say?". An unknown address leaves To empty.
   - It's signed with your first name from a "my name is …" note, and without a sign-off when there's no such note.

**Suggestions** (`reason/suggest.py`, `playbooks/suggest.md`, brief W). After a due, catchup, person, bank or followup answer, code offers at most two next steps from that answer's own entries. No model call.
   - A meeting ask whose day and time were read, with that day of Apple Calendar read: "You're free Thursday, Nov 19 at 7pm. Draft a yes to Milo?" or "You have Lab then (…). Draft a reply proposing another time?".
   - An email with an ask: "Draft a reply to Ivy: Garden plot". If the time or the calendar can't be read, this is what shows, and free/busy isn't mentioned.
   - A Canvas item: "Open the assignment page: Homework 9".
   - A free meeting also gets "Add "Band practice Thursday" to your calendar: Thu Nov 19 7pm". On due and catch-me-up answers, an upcoming item also gets "Remind me: Submit reading quiz (Mon Nov 16 7am)". A click runs worker 14's `computer.add_event` / `add_reminder` (block list, log), which `computer.event_for` / `reminder_for` work out from the stored date.
   - Each entry's suggestions come together, best first, so "What's due tomorrow?" offers the soonest item's page and reminder.
   - `Answer.suggestions`; nothing runs until a click. A dismissed, drafted or opened one doesn't come back in that chat. The chat loop prints them as lines.

3. **Everything else.**
   - **Web gate (RULES.md rule 9).** If the bank can't answer, only a clear factual question goes to the web: it starts with a question word (after "Flux," or "please") or ends with "?", and has no "my"/"mine". Otherwise it answers `not_found` with "I don't have that in your notes or mail." (a "my" question) or "I'm not sure what you're asking, so I didn't look it up." Nothing is sent to a search engine.
   - `bank.search(question, limit=5)`. The entries are written as numbered note blocks and passed to `sufficiency.judge` once. If it's enough, the route is `bank`, and the source is the block that holds the judge's quote.
   - If it's not enough and the network is up (one TCP connect to www.bing.com:443, 2 s timeout), the route is `web`. That runs `gather(question, sufficiency.websearch.search, harness.search.tools.open_page, max_seconds=60)`. websearch tries the partner's `engine.search` first, then Bing. On success the answer is filed with `bank.ingest(..., source=url, kind="page")`. harness is imported only here, so offline answers never load Playwright.
   - If it's not enough and the network is down, the route is `offline`: "I don't have that saved, and the Mac is offline, so I can't look it up."
   - If gather finds nothing, the route is `not_found`, with gather's message.

**What the web route files (a change from the plan).** The plan said to ingest the page itself. But the bank keeps a one or two sentence summary, not the page. cornell.edu's summary came out as a news item, so asking the same question offline got the offline message. The route now files a short text with the question, the answer and the quoted line, with `subject="<question> <answer>"`. ingest's `subject=` keyword wins over the model. With that change, "When did the Berlin Wall fall?" answered from the bank offline (below). The source is still the page url.

## Scores on the many-sender check (`scripts/demo/make_test_mail.py`)

20 made-up emails from 13 senders, scored offline (`check --offline`, network blocked except localhost) against what the generator knows is true.

| Date (`--today`) | Bank | Right | Person | No-match | Due | Bank route |
|---|---|---|---|---|---|---|
| Sat 2026-11-14, before brief P | scratch, `bank.load` | 32/37 | 10/14 | 2/2 | 15/15 | 5/6 |
| Sat 2026-11-14, after brief P (code-listed asks) | scratch, `bank.load` | **36/37** | 14/14 | 2/2 | 15/15 | 5/6 |
| Sun 2026-11-15 | demo bank (`~/flux-demo-bank`, via Gmail pages) | **37/38** | 14/14 | 2/2 | 16/16 | 5/6 |

The one miss in every run: "What are the team name options for the hackathon?" gets the offline message, because the bank's summary of that email dropped the options. That's logged, with no fix (thinker ruling). How to build the demo bank: `docs/integration.md` ("Demo bank") and `docs/PARTNER-TESTING.md`.

## Voice runs (Coby at the mic, network denied with `sandbox-exec`, localhost allowed, `~/flux-bank`)

| Front end | Spoken | Heard | Answer | Seconds |
|---|---|---|---|---|
| chat loop | What's due this week? | exactly | due list: essay Mon 11:59pm, phone bill Thu ($42.18), housing Fri noon | 0.0 |
| window, hold to talk | What's due this week? | exactly | same 3 rows | 0.0 |
| window, hold to talk | What did Coby ask me? | "- What did Kobe ask me?" | "I have nothing from Kobe." (the guard is correct for what was heard) | 0.0 |

Stop-to-text for the voice program alone is about 1.1–1.25 s (`docs/voice-input.md`).

## Live results (2026-11-14, Bonsai 2 4B on :8080 shared with worker 8, `--today 2026-11-14` a Saturday)

Bank: the 16 `bank/eval/fixtures` ingested into a scratch `FLUX_BANK_DIR` outside the repo (`python -m reason.live_check load`, 45.8 s). Offline runs use `python -m reason.live_check offline`, which blocks `socket.connect` for everything except localhost in that process.

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

110 pass on 2026-11-15 (`test_session.py` adds 15: date, name and row follow-ups after due, calendar and person questions, "open it" through act, unrelated questions not taken as follow-ups, nothing written, `say` start/stop and the Source line dropped, the window's Speak switch and stop on talk, one session for the window, the chat loop's `--speak`). Earlier count:

63 pass (`test_me.py` adds the remember, forget, about_me and people routes with any model call failing the test; bank/tests/test_me.py covers `bank.remember/notes/forget` and `bank.people`; `test_playbooks.py` adds the playbook checks: sections, step counts, every wording key code uses and its placeholders, the sufficiency prompt copies). They cover:
- every row of the date table, plus Sunday "this weekend"
- the due words
- person matching: capitals, lowercase, `'s`, "will it rain" and "Will it rain in Ithaca?" against a sender named Will, titles and automated senders
- the due answer for one day, a week, and nothing due, with a model call failing the test
- "this week" on a Saturday and a Sunday (runs to the coming Sunday)
- due rows carrying the entry summary
- ask questions listed by code with no model call, "no ask" plus the summary, and full names narrowing two Ninas
- the no-match guard ("What did Priya ask me?" → "I have nothing from Priya.", no search or model call)
- other person questions with only that person's entries in the prompt, and a bad `used`
- the bank route (and no network check when it answers)
- the offline message, with judge skipped when search finds nothing
- the web route filing the answer under the url, and not_found
- a child process checking that the due route imports neither harness nor playwright
- the window: the page loads nothing remote, `/status`, `/ask`, `/bank` (newest first), and `/listen/start` without voice
- hold to talk with a fake voice, and the chat loop's spoken and voice-unavailable paths

## Not run / known gaps

- **Wi-Fi was not actually turned off.** The stand-ins are the per-process `socket.connect` block (checks) and `sandbox-exec` with only localhost allowed (voice runs). macOS still saw a network.
- **Real email:** answers were checked on made-up mail only: the bank fixtures, the many-sender check, and the demo emails sent through Gmail. No real inbox.
- **Names by voice:** Whisper can misspell a name ("Coby" → "Kobe"). Then the guard answers "I have nothing from <name>", which is safe but not the answer. Use the easy names above, and test each once by voice before recording.
- **Bank summaries lose details:** the hackathon team-name options and the housing form's contents aren't in the summaries, so questions about them miss.
- **Due questions always get the dated list,** even "how much is my phone bill and when is it due?". The amount shows only when it's in the summary (thinker ruling: keep the list).
- **Few web questions:** Berlin (harness engine.search, ed93e1c), Frankenstein (sufficiency.websearch, 4af9140), and Cornell before the filing change. gather's pointer-page weak spot applies here unchanged.
- **The online check is DNS plus one connect to www.bing.com.** A captive portal would count as online, and then gather fails into `not_found`, not `offline`.
- **Person route:**
  - a sender whose only name word is in the stoplist (a lone "Will", all lowercase) is never matched
  - with two senders who share a first name, a first-name question lists both; a full name narrows it
  - names come from the From line, not the sign-off, so mail sent from one account files every message under that account's name
  - "who is waiting on me" has no route (dropped from the video)
- **Due route:** a question that mentions "due" but is really about something else ("why was the quiz moved, it was due Friday") takes the due route.
- **Duplicate rows:** an entry with two deadlines in range is listed twice with the same ask, as Aisha's was.
