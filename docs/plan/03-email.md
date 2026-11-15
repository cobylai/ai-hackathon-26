# 03. Email search and drafting (`feature/email-gmail`)

Read [00-overview.md](00-overview.md) first. Needs browser-core tasks B1 to B8 merged in.

## Goal

Search Gmail, read a thread, and save a draft, all through the hidden browser after a one-time sign-in. No Gmail API, no IMAP or SMTP (Cornell blocks those). The code can save drafts. It cannot send.

## Design choices

- **Page structure, not coordinates.** The meeting notes proposed a fixed window with hard-coded button positions. Reading Gmail's page structure (rows, subject cells, message bodies) is sturdier and needs no screenshot. All selectors live in one file with a self-check command, because Gmail changes its class names.
- **Search by URL.** `https://mail.google.com/mail/u/0/#search/<query>` opens the results list directly. No clicking through the search box.
- **Code builds the Gmail query.** The model gives plain fields (`sender`, `text`, `days`); code writes `from:emily newer_than:14d homework`. The model never needs to know Gmail's search syntax.
- **Code filters before the model reads.** For "what did X ask me", code pulls sentences with question marks, dates, weekdays and times first. The model sees those lines, not whole threads.
- **Drafts only.** There is no `send` function, and a test fails if the Send button's selector appears anywhere in the package.
- **Email text is data.** Tool output wraps message text in `<email>` tags, and the email tool group contains no browsing tools, so a message cannot steer the model to a link.
- **Reference:** gmail.js (KartikTalwar/gmail.js) documents Gmail's page structure and is the place to look when a selector breaks.

## Tools this branch delivers

| Tool | Args | Returns |
|---|---|---|
| `email_search` | `sender`, `text`, `days` (all optional) | numbered rows: `n. sender | subject | date | snippet` |
| `email_read` | `n`, `page` | messages in that thread, newest first, quoted replies removed |
| `email_draft` | `to`, `subject`, `body` | `OK draft saved` (new message) |
| `email_reply_draft` | `n`, `body` | `OK draft saved` (reply in thread `n`) |
| `email_asks` | `sender`, `days` | questions and dated lines from that sender, with thread numbers |

## Tasks

### E1. Sign-in and status (HUMAN)
- **Files:** `harness/email/status.py`, `tests/test_email_status.py`, `docs/plan/notes-gmail-login.md`
- **Steps:** user runs `uv run python -m harness login https://mail.google.com` and signs in (Cornell single sign-on and Duo included). `signed_in() -> bool` loads the inbox headless and checks for the mail list, using `classify` from B6. Every email tool calls it first and returns `LOGIN run: harness login https://mail.google.com` when it fails.
- **Done when:** after sign-in, `signed_in()` is true in a fresh headless session. Record in the notes how long the session lasts before Duo asks again.
- **If Google refuses the sign-in:** stop and write it down. The fallback is the Outlook route (same tools against `outlook.office.com`), decided by the user.

### E2. Selectors file and self-check
- **Files:** `harness/email/selectors.py`, `harness/email/selfcheck.py`, `tests/pages/gmail_list.html`, `tests/pages/gmail_thread.html`
- **Steps:** one dict of named selectors: `list_row`, `row_sender`, `row_subject`, `row_snippet`, `row_date`, `thread_message`, `message_sender`, `message_date`, `message_body`, `quoted_text`, `compose_button`, `compose_to`, `compose_subject`, `compose_body`, `draft_saved_label`, `reply_button`. Prefer `role` and `aria-label` attributes over class names; list a class-name fallback second. `selfcheck` opens the live inbox and reports which names match zero elements. Build the two fixture pages by hand with **made-up** mail that mirrors the real structure. Never commit real email.
- **Done when:** `uv run python -m harness.email.selfcheck` prints all names as found on the live inbox (HUMAN to run), and the fixtures load in a test.

### E3. Query builder
- **Files:** `harness/email/query.py`, `tests/test_query.py`
- **Steps:** `build(sender=None, text=None, days=None, unread=False, has_attachment=False) -> str`. Quote multi-word text. `search_url(query)` percent-encodes it into the `#search/` URL.
- **Done when:** table-driven tests cover each field alone and combined.

### E4. `email_search`
- **Files:** `harness/email/search.py`, `harness/email/tools.py`, `harness/registry.py` (add `GROUPS["email"]`), `tests/test_email_search.py`
- **Steps:** open the search URL, wait for rows or the "no messages" text, parse up to 10 rows, format within the cap (snippet cut to 80 characters), remember row order for the session.
- **Done when:** fixture test returns the expected numbered rows; an empty result returns `OK 0 results`.

### E5. `email_read`
- **Files:** `harness/email/read.py`, `tests/test_email_read.py`
- **Steps:** open thread `n` from the last search, expand collapsed messages, read sender, date and body for each. Remove quoted replies and signatures after `-- `. Wrap as `<email from="..." date="...">text</email>`. Paginate with B4's `paginate`.
- **Done when:** on the thread fixture, quoted text is gone, messages are newest first, and each page is within the cap.

### E6. Asks extractor
- **Files:** `harness/email/asks.py`, `tests/test_asks.py`
- **Steps:** pure text function `extract(text) -> list[str]`: sentences that contain `?`, a weekday name, a month and day, a clock time, or words such as `due`, `by`, `deadline`, `can you`, `could you`, `please`. `email_asks(sender, days)` runs search, reads the top 3 threads, and returns the extracted lines tagged with the thread number.
- **Done when:** unit tests on 10 sample sentences pass, and the fixture thread yields its two known asks.

### E7. New draft
- **Files:** `harness/email/draft.py`, `tests/test_draft.py`, `tests/test_no_send.py`
- **Steps:** click Compose, fill To, Subject and Body by selector, wait for the "Draft saved" label, close the compose window with its close button. Return `OK draft saved` or `ERR <reason>`. `test_no_send.py` greps the package for the Send button's label and selector and fails if found.
- **Done when:** fixture test passes; HUMAN confirms one real draft appears in the Drafts folder and nothing was sent.

### E8. Reply draft
- **Files:** `harness/email/draft.py` (add), `tests/test_reply_draft.py`
- **Steps:** open thread `n`, click Reply, type the body, wait for "Draft saved", close.
- **Done when:** fixture test passes; HUMAN confirms the draft sits in the right thread.

### E9. Live check (live, HUMAN)
- **Files:** `scripts/eval_email.py`, `docs/plan/notes-email-eval.md`
- **Steps:** five real requests the user picks, for example "what did <name> ask me this week" and "draft a reply saying I can meet Tuesday". Log time, characters sent to the model, and whether the user accepts the result.
- **Done when:** the notes file has the table. Target: under 10 seconds per search-and-read, under 4000 characters of model input.

## Later, not now

- Outlook web with the same five tools.
- Attachments.
- A daily digest run (question marks and dates across the inbox), matching the teammate's automation template.
