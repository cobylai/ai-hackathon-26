# Rules for every route

These apply to every kind of question. Each route's own playbook (`due.md`, `person.md`, …) says how that kind is handled. Code picks the route; the model never picks one.

## Rules

1. Answer only from what was found (bank, calendar, page). Never from the model's own memory.
2. Every answer names its source. No source, no answer.
3. If it is not found, say so plainly. Never guess.
4. Dates and sums are worked out in code, never by the model.
5. The model only fills narrow slots (a JSON reply, a quote, a short answer from given text), at low temperature.
6. Never act without showing what it will do and getting a yes. Draft, never send.
7. Only write something about the user to memory if the user said it or confirmed it.
8. A question that fits no playbook goes to the bank, then the web with the quote check, and otherwise gets "I don't know". No free answering.
9. The web is only for clear factual questions: ones that start with a question word or end with "?", and aren't about the user's own things. Chit-chat, misheard names and anything about "my" stay off the web (`chat.md`, `person.md`, `web.md`).

## Wording

Used by every route. Text in `{braces}` is filled in by code; keep the braces as they are.

- empty_question: Ask me something.
- source: Source: {labels}

## How a playbook file is laid out

Every route's file has these sections, with these headings, in this order:

- `## For`: what it is for, with example questions.
- `## Triggers`: lines `- key: `pattern``. Code reads them. Lines with the same key are alternatives; each matches as whole words, any case. A plain word is a pattern; `?` makes the letter before it optional, `|` means "or", `(?: … )` groups.
- `## Steps`: numbered lines, in the order code runs them. Code keeps the order; the number of steps here must match the code (a test checks it). Changing the steps means changing code.
- `## May look` and `## May not look`: where it may and may not look for the answer.
- `## Wording`: lines `- key: text`. Code reads them. This is how the answer is worded. Every answer ends with its source.
- `## Not found`: same format; what it says when it finds nothing.
- `## Never`: what it must never do.
- `## Prompt`: only for routes with a model step. A `### key` heading, then the exact prompt text in a fenced block. Code reads it.
- `## Examples`: a table `| question | route | answer contains |`. The checker runs them. `answer contains` is one or more pieces of text separated by `;`, all of which must be in the answer (any case); leave it empty to check only the route.

Edits take effect the next time Muse starts.

## Keep rule

Run the checker after editing any playbook or prompt:

```bash
MUSE_BANK_DIR=~/muse-demo-bank uv run python -m reason.playbook_check --today 2026-11-15
```

It runs every example on a temporary copy of the bank, with the network blocked, so it never changes the bank. Keep a change only if the checker still passes every example and brief M's score does not drop:

```bash
MUSE_BANK_DIR=~/muse-demo-bank uv run python scripts/make_test_mail.py check ~/muse-demo-threads --today 2026-11-15 --offline
```

(37/38 on 2026-11-15; the one miss is the hackathon team-name options.)
