# Gmail sign-in notes (E1)

## How the sign-in works

`uv run python -m harness login https://mail.google.com` opens the bundled
Chromium **visibly** on `~/.harness/profile` with no automation flags, waits for
the window to close, and the hidden session reuses that profile. Cornell SSO and
Duo are completed by the user in that window.

The window is launched with `--use-mock-keychain --password-store=basic`, the
same cookie key store Playwright's hidden session uses. Without that match the
visible window encrypts cookies with the macOS keychain key, the hidden session
cannot read them, and Chrome silently drops the signed-in cookies on its first
headless launch. That is what happened on 2026-11-14 at 17:36; browser-core B8
(`66fa981`) fixed it by matching the key stores.

## Observed session lifetime

| when (ET) | what | result |
|---|---|---|
| 2026-11-14 17:29 | Cornell SSO + Duo, inbox loaded | signed in |
| 2026-11-14 17:36 | first headless launch, before the keychain fix | signed out, cookies dropped |
| 2026-11-14 ~17:45 | re-sign-in after the B8 keychain fix | signed in |
| 2026-11-14 18:01 | E1 check: inbox goto, 50 rows | signed in |
| 2026-11-14 21:31 | safety recheck draft (headless) | still signed in |
| 2026-11-14 21:37 | five-request E9 run (headless) | still signed in |

So the session survived **at least ~4 hours and a dozen headless launches**
without Duo asking again. That is a lower bound: the run ended the same evening
and nobody has watched it across days. Duo's own "remember this device" window
is the thing to watch; re-check after a night and record it here.

## What `signed_in()` checks

`harness/email/status.py` loads `mail.google.com/mail/u/0/#inbox` headless,
requires `classify()` to be `OK`, and then requires the mail list or the Compose
button to render. The second check matters: Gmail's signed-out interstitial sits
on `mail.google.com` and has no password field, so `classify()` alone reports
`OK` for it. Every email tool calls `signed_in()` first and returns
`LOGIN mail.google.com | sign-in needed | run: harness login https://mail.google.com`
when it is false.

## If Google refuses the first sign-in

The fallback in the plan is the Outlook route (`outlook.office.com`) with the
same five tools. Not built, not tested.
