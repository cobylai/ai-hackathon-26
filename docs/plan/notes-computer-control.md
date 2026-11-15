# C1 spike: reuse or write (computer control)

Written 2026-11-14, branch `feature/computer-control`. Time-boxed to 2 hours.

## Questions and answers

**What does Hermes Agent call on macOS?**
Hermes itself calls nothing OS-specific. Its `computer_use` toolset
(`tools/computer_use/cua_backend*.py`, ~430 lines plus 5 sibling modules) speaks
MCP over stdio to trycua's `cua-driver` binary; all AX/capture/input work lives
in the driver. On macOS the driver walks the AX tree via private SkyLight SPIs
and dispatches input pid-scoped via `SLPSPostEventRecordTo` (no cursor warp, no
focus steal). Hermes folds the driver's ~25 MCP tools into one `computer_use`
tool with a numbered-element list (`#N AXButton 'Back'`), the same pattern we
want — but the wrapper is sized for a large cloud model's agent loop.

**Licence.**
Hermes Agent: MIT. cua-driver: MIT. The optional `cua-perception` extension
(screenshot-to-regions) is AGPL-3.0 — we do not need it; text-only is the
default path.

**Can it list a window's controls as text without a screenshot?**
Yes. `get_window_state` with `include_screenshot:false` returns the AX tree
only, as compact Markdown (`[N] AXCheckBox (bold) [actions=[press]]`) or a
structured elements array (`tree_format:"elements"`). `max_depth` caps the
walk (default 25).

**Install size.**
Single Rust binary: 43 MB tarball, 50 MB on disk (darwin universal). Installs
to `~/.local/bin` + `~/.cua-driver`, no admin needed. Python SDK wheel ~30 MB
if we wanted in-process bindings instead of MCP.

**Cloud key / account?**
No. Runs fully local, no model artifacts, no account (Cua Spaces sign-in is
skippable). Caveat: content-free telemetry is ON by default; must set
`CUA_DRIVER_RS_TELEMETRY_ENABLED=0`.

## Hands-on test (this machine, macOS 27, TextEdit with one document)

The harness host process already has the Accessibility grant
(`AXIsProcessTrusted() == True`), so both tests ran with zero prompts.

**cua-driver (v0.49.9, `mcp --direct` mode):** listed TextEdit's document
window tree in 0.37 s — 47 elements, correctly labelled, with actions
(`[18] AXCheckBox (bold) [actions=[press]]`). Works, but: `call` needs a
running daemon and an incompatible 0.21.0 daemon (from a previous Hermes
install) was already squatting on the socket; `mcp --direct` bypasses it.
Permissions are attributed to CuaDriver.app's identity in the normal install,
so C2's permission flow would become "grant a third-party app", not "grant the
terminal that runs the harness".

**30 lines of pyobjc (`ApplicationServices` AX functions):** listed the same
controls in ~1 s as exactly our target format:

```
1. checkbox "bold"
...
7. popupbutton "typeface"
17. menubutton "document actions"
```

Two gotchas found, both solvable in a couple of lines:
- `NSRunningApplication.processIdentifier` returned -1 for TextEdit on macOS
  27; get the pid from `CGWindowListCopyWindowInfo` instead.
- `AXWindows[0]` can be a floating palette (the Siri dictation orb window)
  whose subtree is nearly empty; pick the window whose walk yields the most
  controls (or the one with a title).

## Decision: thin pyobjc layer

Scope is macOS-only, text-only, front-window control listing plus press/set —
about 150 lines of pyobjc total, with no binary to ship, no MCP plumbing, no
daemon, and a permission story (`AXIsProcessTrusted` on our own process) that
matches C2 exactly. cua-driver's real strengths — cross-platform, background
input on backgrounded/off-Space windows, snapshot token management — are out
of scope for the hackathon, and its macOS path depends on private SkyLight
SPIs that can break on OS updates. If we later need background input or
Windows/Linux, revisit wrapping cua-driver then.

C4 and C5 follow this decision: `pyobjc` (`ApplicationServices`, `Quartz`) for
the AX walk in C5; `uv` already has `pyobjc-framework-ApplicationServices` as
a dev dependency from this spike.

## Proposed, not built: ui tools in the Flux act route (2026-11-15)

The act route (`reason/act.py`) already calls `harness.computer` tools after a
user "yes" (`app_open`, `direct.open_path`) and returns `say(...)` lines. The
natural next step is three new kinds beside `open`/`calendar`/`remind`:

- `find` → `tools.file_find(name)` — answer "where is X" jobs without a model.
- `click` → `ui.ui_click(n)` — press a control from the last `ui` listing.
- `type` → `ui.ui_type(n, text)` — fill a field from the last `ui` listing.

Safety comes free: every ui action already runs the policy check with the
control's label (CONFIRM for risky labels, DENY for blocked apps, STOP file
beats all), and one-time confirm tokens (`--token`) fit the window's
Yes/Cancel flow — a "yes" could mint a token for exactly that action.

Not built now: four `agent-*` branches are live in `reason/`, so edits there
would collide, and the route's trigger wording belongs to the playbook owners.
Revisit once the agent-* branches land on main; zero overlap verified between
those branches and `harness/computer/*`, so the tools side is ready as-is.
