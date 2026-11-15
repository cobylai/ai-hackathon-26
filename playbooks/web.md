# Web

## For

A question the bank can't answer, while the Mac is online. "When did the Berlin Wall fall?", "Who wrote Frankenstein?"

## Triggers

None to enter: the bank route hands over to this one when it falls short. Two patterns gate it (step 1):

- question: `what|what's|who|who's|whom|whose|when|where|which|why|how|is|are|was|were|do|does|did|can|could|will|would|should|has|have|tell me|define|explain`
- personal: `my|mine`

`question` counts only at the start (after "Muse," or "please"); `personal` anywhere.

## Steps

1. Only a clear factual question goes on (RULES.md rule 9): it starts with a question word or ends with "?", and it isn't about the user's own things ("my"). Otherwise say `personal` (about the user) or `unclear`, and stop. Nothing is sent to a search engine.
2. Check the network: one connect to www.bing.com:443, 2 seconds.
3. Offline: say `offline` and stop.
4. Online: search and read pages (`gather`: the partner's search, then Bing; at most 3 searches and 60 seconds). Each page goes to the same judge as the bank route, with the quote check.
5. Nothing found: say gather's message, or `not_found`.
6. Found: answer, the quoted line (if the answer doesn't already contain it), the page's url as the source, and file the answer in the bank under that url so it can be asked offline later. Then say `saved`, `already_saved` or `save_failed`.

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
- unclear: I'm not sure what you're asking, so I didn't look it up. Try asking it as a question.
- personal: I don't have that in your notes or mail.

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
| What's my favorite color? | not_found | I don't have that in your notes or mail. |
| Purple elephants dancing | not_found | I'm not sure what you're asking |
