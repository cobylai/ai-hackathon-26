# Discover

## For

Flux learning about the user on its own and keeping only what the user confirms. "Discover", "learn about me", then yes / no / skip to each question. "What have you learned?", "Unlearn 2".

## Triggers

- start: `discover|discovery|discover mode|run discovery|start discovery|learn about me|find out about me|what can you learn about me`
- learned: `what (?:have|did) you (?:learned|learn|discovered|discover)(?: about me)?|what you(?:'ve| have)? learned`
- unlearn: `(?:unlearn|remove learned|remove fact|forget learned)(?: number| fact)? (\d+)`
- yes: `yes|yeah|yep|yup|sure|correct|right|that's right|true|yes it is|yes i do|yes i am|yes please`
- no: `no|nope|not really|wrong|that's wrong|false|no it isn't|no i don't|no i'm not|never`
- skip: `skip|next|pass|not sure|maybe|later|ask me later|i don't know|dunno`
- stop: `stop|done|quit|end|that's all|cancel|enough|stop discovery`

`start`, `unlearn` and the answers must be the whole input, lowercased, with punctuation and a leading "Flux," or "please" removed. `learned` can be anywhere. The answers count only while a discovery question is held.

## Steps

1. start: when online and not synced by discovery in the last 30 minutes, run the existing mail sync so the bank is current (`scripts/sync_email.py`), then read every bank entry (mail and Canvas) and Apple Calendar from 8 weeks back to 4 weeks ahead. A failed sync or calendar is said and skipped.
2. Code finds the patterns (`discover/propose.py`): an event with the same title, weekday and time at least 3 times; a course code in a Canvas entry or in at least 2 mail entries; a sender with at least 3 emails, with the course they write about most; a sender with an amount and a due date at least twice. For each sender with at least 3 emails and no relation yet, Bonsai suggests a short relation (prompt below), checked in code, only when that question comes up (an unusable guess drops the question); it only becomes a question. Already answered or already known ones are dropped; at most 10, most supporting entries first.
3. Ask the first one: `question`, its entries (`from_row`), `ask_yes`, then the source line. The question is held.
4. While held: yes writes it (a note: `bank.remember`; a person fact: `people.set_fact` with the entries as source; a relation: `people.set_relation`) and records it; no records it so it is never asked again; skip leaves it for next run; stop ends the run. Then the next question, or `done`. Any other input ends the run.
5. learned: list every confirmed fact still in place, numbered, with where it came from.
6. unlearn N: remove fact N (`bank.forget` on the exact note, `people.remove_fact`, or clear the relation) and mark it so it is never asked again.

## May look

The bank (mail, Canvas, notes, person pages), Apple Calendar, Gmail through the existing sync when online, and the model for the relation guess only.

## May not look

New scrapers, the web, any calendar other than the Muse one. The model never writes a fact and never picks a question.

## Wording

- synced: Checked your mail first ({count} new).
- sync_failed: I couldn't check your mail first ({why}), so I used what's already saved.
- no_calendar: I couldn't read Apple Calendar ({why}), so I skipped events.
- found: I found {count} things I'd like to check with you.
- question: Question {k} of {n}: {question}
- from_head: From:
- from_row: - {line}
- from_more: - and {count} more
- ask_yes: Say yes, no or skip (or stop).
- saved: Saved: {fact}.
- declined: Okay, I won't ask that again.
- skipped: Skipped. I'll ask next time.
- done: That's all for now: {yes} saved, {no} no, {skip} skipped.
- stopped: Stopped: {yes} saved, {no} no, {skip} left for next time.
- shown_relation: {name} is your {relation}
- learned_head: What I've learned about you (you said yes to each):
- learned_row: {n}. {fact} (from {sources})
- unlearn_hint: Say "unlearn {n}" to remove one.
- learned_source: Source: your answers in discovery
- unlearned: Removed: {fact}. I won't ask about it again.

## Not found

- nothing_new: Nothing new to ask you right now.
- nothing_learned: Nothing learned yet. Say "discover" and I'll ask you a few questions.
- unlearn_none: There's no learned fact {n}; I have {count}.
- unlearn_failed: I couldn't remove "{fact}" safely. Say "forget" with more of its words.

## Never

- Never write anything about the user without a yes (RULES.md rule 7).
- Never ask a question already answered yes or no, or one that is already true in the bank.
- Never let the model write a fact or choose what to ask; it only suggests a relation.
- Never ask more than 10 questions in one run.

## Prompt

### relation_system

```
You read emails one person sent to the user and say in a few words how that person relates to the user. Reply with JSON only.
```

### relation_prompt

```
Emails from {name}, newest first:

{notes}

How does {name} most likely relate to the user? Answer with 1 to 4 lowercase words, such as "lab partner", "TA", "professor", "advisor", "roommate", "teammate", "classmate", "friend", "coworker". If the emails don't show it, answer "unknown".
Reply as {{"relation": "..."}}
```

### relation_hint

```
{"relation": "lab partner"}
```

## Examples

| question | route | answer contains |
|---|---|---|
| What have you learned? | discover | Nothing learned yet |
| Discover | discover | Question 1 of; Are you taking CHEM 1583 Kitchen Chemistry?; Lab 7: Emulsions; Say yes, no or skip; Source: CHEM 1583 Kitchen Chemistry, Nov 15 |
| yes | discover | Saved: I'm taking CHEM 1583 Kitchen Chemistry.; Question 2 of; Are you taking HIST 2147 Maps and Empires? |
| no | discover | Okay, I won't ask that again.; Question 3 of |
| stop | discover | Stopped: 1 saved, 1 no |
| What do you know about me? | about_me | I'm taking CHEM 1583 Kitchen Chemistry |
| Discover | discover | Question 1 of |
| stop | discover | Stopped: 0 saved, 0 no |
| What have you learned? | discover | 1. I'm taking CHEM 1583 Kitchen Chemistry (from CHEM 1583 Kitchen Chemistry, Nov 15); unlearn 1 |
| Unlearn 1 | discover | Removed: I'm taking CHEM 1583 Kitchen Chemistry. |
| What have you learned? | discover | Nothing learned yet |
| What do you know about me? | about_me | Nothing yet |
