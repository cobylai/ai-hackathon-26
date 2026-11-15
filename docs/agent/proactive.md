# Proactive nudges (Flux speaks first)

Branch `feature/agent-proactive`. Code-only rules, no model call, no network. Default OFF.

## Built
- `proactive/rules.py`: pure `nudges(now, bank, calendar_events, state, config) -> [Nudge(id, kind, text, source, due_at)]`. Kinds: `deadline` (bank deadline with a time within 4 h, or dated today), `event` (calendar event starting within 30 min), `ask` (email ask 3 to 14 days old, deadline not passed; wording "asked you something N days ago; check whether it's still open", because the bank has no replied flag). Quiet hours (22:00 to 08:00), per-kind on/off, max per hour (default 3; nudges already shown stay on the strip), dismiss and snooze filtering. Fake clock = pass `now`.
- `proactive/state.py`: `~/.flux/nudges.json` (outside git; `FLUX_NUDGES_FILE` overrides): `config`, `shown`, `dismissed`, `snoozed`. `poll()` computes, records what is new, optionally notifies with `osascript display notification` (text passed as an argument, not spliced into the script).
- `proactive/live.py`: reads bank + Apple Calendar for one poll; `start_poller()` runs it every 60 s on the vendored OpenJarvis scheduler.
- Server (`reason/web.py`): `GET /nudges` -> `{enabled, nudges}`, `POST /nudges/dismiss {id, snooze_minutes?}`; a dismissible strip above the chat log (hidden when empty or disabled), each nudge shows "From <source>".
- Mac app (`app/Flux.swift`): polls `/nudges` every 60 s and posts a notification once per id. `app/build.sh` still builds (checked).
- Safety: nudge text is a code template plus sender / subject / deadline phrase as single-line, capped, quoted data. Nothing is executed or passed to a model; email text is never an instruction. Each nudge cites its source entry.

## Enable
`FLUX_NUDGES=1` on the window server turns the endpoint and strip on (and the Mac app's polling then notifies). Without it `/nudges` returns `{"enabled": false, "nudges": []}`, so the demo and recording are unchanged. `FLUX_NUDGES_OSASCRIPT=1` (with `FLUX_NUDGES=1`) also starts the server-side poller that posts macOS notifications itself; use this or the Mac app, not both, to avoid double notices. Config example in `~/.flux/nudges.json`: `{"config": {"max_per_hour": 2, "quiet_start": "21:00", "kinds": {"ask": false}}}`.

## Reused vs written
- Reused (Apache-2.0, vendored): `third_party/openjarvis_scheduler/` = OpenJarvis `scheduler.py` + `store.py` (interval/cron/once tasks, background polling, SQLite store), commit in `THIRD_PARTY_NOTICES.md`. Edits: import path; a task runs a callable. We use only interval tasks (cron needs croniter, not installed).
- Written by us: the rules, dedupe/quiet-hours/rate-limit state, server and page, Swift hook, tests.

## Tests
`uv run python -m unittest discover proactive/tests`: 19 tests (rules, quiet hours, kinds, dismiss/snooze, rate limit, injection text, state file, osascript called once, HTTP endpoints, default off, scheduler poller). All offline.
Existing suites: reason 178, bank 72, sufficiency 54, applecal 10, canvas 11 OK; pytest and playbook_check 106/106 see the report.

## Not done
- No "replied" detection for asks (bank has no flag); the ask nudge may fire for a handled mail. Dismiss hides it.
- Deadlines without a time nudge only on the day. No snooze button in the strip (API supports it).
- Notification click does nothing; not tested on a live Mac session with real notification permission.
