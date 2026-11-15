# Round 2 on a MacBook Air (a second, cheaper Mac), 2026-11-15

Tested `main` at d3e75b6 following `docs/PARTNER-TESTING.md` then `docs/PARTNER-TESTING-2.md`. Run **remotely over SSH** (reached through Tailscale) from the first Mac, not at the Air's keyboard, so everything that needs a person at the screen or your own keys is marked NOT RUN. Every model call went to local Bonsai 2 4B on 127.0.0.1:8080. Nothing was sent; no sign-in was done; no keys were used.

## This Mac versus the first Mac

| | First Mac | Air |
|---|---|---|
| Chip / RAM | Apple M5, 32 GB | **Apple M1, 8 GB** |
| macOS | 27.0.1 | 15.8.2 |
| Developer tools | Xcode, Homebrew, uv, Python 3.15 | **Command Line Tools only** (Swift 6.1.2); no uv, no Homebrew, system Python 3.9.6 |
| Network | open | Cornell eduroam; **IPv6 broken** (see failures) |
| Bank (model) answers | 0.8 to 1.5 s | **2.8 to 4.2 s** (about 3x slower) |
| Plain-code answers (due, person) | 0.0 s | 0.0 s |
| pytest | 70 s | 57 to 62 s |
| Bonsai server memory | n/a | about 225 to 380 MB resident; system stayed 39 to 45% free with app, model and tests running |

## Test counts and scores

