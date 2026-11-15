# Bank

## For

Any other question the saved mail and pages might answer. "Where is the review session now?", "What book is on hold for me?", "How much is my share for the cabin?"

## Triggers

None. This is where every question goes that no route above it took.

## Steps

1. Search the bank for the question's words (`bank.search`), keep the top 5.
2. If nothing comes back, go to the web route.
3. Give the 5 as numbered note blocks to the judge (one model call, prompt below). Code checks that the quote it returns is really in the notes.
4. If the quote checks out, answer with the judge's answer and the source of the note that holds the quote. If not, go to the web route.

## May look

The bank (mail and saved pages).

## May not look

The web (that is the web route's job), the model's own knowledge.

## Wording

The judge's short answer, then the source line from RULES.md ("Source: Felix Ambrose, Nov 15").

## Not found

Goes on to the web route, which says what happens next.

## Never

- Never answer when the quote isn't in the notes.
- Never answer from the model's own knowledge.

## Prompt

The judge prompt lives in `sufficiency/prompts.py` (a different folder, so it is not read from this file). It is copied here so you can read it; a test fails if this copy and the code drift apart. Changing it means editing `sufficiency/prompts.py`. Temperature 0.2, at most 300 tokens.

### judge_system
```text
You answer questions using only the web page you are given. You never use outside knowledge and never guess.
```

### judge_ask
```text
If the page answers the question, even in different words, give the answer and copy the exact line from the page that supports it. 
```

### judge_hint
```json
{"answer": "short answer, or null", "quote": "exact text copied from the page, or null"}
```

The full prompt is "Today is …", the question, the notes as the "PAGE", then judge_ask, then "If the page does not answer it, set answer and quote to null."

## Examples

| question | route | answer contains |
|---|---|---|
| Where is the review session now? | bank | barrow |
| What book is on hold for me at the library? | bank | tidal |
| How much is my share for the cabin trip? | bank | 35 |
