# feature/email-gmail log

- E1 (check only): headless goto to `mail.google.com/mail/u/0/#inbox` classifies OK and renders 50 rows in about 1 s; the profile was already signed in.
- Found before the check: the visible login window and the hidden session used different cookie keys (macOS keychain vs mock), so the first headless launch dropped the session. Browser-core B8 (66fa981) now matches the key stores; this branch merged it.
