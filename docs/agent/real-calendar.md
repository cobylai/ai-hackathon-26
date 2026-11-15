# Real calendar (agent: real-calendar)

## Built
- `FLUX_CALENDARS=all` makes `applecal.events()` read every real Apple Calendar through EventKit (`applecal/eventkit_read.swift`, compiled once into `~/.flux/bin`, run as a read-only subprocess that prints JSON; `applecal/real.py` wraps it). EventKit's occurrence predicate expands repeating events, so each occurrence in the window appears (this week / next meeting / am I free Monday).
- Calendar filter in `~/.flux/calendars.json` (outside git; override path with `FLUX_CALENDARS_CONFIG`):
  `{"allow": ["Work"], "deny": ["X"], "include_subscribed": false, "include_birthdays": false}`. Default: all calendars except subscribed, holiday-named and birthday calendars. `allow` (non-empty) = only those; `deny` always wins. Bad or missing file = defaults.
- Time zones: timed events are converted from their absolute instant to the Mac's zone. All-day events run midnight to the midnight after their last day (multi-day included).
- Answers cite the calendar: with `all`, each row ends `[Calendar]` and the source line names the calendars shown (`Source: Apple Calendar (Home, Work)`). Followups and catch-up use the same label. Wording line `row_cal` added to `playbooks/calendar.md`.
- Writes unchanged: event and reminder creation still go only to "Flux demo", confirm-first. `write.add_event` additionally refuses any other calendar when `FLUX_CALENDARS=all`.
- Default is `FLUX_CALENDARS=demo` (or unset): the old osascript path, "Flux demo" only, identical output.

## How to enable
1. `export FLUX_CALENDARS=all` in the shell that runs `python -m reason` / `reason.web`. First run compiles the helper (needs Xcode command line tools, `swiftc`).
2. macOS permission (must be done by the user, not grantable by an agent): the first read shows "<terminal app> would like to access your calendar" -> click **Allow Full Access**. If dismissed: System Settings > Privacy & Security > Calendars > turn on the terminal app (Terminal / iTerm / VS Code) and re-run. Without it Flux answers "I couldn't read Apple Calendar (no permission to read Calendar ...)".
3. Optional: create `~/.flux/calendars.json` as above.

## Tests
- `applecal` 25 tests (14 new in `test_real.py`: filtering, allow/deny, recurrence, all-day, time zone, windows, denied, mode default, writes restricted), `reason` 180 (2 new), `bank` 54, `sufficiency` 72, `canvas` OK, `pytest -q` 275 passed, `playbook_check` 106/106 with the demo bank. All offline, EventKit mocked with fake events.

## Live check
One read-only call, `FLUX_CALENDARS=all`, this week: **blocked by permission** (denied; the Calendar prompt could not be granted from here). No counts available. Please grant access as above and run once: `FLUX_CALENDARS=all uv run python -m reason`, ask "what's on my calendar this week".

## Reused vs written
- Written by me: everything above. No code copied; nothing vendored, so no `third_party/` or `THIRD_PARTY_NOTICES.md`.
- Looked at: open-jarvis/OpenJarvis `connectors/apple_calendar.py` (Apache-2.0, commit 77bff25). Borrowed only ideas: it reads `Calendar.sqlitedb` (needs Full Disk Access, private schema, OccurrenceCache for repeats, `_float` timezone = floating all-day). I kept EventKit as primary (public API, Calendar permission only, real occurrence expansion). Not vendored as a fallback: schema is undocumented and Full Disk Access is a heavier grant. Did not review BRO3886/ical.

## Not done
- Live verification against the real calendar (permission).
- sqlite fallback reader. Per-event de-duplication across calendars (same invite on two accounts shows twice). Free/busy ignores declined status. Time zone of events is shown in local time only (no "(Pacific)" suffix). Meeting-clash suggestions in mail use all calendars in `all` mode.
- Swift helper is unsigned; if macOS ties the permission to the terminal and not the helper, step 2 may need the terminal app entry.
