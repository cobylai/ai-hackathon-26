# Web

## For

A question the bank can't answer, while the Mac is online. "When did the Berlin Wall fall?", "Who wrote Frankenstein?"

## Triggers

None. The bank route hands over to this one when it falls short.

## Steps

1. Check the network: one connect to www.bing.com:443, 2 seconds.
2. Offline: say `offline` and stop.
3. Online: search and read pages (`gather`: the partner's search, then Bing; at most 3 searches and 60 seconds). Each page goes to the same judge as the bank route, with the quote check.
4. Nothing found: say gather's message, or `not_found`.
5. Found: answer, the quoted line (if the answer doesn't already contain it), the page's url as the source, and file the answer in the bank under that url so it can be asked offline later. Then say `saved`, `already_saved` or `save_failed`.

## May look

The web, through the hidden browser. Only after the bank fell short.

## May not look

The model's own knowledge. Person and due questions never come here.

## Wording

- saved: Saved to your notes.
- already_saved: Already in your notes.
- save_failed: (Could not save the page: {error}.)

The answer ends with "Source: <url>" (RULES.md). What gets filed is the question, the answer and the quoted line, with "question answer" as the subject (code, `reason/answer.py` `saved_page`).

## Not found

- offline: I don't have that saved, and the Mac is offline, so I can't look it up.
- not_found: I couldn't find that on the web.

## Never

- Never answer without a quote found on the page.
- Never file a page that didn't answer.

## Prompt

The judge prompts are the bank route's (`bank.md`). The rephrase prompt lives in `sufficiency/prompts.py`; this copy is checked against it by a test.

### rephrase_system
```text
You write short web search queries.
```

## Examples

The checker runs with the network blocked, so web questions get the offline reply.

| question | route | answer contains |
|---|---|---|
| What is the capital of Peru? | offline | the Mac is offline |
