# feature/email-gmail log

- E1 (check only): headless goto to `mail.google.com/mail/u/0/#inbox` classifies OK and renders 50 rows in about 1 s; the profile was already signed in.
- Found before the check: the visible login window and the hidden session used different cookie keys (macOS keychain vs mock), so the first headless launch dropped the session. Browser-core B8 (66fa981) now matches the key stores; this branch merged it.
- E2: one selector map (role/aria first, class fallback) plus `selfcheck`, which walks inbox, first thread and a blank compose; every name matched live. Two hand-made fixtures load in `tests/test_selectors.py`.
- E2 notes: Gmail keeps hidden duplicate rows and cells, hence `first_visible()`; `draft_saved_label` only exists after a save, hence `wait_for()`; Reply buttons live outside the message container.

- E3: `build()` assembles from:/quoted phrase/newer_than:/is:unread/has:attachment in a fixed order; `search_url()` percent-encodes it and an empty query maps to the inbox. 22 table cases.
