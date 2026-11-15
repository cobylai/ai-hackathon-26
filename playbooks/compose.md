# Compose

## For

Writing an email or a reply into a draft box you can edit, then "Open in Mail". Nothing is ever sent. "Draft a reply to Greta", "write a reply to Milo saying yes", "write an email to Felix about the cabin", "draft an email about the study room", and a click on a Suggested "Draft" button. Works with Wi-Fi off. "… in Gmail" stays with `act.md`.

## Triggers

- reply: `^(?:please\s+|can you\s+|could you\s+|(?:flux|muse),?\s+)?(?:(?:draft|write)\s+(?:me\s+)?(?:a\s+|an\s+)?(?:quick\s+|short\s+)?(?:reply|response|answer)(?:\s+back)?|reply)\s+to\s+(.+)$`
- compose: `^(?:please\s+|can you\s+|could you\s+|(?:flux|muse),?\s+)?(?:draft|write|compose)\s+(?:me\s+)?(?:an?\s+)?(?:quick\s+|short\s+|new\s+)?(?:e-?mail|message|note)(?:\s+(.+))?$`
- gmail: `in gmail|as a gmail draft|gmail draft`
- gist: `saying|that says|to say|telling (?:him|her|them)|that|about|re|regarding|on`
- new: `(?:(?:flux|muse),?\s+)?(?:what|when|where|who|whom|whose|why|how|is|are|was|were|do|does|did|can|could|will|would|should|open|remember|forget|catch me up|discover|show|list)`
- my_name: `my name is ([A-Z][a-z'\-]+)|i'm called ([A-Z][a-z'\-]+)|call me ([A-Z][a-z'\-]+)`

`reply` and `compose` are tried on the question with its end punctuation removed. Group 1 is the rest: an optional "to <name>" and an optional `gist` word followed by the topic or what to say. A question with a `gmail` phrase passes to `act.md`. `my_name` is read from your notes for the sign-off.

## Steps

1. If a compose question is held (at most 3 minutes old), this input answers it. A yes or no, a question (ending in "?" or starting with a `new` word) drops it and goes on. Otherwise match `reply` or `compose`, skipping `gmail`. Neither matches: this route passes.
2. Who it is to. A name that matches one sender in the bank: their newest address. Two or more people: `which`. No name, or an unknown name: `who`. These are the only two questions, at most two per draft. An unknown name after asking gets an empty To, and no address is ever made up.
3. Reply: the person's newest meeting ask, else their newest email with an ask, else their newest email. If it is a meeting ask whose day and time were read (`suggest.md`), write the template from code: `yes` if free; `no_slot` with the clash and the next free half hour that day, 9am to 6pm; `no_reason` if no slot is free. Otherwise the model writes the body from that email's summary and ask, plus what you said (`reply_prompt`).
4. New email: the material is the bank entries about the topic (`bank.search`, kept only if they share a word with it), that person's page, and your notes. Nothing on the topic, or no topic: ask `more`, and your answer becomes the only material. The model writes the subject and body only from that (`compose_prompt`).
5. Sign with your first name from a `my_name` note (none: no sign-off). Show the draft box with To, Subject and body, the entries used, and Open in Mail / Discard. Open in Mail hands a plain-text `mailto:` link to macOS; nothing is sent.

## May look

The bank (the person's email, topic search, person pages, your notes), Apple Calendar for a meeting reply's day.

## May not look

The web, Gmail, the model's own knowledge.

## Wording

- draft_head: Here's a draft to {who}. Edit it, then Open in Mail. Nothing is sent.
- draft_head_noto: Here's a draft. I don't have an address for {who}, so To is empty. Nothing is sent.
- draft_head_nobody: Here's a draft. To is empty. Nothing is sent.
- used: Used: {labels}
- yes: Hi {first},\n\nYes, {when} works for me. See you then.
- no_slot: Hi {first},\n\nI can't make {when}, I have {clash} then. Would {slot} that day work instead?
- no_reason: Hi {first},\n\nI can't make {when}, I have {clash} then. Could we find another time?
- sign: \n\n{name}
- opened: Opened a new message in Mail. Nothing was sent.
- discarded: Discarded.

## Not found

- who: Who is this to?
- who_unknown: I don't have anyone called {name}. Who is this to?
- which: Which {name}? {options}
- more: I don't have anything about {topic}. Tell me a little more: what should it say?
- more_blank: What should it say?
- no_sender: I have nothing from {name}, so there's no email to reply to.
- cannot_write: I couldn't write that ({why}). Nothing was drafted.
- open_failed: I couldn't open Mail: {why}

## Never

- Never send. Open in Mail only fills a new message; you press Send yourself.
- Never invent an address, a fact, a date or a name. To stays empty when no address is stored.
- Never ask more than two questions for one draft.
- Never say free or busy unless both the time and the calendar were read.
- Write only from the bank entries shown and what you said.

## Prompt

Code fills in the braces. At most 300 tokens, temperature 0.2.

### reply_system
```text
You write short, plain email replies for a student. You write only the reply body. You never add facts, dates, times or names that were not given.
```

### reply_prompt
```text
Write the student's reply to this email.

EMAIL FROM {who}
Subject: {subject}
Summary: {summary}
{ask_line}
WHAT THE REPLY SHOULD SAY: {gist}

Write one to three short sentences. Start with "Hi {first}," on its own line. No subject line, no signature, no placeholders.
```

### compose_system
```text
You write short, plain emails for a student, using only the notes given. You never add facts, dates, times, places or names that are not in the notes. Reply with JSON only.
```

### compose_prompt
```text
Write a short email from the student{to_line}.

WHAT THE STUDENT WANTS IT TO BE ABOUT: {topic}

NOTES (use only these). Each email note was sent TO the student; its From line is who wrote it:
{notes}

Return {{"subject": "...", "body": "..."}}. The subject is under 8 words. The body is two to four short sentences and starts with "{greeting}" on its own line. No signature, no placeholders, nothing that is not in the notes. Write as the student, to the person named: if an email asked the student for something, the student is the one who answers or does it.
```

### compose_hint
```text
{"subject": "string", "body": "string"}
```

## Examples

Run in order as one conversation. The first and last rows add and remove a name note, so the other playbooks' "Nothing yet" examples still hold. The checker blocks the network; Bonsai on localhost writes the bodies.

| question | route | answer contains |
|---|---|---|
| remember my name is Coby | remember | |
| Draft a reply to Milo | compose | draft to Milo Fenn; Yes, Thursday; Coby |
| Draft a reply to Greta | compose | I have Lab then |
| write an email | compose | Who is this to? |
| Felix | compose | What should it say? |
| about the cabin trip money | compose | draft to Felix Ambrose; Used: |
| write an email to Zed about lunch | compose | I don't have anyone called Zed |
| forget my name is Coby | forget | |
