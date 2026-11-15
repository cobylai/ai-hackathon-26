# Setup

## For

Get me ready to work: "set me up for the lab report", "let's work on Homework 9", "get me ready for the essay". Flux finds the matching coursework or page, its related mail and any note, lists what it will open, and opens them together on a yes.

## Triggers

- setup: `^(?:please\s+)?(?:set me up for|get me (?:set up|ready) for|let'?s work on|let us work on|i want to work on|help me (?:start|work on))\s+(.+)$`

Tried on the question with its end punctuation removed. Group 1 is the thing.

## Steps

1. Take the thing's words, leaving out filler ("the", "my", "this"…). With no words left, say `what_thing`.
2. Search the bank for them. Prefer entries whose subject, summary, ask or course has every word.
3. The page is the matching entry with a web or file link. If several match and none has every word in its subject, say `which_one` with up to 3 subjects and stop.
4. Add up to 2 matching emails and up to 2 me-store notes. With nothing at all, say `nothing_found` and stop.
5. Show the list (`preview_head`, then one line per item) and wait for a yes. On yes, open the page, open each email the way `open.md` does, and repeat the notes.

## May look

The bank (coursework, saved pages, email) and the me-store notes.

## May not look

The web. The model. Links written inside an email or page.

## Wording

- preview_head: To set you up for {target}, I'll open:
- item_page: - the page "{title}"
- item_mail: - the email from {who}, "{subject}"
- item_note: - your note: {note}
- note_line: Your note: {note}

## Not found

- what_thing: What should I set you up for?
- which_one: Which one do you mean: {options}?
- nothing_found: I don't have anything about {target}. What is it? Tell me the course or assignment name.

## Never

- Never guess when nothing matches or several things match: ask.
- Never open a link written inside an email or page; only the entries' own stored sources.
- Never open anything without a yes.

## Prompt

No model step.

## Examples

| question | route | answer contains |
|---|---|---|
| Set me up for Homework 9 | act | I'll open; the page "Homework 9" |
| no | act | Cancelled |
| Let's work on the zebra parade | act | I don't have anything about the zebra parade |
| set me up for the lab | act | Which one do you mean |
