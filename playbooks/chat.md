# Chat

## For

Greetings, mic checks, thanks and questions about Flux itself, so they get a short reply instead of a web search. "Hey, can you hear me okay?", "Hi", "Thanks!", "Is this working?", "How are you?", "Who are you?", "What are you?" ("What can you do?" on its own is the overview, `about.md`)

## Triggers

- chat: `hey|hi|hello|good (?:morning|afternoon|evening)`
- chat: `can you hear me|are you (?:there|listening|working|on)|is this (?:on|working|thing on)|testing(?: testing)*|mic check`
- chat: `how are you(?: doing)?|hope you'?re (?:doing )?(?:well|good|ok|okay)|nice to meet you`
- chat: `thanks|thank you|cheers|good job|great|perfect|never ?mind|cool`
- chat: `who are you|what are you|what(?:'s| is) flux|what can you do|what do you do|who (?:made|built|created) you|are you (?:a|an) (?:ai|bot|robot|assistant|chatbot)`
- filler: `okay|ok|so|um|uh|oh|well|just|yeah|yes|flux|muse|there|again|very much|so much|today|a lot`

It is chat only when, with every chat and filler phrase taken out, at most 2 words are left and none is a question word (what, when, where, who, which, why, how). So "Hey, what's due tomorrow?" is not chat.

## Steps

1. A chat trigger matches and almost nothing else is said (rule above). Checked after the person routes, before the bank.
2. A mic check (can you hear me, is this working, testing) says `hear_you`; thanks says `thanks`; a question about Flux itself (who are you, what can you do) says `about_flux`; anything else says `hello`.
3. Stop. Nothing is searched, nothing is saved.

## May look

Nothing. The reply is fixed text.

## May not look

The web, the bank, the model.

## Wording

- hear_you: I can hear you. Ask me about your mail, what's due, or your calendar.
- hello: Hi. Ask me about your mail, what's due, or your calendar.
- thanks: You're welcome.
- about_flux: I'm Flux, an assistant that runs on this Mac. I answer from your saved mail, notes and calendar, and I look things up online only when you ask something that isn't saved here.

## Not found

Not used: chat always has a reply.

## Never

- Never send chat to the web or the model.

## Prompt

No model step.

## Examples

| question | route | answer contains |
|---|---|---|
| Hey, can you hear me okay? Hope you're doing well. | chat | I can hear you |
| Hi | chat | Hi. |
| Thanks so much! | chat | You're welcome. |
| Who are you? | chat | I'm Flux |
| What are you? | chat | I'm Flux |
| Hey, what's due tomorrow? | due | Due Mon Nov 16 |
