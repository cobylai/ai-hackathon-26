# Suggest

## For

At most two small next steps under an answer, each one line and one button, under a "Suggested" label. They come only from the entries that answer used. "Draft a reply to Greta", "You're free Thu Nov 19 at 7pm. Draft a yes to Milo?", "You have Lab then. Draft a reply proposing another time?", "Open the assignment page: Map essay". Due and catch-me-up answers show them most. Nothing happens until the button is clicked.

## Triggers

- meeting: `are you free|you free (?:for|on|at)|can (?:you|we) meet|could (?:you|we) meet|want to meet|meet up|does .{1,40}? work(?: for you)?|would .{1,40}? work(?: for you)?|are you around|are you available|available (?:on|at)`
- bare_time: `at (\d{1,2})(?::([0-5]\d))?(?!\s*(?:am|pm|a\.m|p\.m|:|\d))`

`meeting` is tried on the email's ask, subject and summary. `bare_time` reads "at 3" when no "3pm" is written.

## Steps

1. Only after a due, catchup, person, bank or followup answer. Take the bank entries that answer listed or named as its sources, in order. None: no suggestions.
2. An email with a `meeting` cue: work out the proposed day (the entry's deadlines, else `bank.dates.resolve_date` on the ask) and time (the deadline's time, else `resolve_time`, else `bare_time`: 1–7 is pm, 8–11 am, 12 noon). With both, read that day from Apple Calendar. An event (not all-day) overlapping the hour from that time is a clash: say `busy` with its title only. No clash: say `free`. No day, no time, or the calendar can't be read: go on to step 3 for this email and say nothing about free or busy.
3. Any other email with an ask: `reply`.
4. A Canvas item with a link: `open`.
5. Meeting suggestions first, then the rest in the answer's order. Skip any suggestion already dismissed, drafted or opened in this chat. Keep at most two.

## May look

The answer's own entries, and Apple Calendar for the one day an email proposes.

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
- dismissed: OK, I won't suggest that again in this chat.

## Not found

- gone: That suggestion isn't available any more.

## Never

- Never suggest from anything the answer didn't find.
- Never more than two.
- Never draft, open or send anything until the button is clicked. Nothing is ever sent.
- Never say free or busy unless both the time and the calendar were read.
- Never name a clash by anything but its title.

## Prompt

No model step.

## Examples

The checker reads the suggestion lines after the answer text. These need the demo bank with Milo's, Greta's and Ivy's meeting emails and the "Lab" event on "Muse demo" (Wed Nov 18, 1:30–3:30pm).

| question | route | answer contains |
|---|---|---|
| What did Milo ask me? | person | You're free; Draft a yes to Milo |
| What did Greta ask me? | person | You have Lab then; another time |
| What did Ivy ask me? | person | Draft a reply to Ivy |
| What's due tomorrow? | due | |
