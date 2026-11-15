# Person

## For

What one sender asked for or said, from saved mail. "What did Felix ask me?", "What does Hugo want?", "What did Lena say about the lab report?"

## Triggers

- ask: `ask|asks|asked|asking|want|wants|wanted|need|needs|needed`
- asked_name: `what\s+(?:did|has|does|do)\s+([A-Za-z][A-Za-z'\-]*)\s+(?:ever\s+|just\s+)?(?:ask|asked|say|said|send|sent|want|wanted)`

- everyone: `everyone|everybody|anyone|anybody|people|all of them`

`ask` makes it an ask question. `asked_name` is the shape "what did <name> ask/say/send/want", used to catch a name that is no sender. Which words count as a sender's name is in code (`reason/route.py`): 3+ letters from the From name or address, no titles (Prof, Dr…), no automated senders (Office, Club…), and common words that are also names ("will", "may") only when capitalized mid-sentence.

## Steps

1. A word in the question is a sender's name. Then this route runs.
2. Ask question (an ask word): list that sender's newest 8 entries, each as date, subject and its ask, or "no ask" and the summary. A full name ("Nina Valdez") keeps only that sender. No model call.
3. Other questions: give the sender's newest 8 entries to the model with the prompt below. The notes it says it used are the sources (all 8 if its list is bad). An empty reply says `model_empty`.
4. Everyone: an `everyone` word plus an ask/say/send/want/need verb ("What did everyone ask me?"). List every sender's asks whose deadline hasn't passed (or that have none), newest first, at most 12, each with the sender. None: say `no_open_asks`. No model call.
5. Misheard name: the question has an ask/say/send/want/need verb and a word that is no sender but close to one: one is the other with up to 2 letters more at the start or end ("Elena" ~ "Lena"), or one letter off when both have 5+ letters. One close sender: list their asks as in step 2, under `heard`. Two or more: say `did_you_mean` and stop.
6. Shaped "what did <name> ask/say/send/want" but no sender has that name and none is close: say `no_sender` and stop, before any search.

## May look

The bank, only that sender's entries.

## May not look

The web, the calendar, other senders' mail, the model's own knowledge.

## Wording

- ask_head: From {name}:
- ask_row: - {who}{date}  {subject}: {ask}
- no_ask_row: - {who}{date}  {subject}: no ask. {summary}
- heard: (I heard "{heard}" and took it as {name}.)
- everyone_head: Open asks from everyone ({count}):
- everyone_row: - {who}, {date}  {subject}: {ask}

`{who}` is "Name, " when two senders share the first name, else nothing. The answer ends with the source line from RULES.md.

## Not found

- no_sender: I have nothing from {name}.
- model_empty: The saved emails from {name} don't say.
- did_you_mean: I heard "{heard}". Did you mean {names}?
- no_open_asks: Nobody has an open ask in your saved mail.

## Never

- Never answer about a person from search or the web. A wrong answer about a person is worse than none.
- Never let the model read or write the ask list (step 2).
- Never mix two senders' mail as one person's.

## Prompt

Step 3 only. Code fills in `{today}`, `{question}`, `{who}` and `{notes}` (numbered note blocks: From, Date, Subject, Ask, Deadlines, Summary). Temperature 0.2, at most 300 tokens.

### person_system
```text
You answer a student's questions using only the email notes you are given. You never use outside knowledge and never guess.
```

### person_prompt
```text
Today is {today}.

QUESTION: {question}

EMAIL NOTES FROM {who}:
{notes}

Answer the question in one to three sentences using only these notes. If the notes do not answer it, say that the saved emails from {who} don't say. List the numbers of the notes you used.
```

### person_hint
```json
{"answer": "your answer", "used": [1]}
```

## Examples

| question | route | answer contains |
|---|---|---|
| What did Felix ask me? | person | $35; Felix Ambrose |
| What did Rafe ask me? | person | no ask; Rafe Quill |
| What did Nina Valdez ask me? | person | poster |
| What did Zelda ask me? | person | I have nothing from Zelda. |
| What did Hugo say about the meeting? | person | Hugo Sato |
| Elena asked me | person | I heard "Elena" and took it as Lena Marsh; outline |
| What did everyone ask me? | person | Open asks from everyone; Felix Ambrose; Source: |
| What did Bartholomew ask me? | person | I have nothing from Bartholomew. |
