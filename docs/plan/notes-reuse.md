# Notes: should we reuse more open-source code?

Written 2026-11-14. Research only: no code or feature branches were changed. Repo facts (license, last push, stars) come from the GitHub API on 2026-11-14. License names come from each repo's LICENSE file. I read some third-party source files (named below), but I did not run any third-party code.

## Short answer

Yes, in two places, and only as small pieces:

1. **Bot-wall detection.** `unclecode/crawl4ai` has a single-file detector (`crawl4ai/antibot_detector.py`, Apache-2.0, standard library only) that is far more thorough than our `state.py`. Copy it, with attribution.
2. **Search-engine parsers.** Our Google parser is the most fragile code we have. SearXNG shows how a maintained project copes, but it is AGPL, so we take its ideas and not its code.

Everything else: keep what we wrote, borrow ideas, and treat Peekaboo (macOS) as a worthwhile spike for computer control.

## Licenses at a glance

| Project | License | Copy code into our repo? |
|---|---|---|
| browser-use | MIT | Yes, with notice |
| Playwright MCP | Apache-2.0 | Yes, with notice |
| Stagehand | MIT | Yes, but it is TypeScript |
| Skyvern | **AGPL-3.0** | No. Ideas only. |
| SearXNG | **AGPL-3.0** | No. Ideas only. |
| GPT Researcher | Apache-2.0 | Yes, with notice |
| Vane (renamed from Perplexica) | MIT | Yes, with notice |
| gmail.js | MIT | Yes, with notice |
| Hermes Agent | MIT | Yes, with notice |
| trycua/cua (cua-driver) | MIT | Yes. **Its optional `cua-perception` extension bundles an AGPL-3.0 model (OmniParser). Do not install or ship that part.** |
| Open Interpreter | Apache-2.0 | Yes, with notice |
| Peekaboo (openclaw/Peekaboo) | MIT | Yes, with notice |
| crawl4ai | Apache-2.0 | Yes, with notice |

AGPL note: using an unmodified AGPL program as a separate running service is generally treated differently from copying its code into ours. I have not taken legal advice on that, so treat it as unverified before shipping anything that bundles it.

## Comparison table

Last-push dates are all within about two weeks of 2026-11-14 unless noted.

| Area | What we have | What they have | License | Recommendation | Effort |
|---|---|---|---|---|---|
| **Bot-wall detection** | `harness/browser/state.py` (109 lines): 5 blocked phrases, 4 challenge iframes, 2 title prefixes, 3 login hosts. Added after we hit walls in B9. | crawl4ai `antibot_detector.py` (281 lines): tiered patterns for Akamai, Cloudflare, PerimeterX, DataDome, Imperva, Sucuri and others; generic terms only on short pages; a structural check for empty shells and silent blocks; `is_blocked(status_code, html, error_message)` returns `(bool, reason)`. Its stated rule is that false positives are cheap and false negatives are costly. | Apache-2.0 | **Adopt (copy the file, keep the license header, add a NOTICE).** Call it from `classify()` with `page.content()` and the status. Keep our login and title checks. | Small, about half a day including tests |
| **Google results parser** | `harness/search/google.py` (157 lines): `a` wrapping `h3`, plus hard-coded obfuscated class names (`uEierd`, `MjjYud`, `VwiC3b` and others). The only fixture is a **2019** results page (per the S1 log). | SearXNG `searx/engines/google.py` asks Google for the simple no-JavaScript page by sending an old feature-phone User-Agent, sets a `CONSENT` cookie, and parses a different markup (`zMzFAb`, `fuLhoc`, `CVA68e`). Its commit log shows frequent fixes (CAPTCHA detection May 2026, User-Agent change Aug 2026). | AGPL-3.0 | **Borrow ideas only:** the simple-page trick, the consent cookie, and its three-way "sorry page" check. Do not copy code. | Medium, 1 to 2 days with a live canary test |
| **Sorry-page detection** | Text phrases only (`unusual traffic`). No check for the `/sorry/` URL. | SearXNG flags `sorry.google.com`, any `/sorry` path, a bare 302, and a body under 2000 bytes containing `/sorry/`. | AGPL-3.0 | **Borrow the idea.** It is about 5 lines of our own code. | Tiny |
| **DuckDuckGo parser** | `harness/search/ddg.py` (123 lines) on `html.duckduckgo.com`. Fixture is a Wayback copy because DDG returned HTTP 202 to curl. | SearXNG has its own DDG engines. | AGPL-3.0 | Keep ours. Add the same live canary. | Tiny |
| **Search loop** | `harness/search/loop.py` plus BM25 top-2 chunks, at most 3 rounds. | GPT Researcher (multi-agent, many pages, large-model prompts). Vane/Perplexica (a full app). | Apache-2.0 / MIT | **Ignore as dependencies.** They are built for large models and heavy stacks, which is the opposite of our goal. | n/a |
| **Element listing** | `harness/browser/elements.js` (66 lines): `a, button, input, select, textarea, [role=button], [role=link]`; visibility check; 200 items; 50-char labels. | browser-use indexes interactive elements for LLMs. Playwright's built-in `page.aria_snapshot()` exists in our installed version (checked). Playwright MCP is built around accessibility snapshots. | MIT / Apache-2.0 | **Borrow ideas, no dependency.** browser-use brings an agent loop and prompts sized for big models. See gaps below. | Small, a few hours |
| **Browser agent frameworks** | Our own six tools. | Stagehand (TypeScript, LLM-driven `act/observe`). Skyvern (vision-based). | MIT / **AGPL-3.0** | **Ignore.** Wrong language or wrong approach (vision), and Skyvern's license rules out copying. | n/a |
| **Gmail** | No email code exists yet on `feature/email-gmail` beyond E1 (sign-in check). Plan E2 uses `role` and `aria-label` first, class names second, plus a live self-check. | gmail.js hooks Gmail's embedded data and DOM classes. Its README says it **cannot be used server-side** and must be injected into the page at `document_start`. | MIT | **Borrow ideas only**, for example cross-check E2's selector names against its DOM helpers. Do not depend on it. Injecting it through Playwright's init script might work but I did not test it. | Small as reference; unknown as dependency |
| **macOS computer control** | `harness/computer/ui.py` (285 lines, pyobjc accessibility walk with macOS 27 workarounds), `policy.py` (allowlist, blocklist, confirm words, STOP file, action log), `direct.py`. | Hermes Agent wraps cua as its default computer-use backend through a provider plugin contract (verified in `plugins/computer_use/__init__.py`). cua-driver is a background MCP driver for native macOS apps that does not steal focus. **Peekaboo** is a macOS 15+ Swift CLI where `peekaboo see --app X --json` returns a structured UI map with opaque element IDs, plus dialog and window helpers. | MIT | **Spike Peekaboo** as an optional backend behind our policy layer (our own allowlist and confirmations stay). Keep `ui.py` until the spike says otherwise. | Spike 2 to 4 hours |
| **Open Interpreter** | n/a | Now a coding agent for open models. Its computer-use story delegates to trycua and to `vercel-labs/agent-browser`. | Apache-2.0 | **Ignore.** It is not a source of reusable computer-control code. | n/a |

