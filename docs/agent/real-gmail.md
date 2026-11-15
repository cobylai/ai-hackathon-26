# Real Gmail sync (agent: real-gmail)

## What I built
- `bank/mailsync.py`: incremental sync of the real inbox into the bank.
  - Last 14 days, up to 200 threads (`--limit`), de-duplicated by thread id and Gmail message id
    (`gmail:<thread>:<message id>`; falls back to `#<index>` if Gmail gives no id).
  - Cursor state in `<bank>/.mailsync.json` (outside git): per-thread fingerprint (hash of the list row's
    date/snippet/subject), seen message ids, a `high_water` date and `last_run`. A second run skips unchanged
    threads and files only unseen messages; a reply adds only the reply. State holds ids and hashes, no content.
  - Resumable: `--budget SECONDS` stops cleanly, state is saved after every thread, run again to continue.
    Model errors leave the thread unmarked so it is retried; 3 errors in a row stop the run.
  - A file lock stops two syncs at once.
  - Summaries, asks and deadlines go through the existing `bank.ingest` -> `llm/client.py` -> local Bonsai only.
    Chunking stays at 6,000 tokens (`bank/extract.CHUNK_TOKENS`, test added) and the 32k guard stays in `llm/client.py`.
- `harness/email/search.collect_rows` (pages through results with Gmail's Older button, read-only),
  `harness/email/read.message_ids`, `older_button` selector.
- Entry points: `uv run python scripts/sync_email.py [days] [--limit N] [--budget S] [--every MIN]`;
  in the chat CLI type `/sync` (or `sync mail`); in the reason.web window the "Sync mail" button in the bank panel
  (`POST /sync`, `GET /sync/status`); background refresh `python -m reason.web --auto-sync-minutes N` (off by default).
  The web sync runs on the server thread (one Gmail browser), bounded to 120 s per pass, resumable.
- Safety: `live_bank_dir()` = `$FLUX_BANK_DIR` else `~/flux-bank`; any path that resolves inside the repo
  (symlinks included) is refused. Demo/test-named banks are still refused for live mail. `.gitignore` covers
  `flux-bank/`, `flux-*bank/`, `.mailsync.*`. Tests: path-inside-repo refused, gitignore check, no tracked bank files.
- The demo path (`FLUX_BANK_DIR=~/flux-demo-bank`) is untouched; playbook_check 106/106.

## How to turn it on
1. `uv run python -m harness login https://mail.google.com` once (already done by the user).
2. `uv run python scripts/sync_email.py` (real bank in `~/flux-bank`), or `uv run python -m reason.web` and press Sync mail
   with `FLUX_BANK_DIR=~/flux-bank`. Bonsai must be serving on 127.0.0.1:8080.

## Reused vs written
Reused: ideas only from OpenJarvis' Gmail IMAP connector (Apache-2.0): persisted cursor with high-water mark,
stable `gmail:<message id>` doc ids, Document-shaped records, resumable sync, reconnect/error tolerance.
No code was copied, so nothing is vendored and no THIRD_PARTY_NOTICES.md is needed. IMAP/OAuth were not used:
both need a secret the user must create. Everything else (browser path, fingerprints, lock, web/CLI hooks) is new.

## Mail.app
Not determined. This process cannot read `~/Library/Mail` or `~/Library/Accounts` (macOS TCC: "Operation not
permitted"), and querying Mail via AppleScript would raise an Automation prompt, so I did not try. If the account
is configured in Mail.app, a JXA read (`Application("Mail")` -> inbox messages with `dateReceived` in range, reading
`messageId`, `sender`, `subject`, `content`) would be faster than scraping and would give stable Message-IDs, but it needs
the user to grant Automation/Full Disk Access once. Not enabled; Flux's Mail integration only opens drafts.

## Tests
Offline suites after the change: bank 84, reason 180, sufficiency 54, applecal 10, canvas 11 (all OK); pytest 279 passed
(incl. 2 new collect_rows/message_ids tests); `FLUX_BANK_DIR=~/flux-demo-bank python -m reason.playbook_check` 106/106.
New tests: `bank/tests/test_mailsync.py` (incremental second run, reply adds only the reply, thread de-dup and limit,
budget resume, model-error retry, state holds no content, 6,000-token chunking, lock, bank-inside-repo refused,
gitignore, no tracked bank files), `reason/tests/test_web.py` (Sync mail button and /sync), `tests/test_email_collect.py`.

## Live result (one read-only run, search and read only; no compose, drafts or sends)
`sync_email.py 14 --limit 200 --budget 2400`, bank `~/flux-bank` (outside git), Bonsai on :8080.
- Threads seen: 50. Read: 44. Failed to open: 6. Messages filed: 44, all added (0 duplicates, 0 model errors).
- Time: 661.6 s total (about 15 s per thread, dominated by Gmail page loads plus Bonsai extraction).
- Only 50 threads came back, which is exactly one Gmail results page. So the "Older" paging to reach 200 did NOT
  demonstrably work live (either the inbox really had 50, or paging failed). I did not rerun (one live run allowed).
  After the run I added fallback selectors for the Older button; that change is untested live.
- The 6 unopened threads were left unmarked, so the next run retries them. The incremental second run was verified
  offline only, not live.

## Not done / risks
- 200-thread paging unverified live; Older-button selectors may need a tweak.
- Web "Sync mail" blocks the window up to 120 s per pass (single-threaded server); rerun to continue.
- Mail.app route not checked (see above). Message ids rely on Gmail's `data-legacy-message-id`; if absent, index-based ids are used.
- OpenHuman (GPL-3): no code copied, only the idea of a periodic (about 20 min) background refresh, behind `--auto-sync-minutes`.
  No third_party/ directory or THIRD_PARTY_NOTICES.md was needed.
