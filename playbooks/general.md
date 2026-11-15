# General

## For

Questions that aren't about the user: explanations, how-to, writing, maths, brainstorming, general facts, and small talk. "Why is the sky blue?", "How do I cook rice?", "Give me three names for a study group", "What's 15% of 80?", "Hi, how are you?"

## Triggers

- straight: `explain|why (?:is|are|do|does|did)|how (?:do|does|can|should|would) (?:i|you|we|one)|how to|write|draft me|brainstorm|ideas? for|suggest (?:a|some)|calculate|solve|what(?:'s| is) \d|translate|summari[sz]e|compare|difference between|pros and cons|tips|advice on`
- volatile: `news|headlines?|price|prices|cost of|stock|stocks|exchange rate|score|scores|weather|forecast|latest|current|currently|right now|this year's|election`

A question is general when no code route takes it and it isn't about the user (`reason-over-data.md` decides that, in code, first). `straight` questions and small talk (`chat.md` triggers) go straight to the model. Anything else is a lookup and tries the bank and the web first.

## Steps

1. Small talk (chat.md triggers) and `straight` questions skip to step 4.
2. A lookup tries the bank first, as the bank route does (`bank.md`); if it answers, that's the answer, with its source.
3. If online and it is a clear factual question (`web.md` step 1), try the web with the quote check; if the web finds something, that's the answer. If it finds nothing, go on.
4. Bonsai answers from its own knowledge, thinking on (small talk: thinking off, a sentence or two), with the last 3 turns of the chat (at most 600 tokens) for context. Then the `label` line.
5. A `volatile` question while offline starts with `cannot_check`.
6. If the answer ran out of its token cap (about 30 seconds of thinking), a short answer without thinking is given instead, followed by `cut_short`.

## May look

The bank and, when online, the web (as the bank and web routes do); the model's own knowledge; the last few turns of this chat.

## May not look

Nothing about the user comes from the model's knowledge. A question about the user never comes here (`reason-over-data.md`).

## Wording

- label: From general knowledge, not from your mail or the web.
- cannot_check: I can't check that right now, so this may be out of date.
- cut_short: (I was cut short, so this is brief.)

## Not found

- no_answer: I don't know.

## Never

- Never invent a source, link, quote or statistic.
- Never state a fact about the user (their mail, deadlines, people, calendar, classes, notes).
- Never leave off the `label` line.

## Prompt

Thinking on (small talk off). At most 1500 tokens (about 30 seconds) (the time cap).

### general_system
```text
You are Flux, a helpful assistant running on the user's Mac. Today is {today}. Answer from your own general knowledge and reasoning. Be accurate and brief: a short paragraph or a few bullet points. If you don't know or aren't sure, say so plainly instead of guessing. Never invent a source, link, quote or statistic. You can't see the user's mail, files or calendar in this reply, so don't claim anything about them.
```

### small_talk_instruction
```text
This is small talk. Reply warmly in one or two sentences.
```

### short_instruction
```text
Time is up. Using your notes so far, give your final answer now, in two or three sentences, in the format asked for above.
```
