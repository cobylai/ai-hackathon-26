# Open

## For

Take me there: after an answer that listed rows, "open it", "open the second one" or a click on a row opens that exact thing. That's the email in Apple Mail (the test account), the assignment or saved page, or the event in Calendar. When the exact thing can't be opened, the nearest one is shown: the saved bank entry. The follow-up route (`followup.md`) picks the row; this playbook says how it is opened.

## Triggers

No triggers of its own: `open` in `followup.md` hands the picked row to `act.plan_row`.

## Steps

1. The row is a calendar event: show `show_event_preview` and wait for a yes. On yes, Calendar shows that event (found by title and start time in the Flux calendar). If it isn't found, say `event_not_found` and open Calendar.
2. The entry has a web or file link (Canvas, a saved web page): show the page preview from `act.md` and open it in the default browser on yes.
3. The entry is an email: show `open_mail_preview` and wait for a yes. On yes:
   - Open the message in Apple Mail, searching only the test account's inbox by sender address and subject. This works offline.
   - If Mail doesn't have it and the Mac is online, open the thread's Gmail page in the test account (`not_in_mail`).
   - Otherwise say `cannot_open_mail` and show the saved copy.
4. Anything else (a note, a page without a link): show the saved copy. Nothing is opened.

## May look

The picked row's stored fields: the entry's source link, sender address and subject, or the event's title and start. Apple Mail, only the inbox of `ilovelocalai@gmail.com`.

## May not look

Links or addresses written inside an email's text. Other Mail accounts. The model.

## Wording

- show_event_preview: I'll show "{title}" ({when}) in Calendar.
- showed_event: Showed "{title}" in Calendar.
- open_mail_preview: I'll open the email from {who}, "{subject}", in Mail.
- opened_mail: Opened the email from {who}, "{subject}", in Mail.
- not_in_mail: Mail doesn't have that email, so I opened its Gmail page instead.
- saved_copy: Saved copy: {who}, {date}, "{subject}". {summary}

## Not found

- event_not_found: I couldn't find "{title}" in Calendar, so I opened Calendar.
- cannot_open_mail: Here's that email, from what I saved:

## Never

- Never open a link, address or attachment that appears inside an email or page. Only the row's own stored source is opened.
- Never open anything without a yes.
- Never search, open or change any Mail account other than the test account. Never send, move, delete or mark mail.

## Prompt

No model step.

## Examples

| question | route | answer contains |
|---|---|---|
| What's due on November 16? | due | Due Mon Nov 16 |
| open the first one | act | I'll open; yes |
| no | act | Cancelled |
| What did Felix ask me? | person | Felix Ambrose |
| open the second one | act | I'll open the email from Felix Ambrose; in Mail |
| no | act | Cancelled |
