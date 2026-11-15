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
| `email_read` | `n`, `page` | messages newest first, quoted replies and signatures removed, wrapped in `<email from date>` |
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

It opens a blank compose and closes it again. If the account inserts a signature
into new messages, Gmail saves that signature as a draft — so an occasional
"(no subject)" draft in Drafts is expected, not a bug in the tool.

## Timings

```bash
uv run python scripts/eval_email.py --sender me --days 7
uv run python scripts/eval_email.py --text "lab safety" --days 14 --draft-to you@example.edu
```

Live results, the asks speedup, and the safety findings:
[docs/plan/notes-email-eval.md](plan/notes-email-eval.md).

## Tests

```bash
uv run pytest -q
```

Tests run offline against hand-made fixture pages in `tests/pages/`; no real mail
is committed. Fixtures cover the inbox list, a thread with a folded message and a
quoted reply, an empty result, a restored draft and a compose that smuggles in an
extra Bcc.
