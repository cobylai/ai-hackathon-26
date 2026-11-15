# Follow-up

## For

A short question that leans on the last answer in this conversation. "And tomorrow?", "What about Friday?", "And next week?" after a due or calendar question. "And Hugo?" after a person question. "The first one", "the second one", "that one", "who sent that?", "when is it due?", "open it" after any answer that listed rows.

## Triggers

- more: `^(?:ok(?:ay)?\s+)?(?:and|what about|how about|and what about)\s+(?:for\s+|on\s+)?(.+)$`
- pick: `^(?:(?:and|what about|how about|show me|tell me about|read|read me|what's|what is)\s+)?(?:the\s+)?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th)(?:\s+(?:one|row|item|thing))?$`
- pick: `^(?:(?:show me|read|tell me about)\s+)?(?:number|#)\s*(\d+)$`
- pick: `^(?:(?:and|what about|show me|tell me about|read)\s+)?(?:that|this) one$`
- who: `^(?:who (?:sent|wrote)|who is|who's|who was)\s+(?:(?:that|this|it)(?:\s+one)?|the (\w+)(?:\s+one)?)(?:\s+from)?$`
- when: `^when(?:\s+is|'s|\s+was|\s+does|\s+do)?\s+(?:(?:that|this|it)(?:\s+one)?|the (\w+)(?:\s+one)?)\s+(?:due|happening|on)$`
- open: `^(?:please\s+)?(?:open|launch|pull up|bring up)\s+(?:(?:it|that|this)(?:\s+one)?|the (\w+)(?:\s+one)?)$`

Code tries these on the question lowercased, with a leading voice dash, "Muse," and "please" dropped and end punctuation removed. A group that should be an ordinal (`the (\w+) one`) only counts when the word is one (first … tenth, last, 1st … 10th); "open the calendar" is not a follow-up.

## Steps

1. Skip this route when a discovery question or an action is waiting for its yes, or when the window or chat loop has no conversation yet. Nothing is kept between runs and nothing is written to the bank.
2. `more` with a date (anything the due date table names) after a due or calendar answer: run that route again for the new range.
3. `more` with one to three name-like words after a person or "who is" answer: ask the last question again with the name swapped. An unknown name gets the person route's "I have nothing from …".
4. `pick`, `who`, `when` or `open` after an answer that listed rows: pick the row (an ordinal, else the row picked last, else the only row; with several, say `which_one`). `pick` shows the row, `who` says who sent it, `when` says when it is due, and `open` hands it to the act route, which shows what it will open and waits for a yes.
5. Anything else is a new question, answered by the routes as usual. No model call in this route.

## May look

The last question, its route and the rows it listed, kept in memory for this window or chat loop only.

## May not look

The model. Earlier answers than the last one. Anything written to disk.

## Wording

- show_entry: {line}
- show_summary: {summary}
- who_sent: {who} sent it on {date}: {subject}.
- who_course: It's from {who} on Canvas, {date}: {subject}.
- who_event: That's an event on your calendar, not mail: {title}.
- when_due: Due {when}.
- when_event: It's on {when}.
- which_one: Which one? Say "the first one", "the second one" and so on (there are {n}).
- out_of_range: The last answer only listed {n}.

## Not found

- when_none: It has no due date in your saved mail.
- no_link: That one is mail from {who}, and it has no link to open.

## Never

- Never call the model to work out what a follow-up means.
- Never write the conversation to the bank or a file.
- Never open anything without the act route's yes.

## Prompt

No model step.

## Examples

| question | route | answer contains |
|---|---|---|
| What's due tomorrow? | due | Due Mon Nov 16 |
| who sent that? | followup | Which one? |
| the first one | followup | Submit reading quiz; Source: INFO 3361 Data Stories |
| who sent that? | followup | It's from INFO 3361 Data Stories on Canvas |
| when is it due? | followup | Due Mon Nov 16 9am |
| open it | act | I'll open this page; yes |
| no | act | Cancelled |
| the third one | followup | Reply with your vote; Hugo Sato |
| and Friday? | due | Due Fri Nov 20; Felix Ambrose |
| what about next week? | due | Due next week |
| - And Tuesday? | due | Due Tue Nov 17 |
| What did Felix ask me? | person | $35; Felix Ambrose |
| and Hugo? | person | Hugo Sato |
| and Zelda? | person | I have nothing from Zelda. |
| What's on my calendar tomorrow? | calendar | calendar |
| and Friday? | calendar | calendar; Fri Nov 20 |
| and next week? | calendar | calendar; next week |
| What is the capital of Peru? | offline | offline |
| the first one | not_found | didn't look it up |
