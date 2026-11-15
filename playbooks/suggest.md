# Suggest

## For

At most two small next steps under an answer, each one line and one button, under a "Suggested" label. They come only from the entries that answer used. "Draft a reply to Greta", "You're free Thu Nov 19 at 7pm. Draft a yes to Milo?", "You have Lab then. Draft a reply proposing another time?", "Open the assignment page: Map essay". Due and catch-me-up answers show them most. "Add \"Band practice Thursday\" to your calendar", "Remind me: Submit reading quiz". Nothing happens until the button is clicked.

## Triggers

- meeting: `are you free|you free (?:for|on|at)|can (?:you|we) meet|could (?:you|we) meet|want to meet|meet up|does .{1,40}? work(?: for you)?|would .{1,40}? work(?: for you)?|are you around|are you available|available (?:on|at)`
- bare_time: `at (\d{1,2})(?::([0-5]\d))?(?!\s*(?:am|pm|a\.m|p\.m|:|\d))`

`meeting` is tried on the email's ask, subject and summary. `bare_time` reads "at 3" when no "3pm" is written.

## Steps

1. Only after a due, catchup, person, bank or followup answer. Take the bank entries that answer listed or named as its sources, in order. None: no suggestions.
2. An email with a `meeting` cue: work out the proposed day (the entry's deadlines, else `bank.dates.resolve_date` on the ask) and time (the deadline's time, else `resolve_time`, else `bare_time`: 1–7 is pm, 8–11 am, 12 noon). With both, read that day from Apple Calendar. An event (not all-day) overlapping the hour from that time is a clash: say `busy` with its title only. No clash: say `free`. No day, no time, or the calendar can't be read: go on to step 3 for this email and say nothing about free or busy.
3. Any other email with an ask: `reply`. A free meeting also gets `calendar` (`computer.event_for`, only when its start is that same time).
4. A Canvas item with a link: `open`. On a due or catchup answer, a Canvas item or an email with an upcoming deadline also gets `remind` (`computer.reminder_for`: 2 hours before a timed deadline, else 9am that day).
5. Meeting emails first, then the rest in the answer's order; each entry's own suggestions together, best first. Skip any suggestion already dismissed, drafted, opened or added in this chat. Keep at most two. A click on `calendar` or `remind` runs `computer.add_event` / `add_reminder` (block list, log), and the row says what was added.

## May look

The answer's own entries, and Apple Calendar for the one day an email proposes. After a click only: the Flux calendar or the "Flux demo" reminders list, through `reason/computer.py`.

## May not look

The model, the web, the rest of the bank, any other calendar day.

## Wording

- label: Suggested
- free: You're free {when}. Draft a yes to {first}?
- free_button: Draft yes
- busy: You have {clash} then ({when}). Draft a reply proposing another time?
- busy_button: Draft reply
- reply: Draft a reply to {first}: {subject}
- reply_button: Draft
- open: Open the assignment page: {title}
- open_button: Open
- calendar: Add "{title}" to your calendar: {when}
- calendar_button: Add
- remind: Remind me: {name} ({when})
- remind_button: Remind me
- added_event: Added "{title}" to your calendar for {when}.
- added_reminder: I'll remind you: {name}, {when}.
- dismissed: OK, I won't suggest that again in this chat.

## Not found

- gone: That suggestion isn't available any more.
- add_failed: That didn't work: {why}

## Never

- Never suggest from anything the answer didn't find.
- Never more than two.
- Never draft, open or send anything until the button is clicked. Nothing is ever sent.
- Never say free or busy unless both the time and the calendar were read.
- Never name a clash by anything but its title.

## Prompt

No model step.

## Examples

The checker reads the suggestion lines after the answer text. These need the demo bank with Milo's, Greta's and Ivy's meeting emails and the "Lab" event on "Flux demo" (Wed Nov 18, 1:30–3:30pm).

| question | route | answer contains |
|---|---|---|
| What did Milo ask me? | person | You're free; Draft a yes to Milo; to your calendar: Thu Nov 19 7pm |
| What did Greta ask me? | person | You have Lab then; another time |
| What did Ivy ask me? | person | Draft a reply to Ivy |
| What's due tomorrow? | due | Open the assignment page; Remind me |
