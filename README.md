# ai-hackathon-26

AI hackathon 2026. `harness/` is a Python package of short text tools that let a
small local model drive a hidden browser and native Mac apps. The model never
sees a screenshot or raw HTML; every tool answers plain text with a status line
first (`OK` / `BLOCKED` / `LOGIN` / `ERR` / `CONFIRM`), numbered lists, and a
1500-character cap. See `docs/plan/00-overview.md`.

## Computer control (`harness/computer/`)

macOS only. Six tools in `GROUPS["computer"]`:

| Tool | What it does |
|---|---|
| `app_open name` | open an app (policy-checked) |
| `file_find query` | Spotlight search, home folder only, numbered paths |
| `file_open n` | open result N |
| `ui [filter]` | numbered controls of the front window (accessibility tree) |
| `ui_click n` | press control N, returns the new window title |
| `ui_type n text` | set control N's value (keystroke fallback) |

Safety: `~/.harness/policy.json` holds `allow_apps` / `block_apps` (block always
wins) / `confirm_words`; every action is logged to `~/.harness/actions.log`; a
`~/.harness/STOP` file makes every tool answer `ERR stopped by user`. Actions
whose label contains a confirm word answer `CONFIRM <what> | call again with
token=xxxxxx`; replaying the same call with that one-time token runs it and
logs `CONFIRMED`. Needs the macOS Accessibility grant for the terminal or app
running the harness (System Settings > Privacy & Security > Accessibility).

## Development

```
uv sync
uv run pytest -q
```

Tests run offline except tasks marked `live`. Logs per branch: `docs/log/`.
