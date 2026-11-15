# Bot-wall rate, live (B9)

One run per engine, 2026-11-14, macOS, headless full Chromium (`channel="chromium"`, temp persistent profile), `domcontentloaded` + 1.2 s settle, 20 s timeout. Status is `harness.browser.state.classify()`; no challenge was solved or bypassed. Plain Playwright 1.65.2 (Chromium 159) vs patchright 1.64.4 (Chromium 156, its own browser build).

| site | playwright | http | s | patchright | http | s |
|---|---|---|---|---|---|---|
| reddit | BLOCKED | 200 | 0.21 | BLOCKED | 200 | 0.19 |
| wikipedia | OK | 200 | 0.45 | OK | 200 | 0.36 |
| bbc-news | OK | 200 | 0.46 | OK | 200 | 0.43 |
| weather.com | BLOCKED | 200 | 0.27 | OK | 200 | 0.21 |
| stackoverflow | ERR | 403 | 0.10 | BLOCKED | 403 | 0.11 |
| github | OK | 200 | 0.56 | OK | 200 | 0.44 |
| youtube | OK | 200 | 0.99 | OK | 200 | 0.90 |
| amazon | OK | 202 | 0.35 | OK | 202 | 0.23 |
| google | OK | 200 | 0.42 | OK | 200 | 0.32 |
| x | ERR | – | 0.19 | ERR | – | 0.13 |
| linkedin | ERR | 403 | 0.10 | BLOCKED | 403 | 0.18 |
| instagram | LOGIN | 200 | 0.47 | LOGIN | 200 | 0.49 |
| hacker-news | OK | 200 | 0.37 | OK | 200 | 0.41 |
| nytimes | OK | 200 | 0.90 | OK | 200 | 0.83 |
| craigslist | OK | 200 | 0.34 | OK | 200 | 0.23 |

Playwright: 2 BLOCKED + 3 ERR = **5 of 15 unusable**, median 0.37 s.
Patchright: 3 BLOCKED + 1 ERR = **4 of 15 unusable**, median 0.32 s.

## What actually differs

- **weather.com**: the only site that got through with patchright but not with Playwright. The plain run was labelled BLOCKED on a normal 200 page whose title was the ordinary weather.com title, so that label may be a false positive from a stray phrase in the body rather than a real wall; one run cannot tell.
- **stackoverflow and linkedin** (both Cloudflare "Just a moment..." 403): patchright classified them BLOCKED, Playwright classified them ERR. Both were walls in both runs; patchright just exposed a challenge iframe/text that plain Playwright's page did not have at settle time. Not a win, but a reminder that `classify` misses plain "Just a moment" pages.
- **reddit** was BLOCKED in both ("Prove your humanity"), **instagram** was LOGIN in both, **x.com** raised `net::ERR_HTTP_RESPONSE_CODE_FAILURE` in both at 0.1 to 0.2 s.
- Everything else loaded OK in both. patchright was 0.05 to 0.12 s faster per page, all sub-second.

## Recommendation

**Stay on plain Playwright.** patchright changed the outcome on 1 of 15 sites (weather.com, possibly noise), needs a second browser build (366 MB unpacked plus a 203 MB headless shell) and a separate driver version, and did not remove any of the four real walls. Re-test only if wall rate on the user's actual sites turns out to be a problem.

Left open (not changed here): add "just a moment" to the B6 phrase list and re-check weather.com's BLOCKED label; both belong to `state.py`, outside this task's files.
