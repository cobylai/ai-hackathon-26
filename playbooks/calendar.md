# Calendar

## For

What is on the Mac's Apple Calendar. "What's on my calendar tomorrow?", "What do I have this week?", "When is my next meeting?", "Am I free Friday?"

## Triggers

- calendar: `calendar|schedule`
- calendar: `(?:my|any) (?:next |upcoming |first )?(?:meetings?|events?|appointments?)`
- calendar: `what do i have|what am i doing|am i (?:busy|free)`
- next_event: `(?:next|upcoming)\s+(?:meeting|event|appointment|thing)s?`
- next_event: `when is my next`

## Steps

1. The question has a calendar trigger and is not shaped "what did <name> say …" (that stays a person question). Checked after due, before person.
2. If it asks for the next event (next_event trigger): read events from today to 60 days out, keep the first that hasn't started yet, write it, and stop. None: say `none_next`.
3. Otherwise work out the date range exactly as the due route does, and read the events in it from Apple Calendar.
4. If there are none, say `nothing`. Otherwise write one row per event (day when the range is more than one day, time or "all day", title, location), then the source line. If Calendar can't be read, say `error`.

## May look

Apple Calendar on this Mac, read through `applecal`: by default only the calendar named in `FLUX_CALENDAR` ("Flux demo"); with `FLUX_CALENDARS=all`, every real calendar except subscribed/holiday/birthday ones and any the user's `~/.flux/calendars.json` denies, with repeating events expanded. With `all`, each row ends with its calendar in brackets and the source line names the calendars used.

## May not look

The model, the web, the bank.

## Wording

- head_day: On your calendar {label}:
- head_range: On your calendar {label} ({start} to {end}):
- next_head: Your next event:
- row: - {when}  {title}{where}
- row_cal: [{calendar}]
- source: Source: Apple Calendar ({calendar})

`{where}` is " (location)" or nothing.

## Not found

- nothing: Nothing on your calendar {label}.
- none_next: Nothing coming up on your calendar in the next {days} days.
- error: I couldn't read Apple Calendar ({error}).

## Never

- Never call the model. Times and ranges are worked out in code.
- Never add, move or delete an event. (Writes elsewhere stay on the "Flux demo" calendar only, whatever `FLUX_CALENDARS` says.)

## Prompt

No model step.

## Examples

| question | route | answer contains |
|---|---|---|
| What's on my calendar tomorrow? | calendar | calendar |
| When is my next meeting? | calendar | calendar |
| What do I have this week? | calendar | this week |
