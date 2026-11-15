# Catch up

## For

The user's day in one answer: today's calendar, what is due soon, and recent asks. "Catch me up", "What's my day?", "What's going on today?", "Brief me."

## Triggers

- catchup: `catch me up`
- catchup: `what(?:'s|’s| is) my day`
- catchup: `how(?:'s|’s| is| does) my day(?: look(?:ing)?)?`
- catchup: `what(?:'s|’s| is) going on today`
- catchup: `brief me`
- catchup: `(?:what|how)(?:'s|’s| is| does| do) (?:this|my|the|next) (?:week|weekend)(?: look(?:ing)?(?: like)?)?`
- catchup: `what does (?:today|tomorrow) look like|how does (?:today|tomorrow) look`
- catchup: `what(?:'s|’s| is) (?:going on|happening) (?:this week|tomorrow|this weekend)`

## Steps

1. The question has a catch-up trigger. Checked after actions and notes, before due and calendar.
2. Read today's events from Apple Calendar (`applecal.events(today, today)`) and write one row each. None: say `cal_none`. If Calendar can't be read, say `cal_error` and go on.
3. Read every deadline from today to today + 2 (`bank.due`, mail and Canvas together) and write one row each, with its sender and sent date. None: say `due_none`.
4. List the asks in email sent in the last 7 days, newest first, at most 8, then `ask_more`. None: say `ask_none`. The bank has no "done" flag, so an ask already handled still shows.
5. Write the three sections in that order, each ending with its source line, with a blank line between them.

## May look

Apple Calendar (today only), the bank's deadlines and the bank's email asks.

## May not look

The model, the web.

## Wording

- cal_head: Today on your calendar ({day}):
- due_head: Due today through {end}:
- due_row: - {when}  {what} ({source})
- due_source: Source: saved mail and Canvas
- ask_head: Asks in mail from the last {days} days:
- ask_row: - {date}  {who}: {ask}
- ask_more: - …and {n} more.
- ask_source: Source: email received in the last {days} days

The calendar rows and source line are the calendar playbook's `row` and `source`.

## Not found

- cal_none: - Nothing on your calendar today.
- cal_error: Calendar: I couldn't read Apple Calendar ({error}).
- due_none: - Nothing due in the next 3 days.
- ask_none: - No asks in mail from the last {days} days.

## Never

- Never call the model.
- Never drop the other sections because one of them failed.
- Never add, move or delete an event, and never mark an ask done.

## Prompt

No model step.
