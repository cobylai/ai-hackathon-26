# feature/computer-control log

## C1 (2026-11-14)
- SPIKE: read Hermes Agent computer-use code and cua-driver README/docs; both tried live on TextEdit.
- Finding: host already AX-trusted, so both paths listed TextEdit controls with no prompts.
- Decision: thin pyobjc layer (macOS-only, text-only, ~30-line AX walk works; cua-driver adds 50 MB binary + daemon + its own TCC identity).
- Gotchas recorded in notes: pid via CGWindowList (NSRunningApplication returns -1 on macOS 27); skip palette windows.
- Added pyobjc-framework-ApplicationServices as a dev dependency for the spike; C5 promotes it if needed.

## C3 (2026-11-14)
- policy.py: ~/.harness/policy.json (allow/block/confirm_words), check() -> ALLOW/CONFIRM/DENY, actions.log, STOP file.
- Block list always beats allow_apps; confirm words matched on word boundaries ("Sender" is not "send").
- 33 table-driven tests pass, all against a tmp home; real ~/.harness untouched.

## C4 (2026-11-14)
- direct.py (open -a / mdfind -name -onlyin ~ / open, list argv only) + tools.py wrappers with status lines and cap.
- GROUPS["computer"] = [app_open, file_find, file_open] in registry; updated browser's test_registry_shape for the new seam.
- file_open(n) policy-checks the path (confirm words in file names trigger CONFIRM); every call logs to actions.log.
- 15 tests with mocked subprocess pass; manual run opened TextEdit and found a real file via Spotlight.

## C5 (2026-11-14)
- ui.py: numbered controls of the front window; pure walk() on (role, label, children) tuples + thin pyobjc fetchers.
- Front app = NSWorkspace name + CGWindowList pid (AXFocusedApplication fails outright on macOS 27); richest window wins.
- ui policy-checks the front app: Chrome frontmost -> ERR not allowed, no controls leak.
- Surprise: windows on another Space vanish from AXWindows (0 controls); a fresh document on the active Space listed 17 controls.

## C2 (2026-11-14)
- permissions.py: accessibility_ok() via AXIsProcessTrusted; ui.py now imports it (no duplicated message).
- Mocked tests cover true/false/no-pyobjc paths and the ui refusal path.
- Real check: accessibility_ok() == True on this host; no prompt needed from the user.

## C6 (2026-11-14)
- ui_click(n) = AXPress, ui_type(n, text) = set AXValue with focused-keystroke fallback; both policy-check the control label ("Delete" -> CONFIRM) and return the new window title.
- Empty text areas now listed as "(empty text area)" so they are typeable; live scenario: ui -> 18 controls, ui_type(1, "The quick brown fox...") -> OK, read back `1. textarea "The quick brown fox..."`; ui_click on "align left" OK twice.
- 13 mocked action tests pass; one full-suite run showed 9 transient Playwright fixture errors, rerun clean (111 passed).

## C7 (2026-11-14)
- scripts/eval_computer.py runs 5 TextEdit-only jobs (open, list, type, read back, read-only find); all passed, ~1.6 s total, 1901 chars to model, zero confirmations.
- Table in docs/plan/notes-computer-eval.md; created document closed without saving.

## Registry seam (2026-11-15)
- GROUPS["computer"] now exposes all six tools (ui, ui_click, ui_type added); desc budget 277 chars, well under the 400-token rule.
- pyobjc-framework-ApplicationServices promoted from dev to a darwin-only runtime dependency.
- Flaky browser tests: a timed-out pytest left orphaned Chromium processes holding the profile lock; after killing them the suite is green again (111 passed).

## Confirm tokens (2026-11-15)
- Implemented the C3 seam: CONFIRM now returns "call again with token=xxxxxx"; a one-time token (confirms.json) authorizes one exact replay, logged as CONFIRMED.
- DENY is never overruled by a token; STOP still beats everything. token arg added to app_open/file_open/ui_click/ui_type (<=3 args each).
- README stub replaced with a short tool-group + safety section.

## Port to main (2026-11-15)
- Main merged this branch at C7, then evolved (Flux). The last two commits (ui tools in registry, confirm tokens) were missing there.
- Cherry-picked both onto bionic/computer-confirm-tokens (off main); conflicts: kept main's generalized registry test and Flux README.
- 91 computer/registry tests + 11 search/no-send tests pass on main's tree; pushed for the team to merge.

## CLI (2026-11-15)
- harness/__main__.py now exposes all six computer tools (app_open/file_find/file_open/ui/ui_click/ui_type, --token where relevant); exit 0 on OK, 1 otherwise.
- 10 offline CLI tests (arg mapping, exit codes, parser coverage); live smoke: file_find OK, app_open Terminal correctly denied. Landed on main as a1e5323.

## Browser session teardown (2026-11-15, landed on main as ddd18cb)
- session.py: atexit.register(self.stop) on start; conftest.py: session-scoped finalizer stops the shared get_session browser.
- 41 browser tests pass with the change. Leak counts could not be verified: 3+ teammate pytest runs were live concurrently, contaminating before/after process snapshots.

## Teardown verification (2026-11-15)
- Controlled experiment (unique HOME profile dirs, teammate-proof): WITH the atexit fix 0 surviving Chromium processes; WITHOUT it also 0.
- Conclusion: Playwright cleans up on normal interpreter exit via the driver pipe; the fix is harmless insurance, not a bug fix.
- The earlier "leaks"/hangs trace to SIGKILLed runs (my 5-min tool timeout) and misattributed teammate processes, not to missing teardown.

## Final verification (2026-11-15)
- Full suite on main@ddd18cb (the shipped state): 295 passed, 0 failed. Includes CLI + token + computer tests.
- scripts/eval_computer.py re-run on the merged tree: all 5 jobs pass.
