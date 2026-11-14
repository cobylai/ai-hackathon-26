# feature/email-gmail log

- E1 (check only): headless goto to `mail.google.com/mail/u/0/#inbox` classifies OK and renders 50 rows in about 1 s; the profile was already signed in.
- Found before the check: the visible login window and the hidden session used different cookie keys (macOS keychain vs mock), so the first headless launch dropped the session. Browser-core B8 (66fa981) now matches the key stores; this branch merged it.
- E2: one selector map (role/aria first, class fallback) plus `selfcheck`, which walks inbox, first thread and a blank compose; every name matched live. Two hand-made fixtures load in `tests/test_selectors.py`.
- E2 notes: Gmail keeps hidden duplicate rows and cells, hence `first_visible()`; `draft_saved_label` only exists after a save, hence `wait_for()`; Reply buttons live outside the message container.

- E3: `build()` assembles from:/quoted phrase/newer_than:/is:unread/has:attachment in a fixed order; `search_url()` percent-encodes it and an empty query maps to the inbox. 22 table cases.
- E4: `email_search` opens the `#search/` URL, waits for a settled list (Gmail keeps the old rows for a moment after the hash change), and prints up to ten `n. sender | subject | date | snippet` rows; snippet 80, cap 1500 with a hint. Order kept in `search.last_rows()` for E5.
- E4 also lands `status.signed_in()` (E1's code, because every email tool checks it first) and `GROUPS["email"]`.
- E4 live: `"ECE 4760" newer_than:30d` gives 25 results; the cap shows 7 rows plus the hint.
- E5: `email_read(n, page)` opens `#all/<id>` (reloading once when Gmail ignores the hash change), clicks folded messages open, strips quote blocks and `-- ` signatures, reverses to newest first, wraps each message in `<email from date>` and pages with B4's `paginate`.
- E5 live: a one-message thread reads cleanly; the folded-message path is covered by the fixture only, because the mailbox had no multi-message thread in reach.
