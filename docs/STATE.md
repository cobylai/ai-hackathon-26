# Flux: state of the project (2026-11-15, before the video)

One page to pick the project back up. Details are in the linked docs.

## What Flux is

A local Mac assistant. Every model call goes to Bonsai 2 4B on localhost
(`llm/client.py`), voice is Argmax Whisper large-v3 turbo, and it works with
Wi-Fi off, answering from a local bank of mail, coursework, notes about you and
Apple Calendar. See `README.md` and `docs/INTERFACES.md`.

## Built (all on `main`, tests passing)

| Area | Where | Doc |
|---|---|---|
| Bonsai client, 32k guard | `llm/` | bonsai-client.md |
| Bank (mail, Canvas, notes, people), whole-word search | `bank/` | context-store.md |
| Web route: gather, judge, Bing/Wikipedia, bot-page guard | `sufficiency/` | sufficiency-check.md |
| Routes: due, person, calendar, memory, catch me up, chit-chat, web, offline | `reason/` | reasoning-layer.md |
| Playbooks (guardrails) + checker | `playbooks/`, `reason/playbook_check.py` | playbooks/RULES.md |
| Follow-ups, saved chats, Speak | `reason/session.py`, `reason/chats.py`, `reason/speak.py` | reasoning-layer.md |
| Discovery (asks before it learns) | `discover/` | reasoning-layer.md |
| Apple Calendar + Reminders | `applecal/` | calendar.md |
| Mock Canvas | `canvas/`, `scripts/*canvas*` | canvas.md |
| Acting, computer control, suggestions, reply drafts, compose | `reason/act.py`, `computer.py`, `suggest.py`, `compose.py` | acting.md |
| Voice (Argmax) | `voice/` | voice-input.md, argmax.md |
| Window + Mac app (Fn-Space, setup window, signed/notarized DMG) | `reason/web.py`, `app/` | window.md |
| Gmail sync + page fixtures | `scripts/sync_email.py`, `scripts/*test_threads*` | integration.md |
| Partner's harness (browser, search, Gmail, computer control) | `harness/` | PARTNER-UPDATE.md |

Scores on `~/flux-demo-bank` (`--today 2026-11-15`, offline): playbook_check
106/106, brief M 37/38 (known miss: hackathon team-name options).

## Where things live on Coby's Mac

- Banks: `~/flux-demo-bank` (sample mail + Canvas), `~/flux-bank` (real sync); chats in `~/flux-chats`.
- Backups: `~/flux-migration-backup-*.tgz`, `~/flux-demo-bank.bak-*`, `~/flux-chats-test-backup-*.tgz`.
- Demo calendar and Reminders list: "Flux demo".
- Keychain: "Flux Argmax key". Notary profile: `Flux-notarize`. Bitwarden: "Apple app-specific password - Flux notarize".

## Releases

- Notarized DMG live at https://cobydev.com/flux/download (cobydev branch `feature/flux-page`, deployed, **not merged** to cobydev main; pages unpublished, so `/flux/privacy` 404s).
- Test build on the private GitHub release `v0.1-test` (Flux.dmg, with the repo URL).

## Open before submitting

- Icon B + 4-screen in-app install wizard (worker 16): approved direction, building.
- Publish the cobydev Flux pages (privacy is linked from the app) and merge `feature/flux-page`.
- Antranig: final test round (`docs/PARTNER-TESTING-FINAL.md`), including the real Wi-Fi-off voice run.
- Judges' access to the repo (private; history notes in `docs/submission.md`).
- The demo video (scripted capture, zooms, voice-over), then the Discord post (`docs/submission.md`).

## Later

- A clean new public repo for Flux (Coby, after the hackathon).
- Sparkle auto-updates (needs the app to carry its code, not just launch a checkout).
- Use what I'm looking at (read the front window), learned schedule, proactive nudges, live Canvas sync.
