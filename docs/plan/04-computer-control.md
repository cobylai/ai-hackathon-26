# 04. Computer control (`feature/computer-control`)

Read [00-overview.md](00-overview.md) first. Needs only the scaffold (B1) and the registry shape (B7). macOS only for the hackathon.

## Goal

Let the model open apps and files and press buttons in native Mac apps, using text only, with firm limits on what it may touch.

## Design choices

- **Three tiers, cheapest first.**
  1. *Direct commands:* open an app, open a file, find a file. One call, no reading of the screen.
  2. *Accessibility tree:* macOS exposes every window as a tree of labelled buttons, fields and menus. List them as numbered text, the same pattern as the browser's `elements`. The model picks a number.
  3. *Pixels and screenshots:* not built. Too slow and too large for a small local model.
- **Reuse first.** Hermes Agent (MIT) ships a computer-use toolset, reported to call trycua's `cua-driver` over MCP and to work in the background through the accessibility stack. Task C1 checks that and decides between wrapping it and writing a thin layer on `pyobjc`. Other references: browser-use's `macOS-use`, Open Interpreter.
- **Web pages stay in the hidden browser.** Computer control is for native apps. It never drives the user's Chrome.
- **Safety is part of the feature**, not a follow-up: app allowlist, blocked apps, confirmation for risky actions, an action log, a stop file.

## Tools this branch delivers

| Tool | Args | Returns |
|---|---|---|
| `app_open` | `name` | status line |
| `file_find` | `query` | numbered paths (Spotlight) |
| `file_open` | `n` | status line |
| `ui` | `filter` (optional word) | numbered controls of the front window |
| `ui_click` | `n` | status line, then window title |
| `ui_type` | `n`, `text` | status line |

## Tasks

### C1. SPIKE: reuse or write (2 hours at most)
- **Files:** `docs/plan/notes-computer-control.md`
- **Steps:** read the Hermes Agent repo's computer-use code and the `cua-driver` README. Answer: what does it call on macOS, what is the licence, can it list a window's controls as text without a screenshot, how large is the install, does it run without a cloud key. Try listing TextEdit's controls with it and with 30 lines of `pyobjc` (`ApplicationServices` AX functions).
- **Done when:** the notes end with one decision, "wrap cua-driver" or "thin pyobjc layer", and the reason. Tasks C4 and C5 follow that decision.

### C2. Permission check (HUMAN)
- **Files:** `harness/computer/permissions.py`, `tests/test_permissions.py`
- **Steps:** `accessibility_ok() -> bool` using `AXIsProcessTrusted`. When false, tools return `ERR accessibility permission needed: System Settings > Privacy & Security > Accessibility`. The user grants it once to the terminal or app that runs the harness.
- **Done when:** returns true after the user grants permission; the test covers the false path with a mock.

### C3. Policy and log
- **Files:** `harness/computer/policy.py`, `tests/test_policy.py`
- **Steps:** `~/.harness/policy.json` with `allow_apps` (default: Finder, TextEdit, Notes, Calendar, Preview, Calculator), `block_apps` (always: System Settings, Keychain Access, Terminal, password managers, banking apps; cannot be overridden by `allow_apps`), and `confirm_words` (`delete`, `remove`, `send`, `pay`, `buy`, `erase`, `empty trash`). `check(app, action, label) -> "ALLOW" | "CONFIRM" | "DENY"`. Every action appends one line to `~/.harness/actions.log`. If `~/.harness/STOP` exists, every tool returns `ERR stopped by user`.
- **Done when:** table-driven tests cover allow, deny, confirm and the stop file.
- **Seam:** `CONFIRM` returns `CONFIRM <what>` to the caller. The reasoning layer or UI asks the user; the tool is then called again with a one-time token.

### C4. Direct commands
- **Files:** `harness/computer/direct.py`, `harness/computer/tools.py`, `harness/registry.py` (add `GROUPS["computer"]`), `tests/test_direct.py`
- **Steps:** `app_open` via `open -a` (after the policy check). `file_find` via `mdfind -name`, limited to the home folder, at most 10 numbered results, hidden and Library paths dropped. `file_open(n)` via `open`. Arguments are passed as a list to `subprocess.run`, never through a shell string.
- **Done when:** tests with mocked `subprocess` pass, and a manual run opens TextEdit.

### C5. Numbered controls
- **Files:** `harness/computer/ui.py`, `tests/test_ui.py`
- **Steps:** per the C1 decision, walk the front window's accessibility tree to depth 8. Keep buttons, text fields, checkboxes, menu items, links and tabs that have a title, description or value. Output `n. button "Save"`, at most 40 lines, within the cap. `filter` keeps lines containing that word. Remember the mapping for the session.
- **Done when:** a unit test on a fake tree passes, and a manual run on TextEdit lists its controls.

### C6. Click and type
- **Files:** `harness/computer/ui.py` (add), `tests/test_ui_actions.py`
- **Steps:** `ui_click(n)` performs the control's press action. `ui_type(n, text)` sets the field's value, falling back to focused keystrokes. Both run the policy check with the control's label, so "Delete" needs confirmation. After acting, return the new window title.
- **Done when:** scripted manual scenario: open TextEdit, new document, type a sentence, read it back with `ui`. Write the transcript into the branch log.

### C7. Live check (live, HUMAN)
- **Files:** `scripts/eval_computer.py`, `docs/plan/notes-computer-eval.md`
- **Steps:** five small jobs, for example "open my most recent PDF about X", "add a note saying Y", "what is on my calendar window". Log calls made, characters sent to the model, time, and outcome.
- **Done when:** the notes file has the table.

## Later, not now

- Windows and Linux.
- Menu bar and multi-window handling.
- A per-app recipe file ("in Notes, new note is this control") so common jobs skip the `ui` listing.
