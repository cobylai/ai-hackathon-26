# Reason over data

Route name: **reason**.

## For

Questions about the user's own things that no code route takes and that need judgement: "What should I work on first this week?", "Am I busy enough this week to skip the cabin trip?", "Which of my classes has the most due soon?", "What's my favorite color?" (nothing saved: says so).

## Triggers

- personal: `my|mine|myself`
- not_me: `(?:tell|show|give|help|let|teach|remind|ask) me|explain to me`
- domain: `deadlines?|due|emails?|mail|inbox|class(?:es)?|courses?|meetings?|exams?|homework|assignments?|quiz(?:zes)?|labs?|professor|prof|grades?|syllabus|schedule|calendar|lecture|section|office hours`
- domain: `owe|owed|owes|pay|paid|bills?|money|rent|share|deposit|fees?|(?:do|did|have|am|was) i (?:owe|need|have|pay|miss|forget|agree|promise|sign)`
- money: `owe|owed|owes|pay|paid|bills?|money|rent|share|deposit|fees?|cost|costs|spend|spent|how much`
- planning: `should i|shall i|what do i (?:do|need)|work on|prioriti[sz]e|priority|focus on|plan (?:my|for|out)|busy|free time|catch up on|fall behind|behind on`

About the user (checked in code before any model call) when any of these hold: `personal`, or "me" outside `not_me`; `domain` or `planning`; a word that is a sender's name; a course code (CS 3110); or a saved entry whose subject or sender has a 4+ letter word of the question (`bank.query.subject_hits`). A plain "I" alone doesn't count ("How do I cook rice?" is general).

## Steps

1. The question is about the user (Triggers) and no code route above took it.
2. Try the bank route first (`bank.md`: search, judge, quote check). If it answers, that's the answer, with its source.
3. Code gathers the facts: `bank.search` on the question (top 8); for a `money` question, also every entry that names an amount ($); for a `planning` or `domain` question, also the earliest 12 due items from today to 6 days out, and for a `planning` question the calendar for those days (skipped if Calendar takes more than 6 seconds to read). Each fact carries its dates as words and as YYYY-MM-DD.
4. Nothing found: say `nothing_saved` and stop. Never fill in from memory.
5. Bonsai, thinking on, gets the numbered facts and may compare, prioritise and advise, using only these facts for anything about the user. It replies with JSON: the answer and the fact numbers it used.
6. Code checks the answer: every date, weekday, time, amount, course code and mid-sentence capitalised name must be in the facts or the question. If one isn't, ask once more (thinking off) naming what wasn't found. If that fails too, don't show it: say `unchecked` and list the facts.
7. The answer ends with the source line for the entries it used (all of them if its list is bad), or `calendar_source` when only calendar facts were used.

## May look

The bank (mail, Canvas, notes, saved pages) and Apple Calendar, through code. The model's reasoning on top of those facts.

## May not look

The web. The model's own knowledge for anything about the user.

## Wording

- unchecked: I couldn't give an answer I could check against your saved items. Here's what I have:
- calendar_source: Source: Apple Calendar

The answer ends with the source line from RULES.md.

## Not found

- nothing_saved: I have nothing saved about that.

## Never

- Never state a date, time, amount or name that isn't in the facts.
- Never fill in a missing fact from the model's memory.
- Never show an answer that failed the check twice.

## Prompt

Thinking on for the first try, off for the retry. At most 1500 tokens (about 30 seconds).

### reason_system
```text
You are Flux, the user's assistant. You reason over facts from the user's own mail, coursework, notes and calendar. Every fact about the user must come from the numbered facts you are given: never add a date, time, amount, name or event that is not in them. You may compare, prioritise and give advice on top of those facts. If the facts don't answer the question, say what they do show and what is missing.
```

### reason_prompt
```text
Today is {today}.

QUESTION: {question}

FACTS FROM THE USER'S SAVED ITEMS (the "Due" facts are listed earliest first):
{facts}

Answer the question in a few sentences or a short list, using only these facts for anything about the user. To compare times, use the 24-hour times in brackets (12:00 is noon, 23:59 is just before midnight). Don't mention fact numbers in the answer text; put them in "used". Reply with only a JSON object: {{"answer": "your answer", "used": [numbers of the facts you used]}}
```

### retry
```text
Your answer mentioned {bad}, which are not in the facts. Answer again using only what the facts say. Reply with only the JSON object.
```

## Examples

| question | route | answer contains |
|---|---|---|
| What's my blood type? | reason | I have nothing saved about that. |
| What should I work on first this week? | reason | Source: |
| What did Priya ask me? | person | I have nothing from Priya. |
