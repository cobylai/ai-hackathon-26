# About Flux

## For

What Flux is and how to use it. "What's Flux?", "What can you do?", "Help", "How do I use this?" give a short overview. "Show me", "Walk me through it" or "Start the tour" start a guided tour that runs real examples on the user's own data, one thing at a time: then "next", "back", "skip" or "stop".

## Triggers

Each must be the whole question (after a leading "Flux," or "please"); "help me draft a reply" is not the overview.

- overview: `what(?:'s|’s| is) flux|what is (?:this|flux)|what can you do|what do you do|help|how do i use (?:this|flux|it)`
- start: `show me|walk me through(?: it| flux)?|start the tour|give me (?:a|the) tour|tour`
- next: `next|next one|go on|continue|keep going|ok next|okay next`
- back: `back|go back|previous`
- skip: `skip|skip it|skip this|skip that`
- stop: `stop|end the tour|stop the tour|that's enough|done|exit`
- internet: `do you need (?:the )?(?:internet|wi-?fi)|do you need to be online|does (?:this|it|flux) (?:need|use) (?:the )?(?:internet|wi-?fi)|do you work offline|can you work offline|does (?:this|it|flux) work offline`
- model: `what model are you(?: running| using| on)?|what model (?:is|does) (?:this|it|flux)(?: use| run| running| using)?|which model (?:are you|do you use|is this)|what ai (?:are you|is this)`
- mail: `how did you get my (?:mail|email|emails)|how do you (?:get|read) my (?:mail|email|emails)|how do you read gmail`
- send: `will you send (?:that|it|this)|are you going to send (?:that|it|this)|do you send (?:it|that|emails|mail|anything)|can you send (?:that|it|this)`

## Steps