| Run | Expected | Got |
|---|---|---|
| unittest reason | about 93 or more | **176 OK** |
| unittest bank | about 65 or more | **72 OK** |
| unittest sufficiency | about 48 or more | **54 OK** |
| unittest applecal | about 9 | **10 OK** |
| unittest canvas | about 10 | **11 OK** |
| `uv run pytest -q` | 271 passed, 3 skipped | **272 passed, 3 skipped** in 57 s (3 skips are uBlock Origin Lite tests; the extension isn't installed here) |
| demo bank check (`make_test_mail.py check ... --offline`) | 37/38 | **37/38**: person 14/14, nomatch 2/2, due 16/16, bank 5/6. The one miss is the known hackathon team-name question. Note the generator wrote **23 emails**, not the 20 the guide says. |
| `python -m reason.playbook_check` | every example right | **80/106** (26 wrong, below) |

### playbook_check, the 26 wrong

By file: calendar 1, compose 2, discover 9, followup 8, setup 3, suggest 3. Every wrong example I read needs something this Air does not have: the "Muse demo" calendar (the message says `no calendar named "Muse demo" in Calendar.app`) or the mock Canvas pages (expected strings name CHEM 1583 / INFO 3361 / "Homework 9", and "set me up for the lab" found one match so it did not ask "Which one do you mean"). Mock Canvas needs saved Canvas templates, which the guide calls optional. I did not add either, so I have **not** shown these 26 would pass with them. Sample:

```
[WRONG] calendar  What do I have this week?
   want: route calendar, contains ['this week']
   got (calendar): I couldn't read Apple Calendar (no calendar named "Muse demo" in Calendar.app).
[WRONG] followup  the first one
   want: route followup, contains ['Submit reading quiz', 'Source: INFO 3361 Data Stories']
   got (followup): 5pm  Reply with your vote (Hugo Sato, Nov 12) | ... 
```

Command: `MUSE_BANK_DIR=~/muse-demo-bank uv run python -m reason.playbook_check` (full output was saved on the Air at ~/air-tests/playbook-full.log).

## Things to try (typed; PARTNER-TESTING-2 table)

| Ask | Result |
|---|---|
| What's on my calendar this week? / next event / free Monday? | **NOT RUN**: no "Muse demo" calendar. The app answers `I couldn't read Apple Calendar (no calendar named "Muse demo" in Calendar.app).` (route calendar, 0.4 s). I did not create the calendar: from SSH I could not place it under "On My Mac" and it would have landed in a real synced account. EventKit access was denied without a screen session. |
| Remember that my lab is Tuesdays at 2. | PASS: `Got it. I'll remember: my lab is Tuesdays at 2.` |
| What do you know about me? | PASS: lists the note, "Source: your notes" |
| When is my lab? | PASS: `Tuesdays at 2 | Source: your note, Nov 15` (route bank, 3.0 s) |
| Forget that. | PASS: `Forgotten: my lab is Tuesdays at 2.` |
| Catch me up | PARTIAL: calendar line fails (no calendar); the due and asks parts answer with sources |
| Open my calendar, then yes | PASS: `I'll open Calendar.` then `Opened Calendar.`; `~/.harness/actions.log`: `ALLOW Calendar open` |
| Open Safari | PASS: refused, `I can only open Calendar, Notes, Finder, TextEdit, Preview and Calculator, or a page saved in the bank.` |
| Draft a reply to a sender saying yes, then yes (online, Gmail signed in) | **NOT RUN** (Gmail is not signed in on the Air; sign-in is the user's). The compose route on its own works: `Draft a reply to Felix saying yes` gave an on-screen draft "Edit it, then Open in Mail. Nothing is sent." |
| The same draft request offline | **DIFFERS from the guide**: the compose route still produced the draft offline instead of saying it needs a connection. (The guide's row is about the Gmail draft path, which I did not run.) |
| What's due this week? then "and next week?" then "the first one" | PASS (follow-ups answer from the last list) |
| Hey, can you hear me okay? | PASS: `I can hear you. Ask me about your mail, what's due, or your calendar.` route chat, no web |
| Who wrote Frankenstein? (online) | **FAIL**: `Not found after 3 search(es) and 14 page(s) (14 unreadable).` (route not_found, 6.2 s). Cause below. |
| Edit one line of playbooks/due.md, restart, ask | PASS: changed the `nothing_due` wording; after restart "What is due on November 30?" answered `AIR TEST: nothing due Mon Nov 30.` Restored the file afterwards. |
| Everything above, spoken | **NOT RUN**: no Argmax key or registry login on the Air (voice must not use anyone else's key; the guide has you enter your own). |

## Wi-Fi-off run (round 1 item 4, PASS)

Started the window and Bonsai while online, then ran a script on the Air that turned Wi-Fi off, asked 14 questions locally, and turned Wi-Fi back on by itself (with a 6-minute watchdog). Wi-Fi was off for 18 s (`wifi power now: Off`). All answers matched online except where noted:

- What's due this week / What did Felix ask me / What did Zelda ask me: same as online, 0.0 to 0.2 s
- remember, what do you know about me, forget: same as online
- Catch me up: same, with the calendar line failing as it did online
- open my calendar, yes: `Opened Calendar.`
- Who wrote Frankenstein? `I don't have that saved, and the Mac is offline, so I can't look it up.` (route offline, 0.0 s)
- Draft a reply to Felix saying yes: produced the draft (see the DIFFERS row above)
- Where is the review session now?: `Barrow Hall room 112`, 4.2 s (bank, from Bonsai)

Nothing hung or errored. The Air's link dropped during the run and came back by itself. Wi-Fi-off with voice was **not run**.

## Window and Mac app

| Item | Result |
|---|---|
| Window server (`python -m reason.web --no-open --no-voice`) | starts; `/status` returns online, 23 items, voice off |
| Window visuals (answer styles, bank sidebar, Yes/Cancel, Escape, narrow and full screen) | **NOT RUN** (needs a screen) |
| `MUSE_REPO="$PWD" app/build.sh` on the Air | PASS in 17 s with Command Line Tools only (no Xcode): `Built .../app/build/Muse.app (signed: adhoc ...)`. Signed ad hoc, so macOS permissions will not survive rebuilds. |
| First launch key pop-up, Fn-Space tap and hold, Accessibility/microphone/Calendar prompts, "Check setup", Quit leaves no servers on :8765/:8080 | **NOT RUN**: I did not open the app because it needs the user to enter their own keys and click macOS prompts. |
| DMG path (Muse.dmg, INSTALL.html) | NOT RUN: used the local build instead. I read INSTALL.html and setup.sh before touching anything. |

## Setup steps that failed or differ on this Mac

1. **No uv, no modern Python.** A stock Air has system Python 3.9.6 and no uv. `setup.sh` offers to install uv, but I copied the binary from the other Mac instead (no download). `uv sync` then fetched Python 3.12.16 and the packages in 5 s.
2. **`setup.sh` clones a private repo with no credentials** (its default `REPO_URL` is a placeholder filled in only for the DMG). The Air has no GitHub login, so I copied the repo over SSH (rsync).
3. **`uv run playwright install chromium` fails on this network:**
   ```
   Downloading Chrome for Testing 159.0.8154.6 ... https://cdn.playwright.dev/builds/cft/159.0.8154.6/mac-arm64/chrome-mac-arm64.zip
   Error: read ECONNRESET   (errno: -54)
   ```
   Worked around by copying `chromium-1255` and `chromium_headless_shell-1255` from the other Mac.
4. **IPv6 is broken on the Air's network, which breaks `localhost` and Chromium.**
   - `curl http://localhost:8080/v1/models` fails with `curl: (56) Recv failure: Connection reset by peer` (localhost resolves to `::1` first); `http://127.0.0.1:8080` works. The app's default `BONSAI_BASE_URL` is `http://localhost:8080/v1`, so I set `BONSAI_BASE_URL=http://127.0.0.1:8080/v1` for every run. `llm/client.py` accepts 127.0.0.1.
   - Consequence for `setup.sh` step 7: its `until curl -s -m 2 localhost:8080/v1/models; do sleep 2; done` can never succeed here (inferred from the curl failure above; I did not run `setup.sh`). The guide's `curl -s localhost:8080/v1/models || scripts/serve_bonsai.sh 4B` would also start a second server.
   - `curl -4 https://en.wikipedia.org/...` returns 200; `curl -6` returns `Recv failure: Connection reset by peer` (also for cdn.playwright.dev).
   - Chromium via Playwright (`channel="chromium"`, headless new) gets `net::ERR_CONNECTION_RESET` on example.com, pypi.org, bing.com, wikipedia.org (HTTP and HTTPS) and works on duckduckgo.com. Adding `--disable-ipv6` (and `--disable-quic`) did not fix it, so I did not isolate the cause. **This is why the web route fails here.** Try another network (a phone hotspot) before calling it a code bug.
5. **`scripts/serve_bonsai.sh` binds `*:8080` (all interfaces).** On a campus network that exposes the model. I ran the server with `--host 127.0.0.1` instead. Suggest adding that flag to the script.
6. **The guide's step "Xcode 16+" is not needed to build the app.** `app/build.sh` built with only Command Line Tools. `setup.sh` step 0 also passes on Command Line Tools (`xcrun --find swift`). I did not run the voice build: the Air has no `~/.swiftpm/configuration` (no Argmax registry login), and the guide has you paste your own `axst_` token.

## Anything in `harness/` that broke

Nothing in the harness tests (272 pass). The one live failure is browsing (item 4 above), which looks like the network, not the harness. `email_asks`, drafts through Gmail and computer control were not run here (no Gmail sign-in; computer control needs a screen session).

## Left on the Air

`~/air-tests/` (repo copies, model, venvs, logs, demo bank), `~/muse-demo-mail` and `~/muse-demo-bank`, copied Chromium in `~/Library/Caches/ms-playwright/`, `~/.local/bin/uv`, and one extra line in `~/.ssh/authorized_keys` ending `claude-air-tests-2026-11-15` (remove it). `caffeinate` was running for 3 hours; Bonsai (127.0.0.1:8080) may still be running. Calendar.app was opened once by the "open my calendar" test.
