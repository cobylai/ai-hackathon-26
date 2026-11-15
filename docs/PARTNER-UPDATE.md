# Update for Antranig (2026-11-14 night)

`main` now has everything: your four `feature/*` branches plus our half,
merged and tested together. Start from `main` for anything new.

## What we changed in your code (harness/)

One change, nothing else:

- **`harness/llm.py`**: `ask()` keeps its signature and `FakeLLM`, but now calls
  `llm.client.chat`, so every model call goes through the one localhost-only
  Bonsai client with the 32k check. Choices are listed in the prompt instead
  of a JSON enum. `tests/test_prompts.py` patches `client.chat` instead of httpx.
  (commit 3fd8fe6)

Everything else in `harness/` and `tests/` is exactly your branches, merged.
`registry.py`, `browser/state.py` and a few tests are the union of your branches.
Your `plan/harness-task-breakdown` branch (plans only) is not merged.

## What we added around it

- **`llm/`**: the Bonsai client. Raises unless the URL is localhost.
- **`sufficiency/`**: decides whether a web answer is good enough.
  `sufficiency/websearch.py` calls your `harness.search.engine.search` first and
  reads Bing only when yours comes back BLOCKED. No bot check is bypassed.
- **`bank/`**: the context store, a local bank of synced email and saved web
  answers (deadlines, asks, senders).
- **`reason/`**: `answer(question, today)` routes a question to due /
  person / bank / web. `python -m reason` is a chat loop, and
  `python -m reason.web` is a local chat window at http://localhost:8765.
  The due and "what did <name> ask" routes are plain code, with no model call.
- **`voice/`**: Argmax speech-to-text (`voice/listen.py`). Being wired into the
  chat loop and the window now.
- **`scripts/sync_email.py`**: your Gmail reader -> the bank. Fixed to parse
  Gmail's 24-hour dates ("14 Nov 2026, 22:24").
- **Test mail**: `scripts/demo/make_test_mail.py` (20 fake emails, 13 senders) and
  `scripts/demo/make_test_threads.py` + `sync_test_threads.py` (the same emails
  written into a saved Gmail thread page, read by your reader offline).
  Both score 36/37 on the demo questions with the network blocked.

## Changes from the original plan

- **Demo inbox**: a throwaway Gmail, `ilovelocalai@gmail.com`, not anyone's
  real mail. `docs/demo-emails.md` has 8 fake emails; 4 are signed by you.
  Please send yours from the links Coby gives you.
- **Offline**: the demo answers from the bank with Wi-Fi off. The web route
  only works online and files what it finds into the bank.
- **Person questions** ("what did X ask me") list each email's ask from code,
  because the model misread them.
- The partner tool once saved a test reply **draft** to a real person (never
  sent). `email_draft` only saves drafts; nothing sends.

## Acting route (worker 14): your tools now called, `harness/` unchanged

`reason/act.py` calls your `computer.tools.app_open`, `email.search.search` +
`last_rows`, and `email.draft.reply`, and only after the user says yes to a preview.
It saves drafts only when the Gmail tab title shows `ilovelocalai@gmail.com`. Opening a
bank link uses `computer.direct.open_path` plus `policy.log_action("Browser", "open_url", ...)`,
because no browser is on your allow list. See `docs/acting.md`.

## Computer control (worker 14, brief X): `harness/` unchanged

`reason/computer.py` reads your `computer.policy` before every action: `stopped()`, the
`block_apps` from `load_policy()`, and one `log_action` line per action ("Mail open_message",
"Calendar add_event", "Calendar show_event", "Reminders add_reminder"). The actions themselves
are AppleScript (Mail, Calendar, Reminders), because those apps can do them directly, so
`ui_click` / `ui_type` aren't used. Mail and Reminders aren't on your `allow_apps`; we use only
your block list, so nothing on it can ever be touched. See `docs/acting.md`.

## Run it

```bash
uv sync
curl -s localhost:8080/v1/models || scripts/serve_bonsai.sh 4B
FLUX_BANK_DIR=~/flux-bank uv run python -m reason.web
```

More: `docs/integration.md`, `docs/INTERFACES.md`, `docs/reasoning-layer.md`.
