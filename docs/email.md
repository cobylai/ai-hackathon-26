# Email tools (`feature/email-gmail`)

Short plain-text Gmail tools for a small local model. The model never sees a
screenshot or raw HTML: each tool returns at most 1500 characters, starts with
`OK`, `BLOCKED`, `LOGIN` or `ERR`, and lists things as numbers it can pick.

## One-time sign-in

```bash
uv run python -m harness login https://mail.google.com
```

Opens a plain Chromium on `~/.harness/profile` (no automation flags); finish
Cornell SSO and Duo, then close the window. The hidden session reuses the
profile. How long that lasts, and why the cookie key store has to match:
[docs/plan/notes-gmail-login.md](plan/notes-gmail-login.md).

## Tools

| tool | args | returns |
|---|---|---|
| `email_search` | `sender`, `text`, `days` | numbered rows: `n. sender \| subject \| date \| snippet` |
| `email_read` | `n`, `page` | messages newest first, quoted replies and signatures removed, wrapped in `<email from date attachments>` |
| `email_asks` | `sender`, `days` | questions and dated lines from the top 3 threads, tagged with the thread number |
| `email_draft` | `to`, `subject`, `body` | `OK draft saved` (new draft) |
| `email_reply_draft` | `n`, `body` | `OK draft saved \| to <address>` (reply in thread `n`) |

`GROUPS["email"]` in `harness/registry.py` contains only these five, so an email
tool group can never hand the model a browsing tool while it reads a message.

### There is no send function

`tests/test_no_send.py` fails if a Send label, selector, function or tool name
appears anywhere in `harness/`. Drafts are the only thing these tools create.

### Draft safety

Gmail can restore a draft from an earlier session, and a Compose click may
surface it. `harness/email/draft.py` therefore:

- closes open compose windows (unchanged) before starting;
- refuses anything that is not a blank "New Message" — no To/Cc/Bcc addresses,
  no subject, no body beyond a `-- ` signature — and leaves it alone;
- types the address, then requires the recipient list to be exactly that one
  address with empty Cc and Bcc, checking again before saving;
- refuses a reply box that already has text, and reports who a reply is
  addressed to (a reply goes to whoever the thread says).

Every email tool calls `signed_in()` first and returns
`LOGIN mail.google.com | sign-in needed | run: harness login https://mail.google.com`
instead of treating a sign-in page as mail.

## Checking Gmail's page structure

All selectors live in `harness/email/selectors.py` (role/aria first, Gmail class
as the fallback). Gmail changes them; the self-check walks the live inbox, the
first thread and a blank compose and prints a count per name:

```bash
uv run python -m harness.email.selfcheck
```

By default it only reads the inbox and the first thread, so it writes nothing.
`--compose` also opens a blank compose to check the compose selectors; if your
account inserts a signature, Gmail saves it as a draft, so that step is opt-in.

## Timings

```bash
# the five-request table from the plan, read-only
uv run python scripts/eval_email.py --suite --sender me --text "ECE 4760" --days 7

# one flow, optionally saving a test draft
uv run python scripts/eval_email.py --sender me --days 7
uv run python scripts/eval_email.py --text "lab safety" --days 14 --draft-to you@example.edu
```

Live results, the asks speedup, and the safety findings:
[docs/plan/notes-email-eval.md](plan/notes-email-eval.md).

## Daily digest

```bash
uv run python scripts/daily_digest.py --days 1 --limit 8
```

Read-only: searches the last N days, opens the newest threads the fast way, and
prints questions and dated lines grouped by thread. It reuses the same `scan()`
as `email_asks`, so it inherits the login check and the 1500-character cap.
Nothing is drafted or sent.

### Unattended

Exit codes: `0` a digest was produced, `1` the digest line is `LOGIN`/`ERR`
(sign in, or retry), `2` the browser could not start (usually because
another process holds `~/.harness/profile`). A locked profile prints one line,
not a traceback, so a scheduler can retry quietly.

```cron
# weekdays at 07:30; keep each day's digest, note failures
30 7 * * 1-5 cd /path/to/harness && uv run python scripts/daily_digest.py --days 1 --output ~/digest-$(date +\%F).txt || echo "digest failed" >> ~/digest.log
```

launchd works the same way. The script never prompts and never writes mail, so
it needs no babysitting once the profile is signed in.

## Known gaps

- Attachment **contents** are not read. Names do come through
  (`<email ... attachments="a.pdf; b.png">`), taken from Gmail's chips.
- **Outlook web** is not implemented (the plan's fallback if Google refuses sign-in).
- A digest script exists (`scripts/daily_digest.py`), but nothing schedules it
  and it is not yet wired into the teammate's automation template.
- A reply is addressed to whoever the thread says (usually the other
  participant). The result names that address, but the tool will not stop a
  reply to a stranger.
- Gmail autosaves an opened compose, so a draft attempt refused after Compose
  opens can leave a signature-only "(no subject)" draft in Drafts. The
  self-check's compose step is opt-in for the same reason.

## Tests

```bash
uv run pytest -q
```

Tests run offline against hand-made fixture pages in `tests/pages/`; no real mail
is committed. Fixtures cover the inbox list, a thread with a folded message and a
quoted reply, an empty result, a restored draft and a compose that smuggles in an
extra Bcc.
