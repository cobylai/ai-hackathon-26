# People

## For

Who someone is and how they relate to the user, from their person page and their mail. "Who is Felix?", "What do you know about Hugo Sato?"

## Triggers

- who: `who is|who's|what do you know about|what do you remember about`

Counts only at the start. The rest of the sentence must be a known name: every word is a sender's name word or a word of a person page's name. Otherwise this route doesn't run and the question goes on to the other routes.

## Steps

1. The question starts with a who trigger and the rest is a known name.
2. Read their person page (`bank.people.get`): how they relate to the user and the facts on it. A sender with no page yet gets an empty one.
3. Read their newest 5 emails (`bank.by_person`), never copied into the page.
4. Write: name, relation (or `relation_unknown`), facts, emails, then the source line (the page and the emails).

## May look

The bank's `people` folder and that person's mail.

## May not look

The model, the web, other people's mail.

## Wording

- head: {name}
- relation: How you know them: {relation}
- relation_unknown: I don't know how you know them yet.
- facts_head: What I know about them:
- fact_row: - {fact}
- emails_head: Newest emails from them ({count} of {total}):
- email_row: - {date}  {subject}
- page_label: people page for {name}

## Not found

A name that is no sender and has no page doesn't take this route; the other routes answer (the bank, then the web, else "I don't have that saved").

## Never

- Never guess how someone relates to the user. Only the page says that, and only what discovery or the user wrote there.
- Never let the model write the page.

## Prompt

No model step.