1. The whole question is one of the fixed questions (internet, mail, model, send): write its `<key>_answer` (internet: `internet_offline` or `internet_online` after it, by whether the Mac is online) and the source line. These are answered even while an action or draft waits for a yes, and don't touch it.
2. The whole question is an overview trigger: write `intro`, `intro2`, `can_head`, then one line per row of `## Overview` (its example question, filled from the bank, without a closing full stop; left out when the bank has no sender or due item for it). The example questions are also buttons.
3. The whole question is a start trigger: go to the first row of `## Tour`. While a tour is on (kept in the chat's session), next, back and skip move one row and stop ends it; any other question is answered as usual and the tour waits.
4. For a step: write `step_head`, the step's `<key>_what` line, then for each example in its row, fill names and items from the bank (`name` = the newest sender with an ask, `item` = the nearest coursework due item), run it through answer() on a scratch session, and write the question and the real answer. Rows marked `show` write the question without running it.
5. Clear anything an example left waiting for a yes or for more words (act, compose), so "next" is never taken as a yes. Nothing is saved, opened or sent.
6. If the bank lacks what a step needs, write its `<key>_skip` line and go on to the next step in the same answer. End with `<key>_try`, `nav`, and the buttons.

## May look

The playbooks' own Examples tables, and the bank (sender names with an ask, coursework due items) to fill them. Each example then looks where its own route may look.

## May not look

The model, the web (an example that needs the web is not in the tour).

## Overview

Each line: a label (for this file only), then the playbook and the example row (1 = first row) whose question is shown and offered as a button. `name` / `item`: the example's own name or item is kept when the bank has it; otherwise the bank's newest sender with an ask, or its nearest coursework due item, is put in; with neither, the line is left out.

- Your day: catchup 1
- What's due: due 4
- What someone asked you: person 1 name
- Set you up to work: setup 3 item
- Remember something: remember 3

## Tour

Each line: step key, then the examples it runs, as playbook and row. `name` or `item` swaps in the bank's sender or due item; `show` writes the question without running it.

- catchup: catchup 1
- due: followup 1, followup 3
- person: person 1 name
- remember: remember 3 show, remember 1
- suggest: suggest 1 name, compose 2 name
- setup: setup 1 item
- voice:
- never:

## Wording

- internet_answer: No. I read your mail and coursework while you're online, then answer from what I saved.
- internet_offline: You're offline right now, and I still work.
- internet_online: I only go online to sync and to look things up.
- mail_answer: Through my own hidden browser. You sign in once, and I read Gmail the way you would. No connectors and no API keys.
- model_answer: Bonsai 2, the 4B model, running on this Mac. Your voice is transcribed by Argmax, also on this Mac. Most answers about your day use no model at all: I look them up in what I saved.
- send_answer: No. I write the draft and you send it. I never send anything myself.
- intro: I'm Flux, a personal assistant that lives on your Mac.
- intro2: I keep track of your mail, deadlines and calendar, remember what matters, and help you act on it. Everything runs on this Mac. Nothing goes to the cloud, and I work with Wi-Fi off.
- can_head: Try asking:
- can_row: - {question}
- source: Source: Flux's guide
- step_head: {n} of {total}: {title}
- example: Example: "{question}"
- shown: (Flux would save that note. The tour doesn't, so here's what Flux knows about you now.)
- suggested: Suggested: {line}
- no_yes: (In the tour this stops here: nothing is opened. Ask it yourself to go ahead.)
- nav: Say "next", "back" or "stop".
- nav_last: That's the tour. Say "stop" to finish, or ask anything.
- ended: Tour ended. Ask anything, or say "show me" to start again.
- resumed: Picking up the tour where you left it.
- catchup_title: Catch me up
- catchup_what: One question gives you today's calendar, what's due soon and recent asks in your mail.
- catchup_try: Try it with your own words: "what's my day?" or "brief me".
- due_title: What's due, and follow-ups
- due_what: Ask what's due for any day or week, then ask about one of the rows by its place in the list.
- due_try: Try "what's due this week?", then "the second one".
- person_title: What someone asked you
- person_what: Ask about anyone who has written to you, and Flux lists what each email asked.
- person_try: Try it with someone else who emails you.
- remember_title: Remember something
- remember_what: Tell Flux something about you, and it keeps it as a note on this Mac. Only what you say is kept.
- remember_try: Try "remember that …" with something true about you; "forget …" removes it.
- suggest_title: A suggested task and a draft
- suggest_what: Under an answer, Flux may suggest one next step, like adding an event or drafting a reply. Nothing happens until you click.
- suggest_try: Click a suggestion under any answer, or say "draft a reply to …".
- setup_title: Set you up to work
- setup_what: Name a piece of coursework and Flux finds its page and what it needs, then asks before opening anything.
- setup_try: Try "set me up for …" with something you have due.
- voice_title: Talking to Flux
- voice_what: Tap Fn-Space from any app to open Flux. Hold Fn-Space, say your question and let go to get the answer. Hold to talk works in this window too.
- voice_try: Try holding Fn-Space and asking "what's due tomorrow?".
- never_title: What Flux won't do
- never_what: Flux won't guess facts about you, won't send, submit or buy anything, and won't act without showing you what it will do and getting your yes. It answers only from what it found, and says so when it hasn't.
- never_try: That's the tour. Ask anything, or say "stop" to finish.

## Not found

- catchup_skip: (Skipping "Catch me up": your bank is empty. Sync your mail to see it.)
- due_skip: (Skipping "What's due": nothing is due tomorrow in your saved mail or Canvas. Sync them to see it.)
- person_skip: (Skipping "What someone asked you": no saved email has an ask yet. Sync your mail to see it.)
- remember_skip: (Skipping "Remember something".)
- suggest_skip: (Skipping "A suggested task": no saved email has an ask yet. Sync your mail to see it.)
- setup_skip: (Skipping "Set you up to work": no coursework is due soon. Sync Canvas to see it.)
- not_on: There's no tour going on. Say "show me" to start one.

## Never

- Never let the model write the overview or a step.
- Never run an action: drafts and "set me up" stop before the yes, and remember examples are shown, not saved.
- Never show an example question that its own route no longer answers: examples come from the routes' Examples tables.

## Prompt

None. No step calls the model; the examples run through their own routes.

## Examples

| question | route | answer contains |
|---|---|---|
| What is Flux? | about | I'm Flux, a personal assistant that lives on your Mac.; Try asking:; - Catch me up |
| Do you need the internet? | about | No. I read your mail and coursework while you're online; You're offline right now, and I still work. |
| How did you get my mail? | about | Through my own hidden browser |
| What model are you running? | about | Bonsai 2, the 4B model; Argmax |
| Will you send that? | about | No. I write the draft and you send it. |
| What's Flux? | about | Everything runs on this Mac; - What's due this week? |
| What can you do? | about | - Set me up for the lab report |
| help | about | - Remember that my lab is Tuesdays at 2 |
| next | about | There's no tour going on |
| show me | about | 1 of 8: Catch me up; Example: "Catch me up"; Asks in mail |
| next | about | 2 of 8; Example: "What's due tomorrow?"; Due Mon Nov 16; Example: "the first one" |
| next | about | 3 of 8; ask me?" |
| back | about | 2 of 8 |
| skip | about | 3 of 8 |
| next | about | 4 of 8; Remember that my lab is Tuesdays at 2.; doesn't |
| next | about | 5 of 8; Example: "What did; Draft a reply to |
| next | about | 6 of 8; Example: "Set me up for |
| next | about | 7 of 8; Fn-Space |
| next | about | 8 of 8; won't send; That's the tour |
| stop | about | Tour ended |