## Where our code is weaker (looked at in the worktrees)

- **`state.py` is a short, hand-picked list.** It will miss most real challenge pages (Akamai, DataDome, PerimeterX, Imperva) and any Cloudflare page that is not titled "Just a moment". crawl4ai's detector covers these, and its tiering keeps generic words from firing on real articles.
- **`google.py` has never been tested against current Google markup.** The fixture is a 2019 capture, saved because Google served its sorry page to the agent's fetches (per the S1 log). Our B9 run did get a live Google page (OK, 200), so it can work from your network, but nothing checks that the parser still finds results. A markup change will make search quietly fall back to DuckDuckGo, and the same will happen if that parser breaks.
- **Both parsers depend on class names Google and DuckDuckGo can change.** SearXNG's own Google engine uses different obfuscated classes from ours and has been patched repeatedly in 2026, which shows how short-lived they are.
- **`elements.js` misses common controls.** It does not list `[role=textbox]` or `contenteditable` fields (rich-text editors, including Gmail's compose body), tabs, menu items or `[role=checkbox]`. It does not reach inside shadow DOM or iframes. The email branch uses its own selectors, so this affects general browsing more than email.
- **Email has nothing to compare yet.** Only E1 is committed, so my email comparison is at the plan level.

## Top 3 changes, in order

1. **Adopt crawl4ai's `antibot_detector.py` and add a `/sorry/` URL check.** Cheapest and biggest gain, and it fits the existing "skip to the next result" design. Wire it into `classify()` and add fixtures for Cloudflare, Akamai and a normal article, to guard against false positives.
2. **Make the search parsers survive markup changes.** Add a live canary test that fetches real Google and DuckDuckGo results and fails if fewer than five results parse. Then add a second parse path using the simple-page approach SearXNG demonstrates (ideas only).
3. **Widen `elements.js`.** Add `[role=textbox]`, `contenteditable`, `[role=tab/menuitem/checkbox]`, open shadow DOM and same-origin iframes, with tests. Then run the Peekaboo spike for computer control.

## What I could not verify

- I did not run any third-party code, so every claim about behavior comes from reading READMEs and source files, not from running them.
- crawl4ai's false-positive rate on our pages is unknown. Its own philosophy accepts false positives, and our design can skip a page cheaply, but test it on real pages first.
- I did not fetch Google live to check whether the current page matches our parser. I only know the fixture is old.
- I did not test whether gmail.js works through Playwright's init script.
- I did not run Peekaboo or cua-driver, so macOS 27 compatibility and whether their output fits a 1500-character cap are unknown. I did not check how either handles permissions compared with our policy layer.
- The "run SearXNG as a separate service" idea comes from general knowledge of its JSON output option and was not checked in its source.
- Star counts and dates come from the GitHub API on the day of writing. Perplexica now redirects to a repo named Vane (last push 2026-09-01, the oldest of the group).
- License summaries are not legal advice.
