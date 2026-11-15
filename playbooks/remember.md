# Remember

Three routes share this file: **remember**, **forget** and **about_me**. They hold what the user tells Flux about themself, in the bank's `me` folder.

## For

Notes the user asks Flux to keep about them. "Remember that my lab is Tuesdays at 2", "Remember I'm vegetarian", "Forget that my lab is Tuesdays at 2", "Forget that", "What do you know about me?"

## Triggers

- remember: `remember(?: that)?`
- remember: `note that`
- remember: `(?:don't|do not) forget(?: that)?`
- forget: `forget(?: that| about| the note)?`
- about_me: `what (?:do|did) you (?:know|remember) about me`
- about_me: `what have you (?:remembered|saved|noted)(?: about me)?`
- about_me: `(?:who|what) am i\b`

remember and forget count only at the start of what was said (after "Flux," or "please", which are dropped). A question ending in "?" is never a remember. about_me can be anywhere.

## Steps

1. remember: save the rest of the sentence as a note, in the user's own words (`bank.remember`), and say `saved`, or `already` if it is already there. No model call.
2. forget: find the note sharing the most words with the rest of the sentence ("forget that" alone means the newest note) and delete it (`bank.forget`), then say `forgotten`. If two notes tie, delete neither and say `which_one` with both. If none shares a word, say `forget_none`.
3. about_me: list every note, newest first, then `notes_source`. None: say `no_notes`.
4. Other questions ("when is my lab?") reach the notes through the bank route, which names the note as the source (`note_label`).

These run before every other route, so "remember the essay is due Monday" is a note, not a due question.

## May look

The bank's `me` folder.

## May not look

The model, the web, the mail. Nothing is added to the notes that the user didn't say.

## Wording

- saved: Got it. I'll remember: {fact}.
- already: I already have that: {fact}.
- forgotten: Forgotten: {fact}.
- which_one: Which one? Say a few more of its words. I have:
- note_row: - {date}  {fact}
- notes_head: Here's what you've told me:
- notes_source: Source: your notes
- note_label: your note, {date}

## Not found

- empty: What should I remember?
- forget_none: I don't have a note like that.
- no_notes: Nothing yet. Say "remember that …" to tell me something.

## Never

- Never write a note the user didn't say (RULES.md rule 7). Never rewrite their words with the model.
- Never delete more than one note per request, and never on a tie.

## Prompt

No model step.

## Examples

| question | route | answer contains |
|---|---|---|
| What do you know about me? | about_me | Nothing yet |
| Who am I? | about_me | Nothing yet |
| Remember that my lab is Tuesdays at 2. | remember | I'll remember: my lab is Tuesdays at 2. |
| Flux, remember I'm vegetarian | remember | I'm vegetarian |
| Remember I'm vegetarian | remember | I already have that |
| What do you know about me? | about_me | my lab is Tuesdays at 2; I'm vegetarian; Source: your notes |
| When is my lab? | bank | Tuesday; your note |
| Forget my bike lock code | forget | I don't have a note like that. |
| Forget that my lab is Tuesdays at 2 | forget | Forgotten: my lab is Tuesdays at 2. |
| Forget that | forget | Forgotten: I'm vegetarian. |
| What do you know about me? | about_me | Nothing yet |
