# Flux: smarter routing, a proposal (Antranig's testing, 2026-11-15)

Written after the full test pass (`docs/test-results/antranig-full.md`). Antranig's
point: we keep patching one wrong answer at a time. This says why, and what to
build instead. Nothing here is built yet except the mic fix at the end.

## What the test showed

Every bad answer in the test came from the same place: a question matched no
rule, so it fell through to the **web**.

| Asked | What happened |
|---|---|
| "Who are you" | Web search, 60 s, an answer about the band The Who, saved to notes |
| "what am I?" | Web search, a riddle app |
| "what does this week look like?" | Web search, the TV show *Mock the Week*, 38.7 s |
| "and the day after?" in a fresh chat | Web search (nothing to follow up on) |
| Junk saved to the bank | Later broke real answers ("my cabin share" → not found) |

Each was fixed by adding another regex. That is the "pinprick" problem.

## Why it keeps happening

`reason/answer.py` is one long **first-match-wins chain** of regex triggers
(`discover`, `compose`, `act`, `me`, `catchup`, `due`, `calendar`, `person`,
`everyone`, `chat`, then bank, then web). Four weaknesses:

1. **Closed list of phrasings.** Anyone who words it differently misses every
   rule. Real users and speech-to-text do this constantly.
2. **Order is the logic.** Moving one rule can break another. Nobody can say
   what a new question will hit.
3. **The default is the worst route.** Unmatched means web: slow (10 to 60 s),
   off-topic, and it saves what it finds. An unknown question should never
   quietly leave the Mac.
4. **The model is only used at the end**, to judge bank hits. It is never asked
   "what is this person trying to do?", which is the thing it could help with.

Bonsai 4B is small, so we should not ask it to write or reason freely. It is
good enough to **choose from a short list**, and that is the job here.

## Proposal: classify first, then run code

Keep all the existing handlers (due, calendar, person, bank, act...). They are
good, fast and tested. Change only **how a question picks one**.

```
question
  1. context check (code): is there a held yes/no, a pending draft, a last answer to follow?
  2. fast path (code): the current regex triggers. A confident match runs now, as today.
  3. classifier (Bonsai): only when 2 doesn't match. Picks ONE label from the
     closed list, with a confidence.
  4. confidence gate:
       high    -> run that route
       medium  -> ask one short question: "Did you mean your calendar or the web?"
       low     -> "I'm not sure what you want. I can check your mail, calendar..."
  5. web is never the fallback. It runs only when the user asks for it
     ("search for...", "look up...", "online") or says yes to
     "I don't have that saved. Search the web?"
```

### How the classifier works (small model friendly)

- **One short prompt**: the label list with a one-line meaning each, 3 to 5
  examples per label (we already have these in `playbooks/*.md`), then the
  question. Generated from the playbooks, so there is still one place to edit.
- **Answer is a label, not prose.** Read the next-token **probabilities** over
  the label names (or constrain output to the list) and take the top one. The
  gap between first and second place is the confidence. No parsing, no
  rambling, about 0.3 s on the Pro.
- **Slots by code**, not by the model: names, dates and "which assignment" are
  pulled by the existing functions (`route.person_in`, `bank.dates`).
- **Include light context**: the last route and whether a list is on screen, so
  "and tomorrow?" and "open it" resolve without a regex per phrase.

### Safety rules that stay in code

- Anything that acts (draft, add to calendar, reminder, open a page) still asks
  for a yes and still never sends. The classifier can only *propose* an action.
- Sender names must exist in the bank. A name that doesn't gets "I have nothing
  from X", as now.
- Web answers are shown but **not saved** unless the user says "save that".

## How to know it is better: a test set, not more regexes

Build `reason/tests/routing_eval.jsonl`: about 300 labeled questions.

- Seed: every example row in `playbooks/*.md` (about 600 already).
- Add every failure from this test pass (the table above, plus the 22 findings).
- Add paraphrases, typos, and **speech-to-text mistakes** (Whisper hears
  "Coby" as "Kobe"; "Elena" for "Lena").
- Add "should NOT go to the web" cases: questions about you, Flux, your
  schedule, anything personal.

Then `python -m reason.route_eval` prints accuracy per route and the confusion
list. Compare **regex only** against **regex + classifier**. Ship the
classifier only if it wins, and watch the "wrongly sent to web" count: the
target is zero.

## Suggested order for Coby

1. Stop the bleeding (small): web answers not saved without a yes; unmatched
   question asks instead of searching ("Search the web for that?").
2. Build the eval set and the scorer (no behavior change; gives a baseline).
3. Add the classifier behind the confidence gate; compare on the eval set.
4. Retire regexes the classifier handles at least as well; keep the
   safety ones (act, names, dates).

## Also from this round: the server and the window

Two things Antranig hit that are not routing:

- **No queue.** `python -m reason.web` is a single-threaded `HTTPServer`, so one
  slow web search blocks everything, including typing a new question.
  Use `ThreadingHTTPServer` and a per-chat queue; show "queued" in the window.
- **No window that stays.** The Fn-Space panel disappears in Window Manager.
  Add an optional normal, resizable window (menu: "Keep Flux in a window"),
  while keeping the Spotlight-style panel as the default.

## Mic: "recording too short" (fixed on this branch)

Clicking the mic button sent start on press and stop on release. A click lasts
about 0.1 s, so the recorder had under the 0.25 s minimum and failed with
"recording too short". Fix in `reason/web.py`: **hold** still talks and sends on
release; a **quick click** (under 0.4 s) now keeps listening, and the next
click sends. The error text also now says what to do. The Fn-Space voice path
through the Mac app is unchanged and still needs a test.
