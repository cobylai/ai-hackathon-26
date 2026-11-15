# E9 notes: email flow timings

## Safety findings

**1. E9 draft edited a restored draft (2026-11-14).** An independent Gmail check
found the E9 draft `[harness test] eval run` (messageId `1a1dc98297717dc9`) with
**10 Bcc recipients**, filed in an old thread (`1a1af56243589841`). Clicking
Compose surfaced a draft Gmail had restored, and the tool typed into it; the
restored draft's Cc/Bcc chips came along.

Fixed in `harness/email/draft.py`: close open composes first; refuse anything
that is not a blank "New Message" (no To/Cc/Bcc addresses, no subject, no body
beyond a `-- ` signature); require the recipient list to be exactly the one
requested address with empty Cc/Bcc, checked after typing the address and again
before saving; `email_reply_draft` refuses a reply box that already has text.
Verified live: `[harness test] safety recheck` landed in a new thread
(`1a1dd0bbddaf656e`) with To exactly `ab2864@cornell.edu` and empty Cc/Bcc, and
the restored-draft fixture returns `ERR ... refused to edit a restored draft ...`.

**2. Reply draft addressed a third party (2026-11-14).** The reply step below
was run on a thread the user had sent, so Gmail's Reply addressed the other
participant (`alp267@cornell.edu`), not the user. It was never sent and is left
in Drafts for the user to delete, but it broke the "recipient only the user's
own address" limit. `email_reply_draft` now returns its recipient
(`OK draft saved | to <address>`) so this is visible instead of silent.

## Five requests (live, 2026-11-14)

"Chars" is what the tool returned to the model for that request (all steps).

| # | request | steps | total s | chars | status |
|---|---|---|---|---|---|
| 1 | sender search `from:me newer_than:7d` | `email_search` 4.2 s | 4.2 | 1387 | OK 50 results |
| 2 | text search `"ECE 4760" newer_than:30d` | `email_search` 2.5 s | 2.5 | 1417 | OK 25 results |
| 3 | date-bounded search `newer_than:1d` | `email_search` 2.1 s | 2.1 | 1387 | OK 25 results |
| 4 | read the `BME 3030` thread | `email_search` 2.2 s + `email_read(1)` 2.1 s | 4.3 | 1719 | OK, thread 1 |
| 5 | asks `from:me newer_than:7d` | `email_asks` 5.6 s | 5.6 | 336 | OK 7 asks |
| 6 | reply draft (write) in `BME 3030 Sign Up Notification` | `email_reply_draft` 10.8 s (one attempt hit a scheduled-send thread with no reply box) | 10.8 | 14 | OK draft saved |

Before/after the asks speedup (same query, same session):

| `email_asks(from:me newer_than:7d)` | seconds |
|---|---|
| before (URL + full reload per thread) | 28.5 |
| after (click the result row, in-app render) | 6.4 |

The speedup clicks the row (matched by thread id), checks the tab title against
the row subject, skips draft rows, and falls back to the URL + reload path only
if the click path does not render the right thread. `tests/test_asks.py` covers
both the click path (with the reload path made to fail) and the title guard.

## Against the targets

- Every request is **under 10 seconds**; the slowest read-only one is 5.6 s, and
  search+read is 4.3 s.
- Characters returned range **336 to 1719**, well under the 4000 budget.
- To regenerate this table in one read-only run:

  ```
  uv run python scripts/eval_email.py --suite --sender me --text "ECE 4760" --days 7
  ```

  It writes nothing; use the single-flow mode with `--draft-to <address>` if a
  draft step is wanted.

## Drafts in the account after these runs (none deleted)

- `[harness test] draft` (E7)
- `[harness test] eval run` (E9 — the one with the extra Bcc; left for inspection)
- `Re: What I want to talk to Aakash about` (E8 reply draft, to the user)
- `[harness test] safety recheck` (E7 recheck, new thread, one recipient)
- `Re: BME 3030 Sign Up Notification: Addison Pressley` (E9 reply draft, addressed
  to `alp267@cornell.edu` — see finding 2)
- two signature-only "(no subject)" drafts from failed attempts

`in:sent subject:"[harness test]"` returns 0 results: nothing was sent.
