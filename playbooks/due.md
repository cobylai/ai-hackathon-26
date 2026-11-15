# Due

## For

What is due, and when, from saved mail. "What's due Monday?", "Any deadlines this week?", "What's due on November 19?"

## Triggers

- due: `due`
- due: `deadlines?`

## Steps

1. The question has a due word (Triggers). Then this route runs, before every other route below it.
2. Work out the date range in code from the question (table below). Nothing named means today plus the next 6 days.
3. Look up every deadline in the bank inside that range (`bank.due`), sorted by date, then time.
4. If there are none, say `nothing_due` and stop.
5. Write one row per deadline: day (when the range is more than one day) and time, the ask (or the summary, or the subject), and the sender and sent date. Under it, the entry's one-line summary, so amounts come along.

Date range table (in code, `reason/route.py`):

| Phrase | Range |
|---|---|
| today, tonight | today |
| tomorrow | today + 1 |
| Monday … Sunday | the next such day, or today if today is that day |
| next Friday (etc.) | that day in next week (Mon–Sun) |
| this week | today to Sunday; on Sat/Sun, today to the coming Sunday |
| this weekend | Saturday (or today, if later) to Sunday |
| next week | next Monday to next Sunday |
| Nov 20, November 20th, 11/20, 2026-11-20, on the 20th | that day |
| nothing | today to today + 6 ("in the next 7 days") |

## May look

The bank's deadlines (dates already worked out when the mail was saved).

## May not look

The model, the web, the calendar.

## Wording

- head_day: Due {label}:
- head_range: Due {label} ({start} to {end}):
- row: - {when}{what} ({source})

`{when}` is the day and time followed by two spaces, or nothing. `{source}` is "sender, Nov 12".

## Not found

- nothing_due: Nothing due {label} in your saved mail.

## Never

- Never call the model. Dates are worked out in code.
- Never leave out a row's source.

## Prompt

No model step.

## Examples

| question | route | answer contains |
|---|---|---|
| What's due on November 16? | due | Reply with your vote; Hugo Sato |
| What's due tomorrow? | due | Due Mon Nov 16 |
| What's due on November 30? | due | Nothing due Mon Nov 30 in your saved mail. |
