# uBlock Origin Lite (B3b): headless result

Checked 2026-11-14 with uBOLite 2026.1110.1816 (Chromium 159, Playwright 1.65.2, `channel="chromium"`, `--headless=new`), unpacked via `scripts/fetch_ubol.py`.

## Does it load headless?

Yes. `--load-extension` works in the full Chromium build in new headless mode: the extension's service worker appears at `chrome-extension://<id>/js/background.js`, and its declarative rulesets (`ublock-filters`, `easylist`, `easyprivacy`, `pgl`, `ublock-badware`, `urlhaus-full`) are enabled. Network blocking works: `https://doubleclick.net/x.js` fails with `net::ERR_BLOCKED_BY_CLIENT`.

## Cosmetic filtering: not by default, and not for this fixture

- Default filtering mode is **Basic**, which does no cosmetic filtering. `div.ad-banner` stays visible with the extension on.
- Raising the mode to **Complete** (done only for the probe, via the extension's own dashboard message) does apply generic cosmetic filters, but only for selectors that exist in the compiled lists. `.ad-banner-content` (present in EasyList) is hidden on the first reload; `.ad-banner` is in no shipped list, so it stays visible in every mode.
- **The B3b check as written ("`div.ad-banner` hidden with UBOL on") cannot pass**: no filter list targets that class. The test records the observed result instead: off and basic mode leave both banners visible; Complete mode hides the EasyList-listed one.
- The extension makes no network requests for filter lists; rulesets are compiled into the package.

## Page-load time (local `ads.html`, 3 cold runs each)

| Mode | `Session.start()` | `goto` (domcontentloaded) |
|---|---|---|
| off | 1.47 s, 0.75 s, 0.76 s | 0.16 s, 0.13 s, 0.19 s |
| on | 1.18 s, 1.91 s, 0.95 s | 0.09 s, 0.10 s, 0.05 s |

Startup is noisier and on average ~0.4 s slower with the extension; local page load is unchanged within noise.

## Size

9.1 MB zip, 47 MB unpacked (~29 MB of that is compiled rulesets), 1029 files. Nothing is committed; it lives in `~/.harness/extensions/ubol`.

## Recommendation

Keep `USE_UBOL = False` (opt-in only). The B3 network layer already blocks ad scripts, images and fonts for text reading; uBOL adds scriptlets and specific cosmetics only in Optimal/Complete mode, which is not the default, costs 47 MB on disk plus extension startup, and needs a user-visible mode change. If it is enabled later, preset Complete mode and re-measure on real sites.
