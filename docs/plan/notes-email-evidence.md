# Email: task → evidence

What proves each task in [03-email.md](03-email.md) is done. "Live" rows were run
against the signed-in profile; the rest run offline on fixtures.

| task | what it does | proof |
|---|---|---|
| **E1** sign-in + status | `signed_in()` loads the inbox, requires `classify()==OK` **and** a rendered list; every tool returns `LOGIN …` otherwise | `harness/email/status.py`; live inbox goto classified `OK`, 50 rows (2026-11-14 18:01); session lifetime + keychain notes in [notes-gmail-login.md](notes-gmail-login.md) |
| **E2** selectors + self-check | named selectors, role/aria before class; `python -m harness.email.selfcheck` walks inbox → thread | live self-check (6.4 s): every inbox/thread name matched (50 rows, 1 message, reply button); compose names behind `--compose`; fixtures `tests/pages/gmail_*.html` |
| **E3** query builder | `build(sender,text,days,unread,has_attachment)` + percent-encoded URL | `tests/test_query.py`, 22 table cases |
| **E4** `email_search` | numbered rows, ≤10 shown, snippet 80, 1500-char cap, order remembered | `tests/test_email_search.py`; live 25 and 50-result searches; flash-of-empty-note bug fixed with `gmail_slow_results.html` |
| **E5** `email_read` | newest first, quotes and `-- ` signatures removed, `<email from date attachments>` blocks, paged | `tests/test_email_read.py`; live 5-message thread read (7 asks), live attachment name `Myers_BME Seminar 7900 Flyer.pdf` |
| **E6** asks | pure `extract()` + `scan()` over the top 3 threads | `tests/test_asks.py` (14 sample sentences + the fixture's two asks); live `email_asks` returned 7 asks |
| **E7** new draft | blank-"New Message" check, exact one-recipient proof, `OK draft saved` | `tests/test_draft.py` (restored draft → ERR, extra Bcc → ERR, clean → OK); live `[harness test] safety recheck` in new thread `1a1dd0bbddaf656e`, To exactly the user, Cc/Bcc empty |
| **E8** reply draft | reply in thread n, recipient named in the result | `tests/test_reply_draft.py`; live reply draft in its thread with `Re:` subject and the same thread id |
| **E9** timings | five-request table, asks speedup 28.5 s → 6.4 s, replayable | [notes-email-eval.md](notes-email-eval.md); `scripts/eval_email.py --suite` |
| rules 1–3 | ≤1500 chars, status word first, numbered lists | `tests/test_email_contract.py` (all five tools in one run) |
| no send | no send path exists anywhere in `harness/` | `tests/test_no_send.py` |

Every tool is also reachable from a shell: `uv run python scripts/run_tool.py --list`.

## Caveats worth reading before calling it perfect

- The **reply recipient** is whatever the thread says (usually the other person);
  the result names it, but nothing blocks a reply to a stranger.
- Gmail **autosaves** an opened compose, so a refused draft can leave a
  signature-only "(no subject)" draft behind.
- **Attachment contents** are never read — only names.
- The **digest** is a script, not a scheduled job.
- `main` carries this work up to `ba30ba7`; the rest (digest, attachments, guards,
  hardening, self-check default, busy-profile line) is on `feature/email-gmail`.
  Merging `main` in conflicts only in `README.md`, the email log and
  `tests/test_state.py`; `harness/email/*` auto-merges.
