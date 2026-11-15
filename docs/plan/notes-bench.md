# Timing and size (B10)

Measured 2026-11-14 on macOS 27.0.1 (arm64), Python 3.15.2, Playwright 1.65.2 / Chromium 159, local fixture pages via `uv run python scripts/bench.py`. Temp profiles; request blocking active with the downloaded EasyList/EasyPrivacy.

## Cold start (`Session.start()`, 3 fresh profiles)

1.44 s, 0.55 s, 0.48 s — median 0.55 s. The first run includes cold file cache.

## Warm `goto` + `read(1)` (seconds, 3 runs per page)

| Page | Runs | Median |
|---|---|---|
| hello.html | 0.03, 0.03, 0.03 | 0.03 |
| article.html | 0.04, 0.04, 0.04 | 0.04 |
| form.html | 0.04, 0.04, 0.03 | 0.04 |
| ads.html (blocked script + image) | 0.14, 0.16, 0.07 | 0.14 |
| captcha.html | 0.02, 0.03, 0.03 | 0.03 |

Overall median **0.04 s**, max 0.16 s — far under the 2 s target. `ads.html` is slower because the aborted third-party script still waits on route handling.

## Memory (article page loaded, 2 s settle)

7 Chromium processes, **635 MB** resident total for the profile's process tree. This is one tab of a full Chromium, not the headless shell.

## Disk

| Item | Size |
|---|---|
| repo `.venv` | 263 MB |
| Chromium build (`ms-playwright/chromium-1255`) | 622 MB |
| whole `ms-playwright` cache | 1330 MB (includes headless shell, WebKit and ffmpeg, which the harness does not need) |
| `~/.harness` (profile + filters + uBOL) | 56 MB (47 MB of that is the opt-in uBOL copy) |

The harness needs roughly 0.9 GB for `.venv` + Chromium. Dropping unused Playwright browsers and uBOL (`rm -rf ~/.harness/extensions/ubol`) saves about 0.75 GB.
