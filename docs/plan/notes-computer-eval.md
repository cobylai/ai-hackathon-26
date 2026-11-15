# C7 live check: computer control

Run 2026-11-14 (America/New_York) on macOS 27, branch `feature/computer-control`,
via `uv run python scripts/eval_computer.py`. Scope per authorization: TextEdit
only from the app allowlist plus a read-only Spotlight search; the only text
typed was the test sentence, into a fresh document closed WITHOUT saving at the
end. The user did not touch the keyboard during the run.

| job | calls | chars to model | time (s) | outcome |
|---|---|---|---|---|
| open TextEdit, new document | 1 | 18 | 0.9 | pass |
| what is on my TextEdit window | 1 | 519 | 0.5 | pass |
| add a note saying the test sentence | 2 | 577 | 0.0 | pass |
| read the note back | 1 | 96 | 0.0 | pass |
| find files named 'harness' (read-only) | 1 | 691 | 0.2 | pass |

Totals: 6 tool calls, 1901 characters returned to the model, ~1.6 s of tool
time. All five jobs passed.

## Confirmations

None. No job touched a confirm word (`delete`, `remove`, `send`, `pay`, `buy`,
`erase`, `empty trash`) or a blocked app, so `policy.check` returned ALLOW for
every action; `~/.harness/actions.log` has one line per call, all ALLOW.

## Notes

- The read-back job used `ui` with the filter `quick`, which cut the model-facing
  text from 519 to 96 characters — the filter argument earns its keep.
- Verification came from the accessibility tree itself: after `ui_type`, the
  text area's value read back as the full sentence.
- Observed earlier, still true: TextEdit windows on another Space are invisible
  to the AX tree; the eval makes a fresh document on the active Space to avoid it.
