# E9 notes: email flow timings

## Safety finding (2026-11-14, after the run below)

An independent Gmail check found that the E9 draft `[harness test] eval run`
(messageId `1a1dc98297717dc9`) came back with **10 Bcc recipients** and sat in an
**old thread** (threadId `1a1af56243589841`). Cause: clicking Compose surfaced a
draft Gmail had restored, the tool typed into that window, and the restored
draft's Cc/Bcc chips came along for the ride.

Fixed in `harness/email/draft.py`:

1. Save & close any open compose window before starting a new one.
2. Refuse to type into anything that is not a blank "New Message": no recipient
   chips, no To/Cc/Bcc text, no subject, and no body beyond a `-- ` signature.
   On a restored draft the tool returns `ERR ... refused to edit a restored
   draft ...` and leaves the draft untouched.
3. After typing the To address, the recipient list must be exactly that one
   address with empty Cc and Bcc, and it is checked again before saving. If not,
   the tool stops without writing the subject or body.
4. `email_reply_draft` refuses a reply box that already has text.

Covered by fixture tests (`tests/test_draft.py`): restored draft -> ERR, extra
Bcc -> ERR, clean compose -> OK, plus unit tests for the two checks. No live run
was made after the finding, and the affected draft was left in place.

## Run

Run 2026-11-14 on the signed-in profile, one pass of search -> read -> asks -> new draft:

```
uv run python scripts/eval_email.py --sender me --days 7 --draft-to ab2864@cornell.edu
```

"Chars returned" is the length of the text each tool hands back to the model.

| step | seconds | chars returned | status | first line |
|---|---|---|---|---|
| email_search | 5.3 | 1428 | OK | `OK 48 results | from:me newer_than:7d` |
| email_read | 2.1 | 334 | OK | `OK mail.google.com | thread 1: Reach out to Watkins Glenn ...` |
| email_asks | 28.5 | 33 | OK | `OK 0 asks | from:me newer_than:7d` |
| email_draft | 1.3 | 14 | OK | `OK draft saved` |

Total 37.2 s, 1809 characters returned.

## Against the targets

- **Search and read: 7.4 s**, inside the "under 10 seconds" target.
- **Total: 1809 characters**, well under the 4000-character budget.
- **`email_asks` is the outlier at 28.5 s.** It re-runs the search and opens the top three
  threads, and each thread needs a full page load: Gmail routes threads through the URL hash,
  and a hash change leaves the previous thread on screen, so `open_thread` reloads. The 33
  characters are correct (no questions or dates in those three threads).
- The draft step saves and closes in 1.3 s; nothing is ever sent.

## Five requests

The plan wants five user-picked requests in this table. This run covered one end-to-end pass
(the orchestrator asked for a single pass). To add a row, rerun the script with the request's
fields, for example:

```
uv run python scripts/eval_email.py --sender emily --days 14
uv run python scripts/eval_email.py --text "lab safety" --days 7
```

## Drafts created by the live checks (left in place for review)

- E7: `[harness test] draft` in Drafts (to ab2864@cornell.edu).
- E8: reply draft in `What I want to talk to Aakash about`, subject `Re: ...` (same thread id).
- E9: `[harness test] eval run` in Drafts — the one with the extra Bcc recipients and the old
  thread id noted above; left untouched for the user to inspect and delete.

`in:sent subject:"[harness test]"` returns 0 results: nothing was sent.
