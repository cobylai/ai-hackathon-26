# 01. Hidden browser (`feature/browser-core`)

Read [00-overview.md](00-overview.md) first.

## Goal

A Chromium that ships with the install, runs with no visible window, has its own profile (nothing from the user's Chrome), blocks ads, and is driven only through short text tools.

## Design choices

- **Engine:** Playwright for Python with its bundled Chromium (`playwright install chromium`). No compile from source.
- **Profile:** one persistent profile at `~/.harness/profile`, so sign-ins survive restarts. Never point at the user's Chrome profile.
- **Hidden:** headless (`--headless=new`, full Chromium, not the cut-down headless shell, which sites detect more easily).
- **Ad blocking:** at the network layer with `page.route`, using Brave's `adblock` Python package and EasyList. Images, fonts and media are also dropped, since the model only reads text. This is faster than an extension and works headless.
- **Bot walls:** the tool detects "are you a robot" pages and returns `BLOCKED`. It does not try to solve them. The caller moves to the next result. `patchright` (a drop-in Playwright fork with fewer automation tells) is an optional switch tried in B9.
- **One browser process** stays alive for the session; tools reuse one tab unless told otherwise.

## Tools this branch delivers

| Tool | Args | Returns |
|---|---|---|
| `goto` | `url` | status line, title, first page of text |
| `read` | `page` (int, default 1) | that page of the current page's main text |
| `elements` | `filter` (optional word) | numbered clickable and typeable items |
| `click` | `n` | status line, then new title |
| `type` | `n`, `text`, `enter` (0 or 1) | status line |
| `back` | none | status line, title |

Status line format: `OK <domain> | <title, max 60 chars> | page 1/4`.

## Tasks

### B1. Scaffold
- **Files:** `pyproject.toml`, `harness/__init__.py`, `harness/config.py`, `tests/test_smoke.py`, `.gitignore`, `docs/log/`
- **Steps:** `uv init`-style project named `harness`, Python 3.12+. Dependencies: `playwright`, `trafilatura`, `adblock`, `rank-bm25`, `httpx`, `pytest`. `config.py` holds `HOME_DIR = ~/.harness`, `PROFILE_DIR`, `MAX_CHARS = 1500`. Ignore `.venv`, `__pycache__`, `*.gguf`.
- **Done when:** `uv run pytest -q` passes one trivial test that imports `harness.config`.

### B2. Browser session
- **Files:** `harness/browser/session.py`, `tests/test_session.py`, `tests/pages/hello.html`, `tests/conftest.py`
- **Steps:** class `Session` with `start()`, `stop()`, `page` property. Use `launch_persistent_context(PROFILE_DIR, headless=True, args=["--headless=new"])`. Module-level `get_session()` returns one shared instance. `conftest.py` adds a fixture that serves `tests/pages/` on a local port and a fixture that uses a temporary profile directory.
- **Done when:** test opens `hello.html` from the local server and reads its `<title>`.
- **Do not:** use the real `~/.harness/profile` in tests.

### B3. Request blocking
- **Files:** `harness/browser/blocking.py`, `scripts/fetch_filters.py`, `tests/test_blocking.py`, `tests/pages/ads.html`
- **Steps:** `fetch_filters.py` downloads EasyList and EasyPrivacy to `~/.harness/filters/`. `blocking.py` builds an `adblock.Engine` from those files (empty engine if missing) and installs a `page.route("**/*")` handler that aborts requests when the engine matches or when the resource type is `image`, `media` or `font`. Count blocked requests.
- **Done when:** on `ads.html` (which references `doubleclick.net/x.js` and a local image), the test sees both aborted and the page text still loads.

### B4. Page text reader
- **Files:** `harness/browser/text.py`, `tests/test_text.py`, `tests/pages/article.html`
- **Steps:** `page_text(html) -> str` using `trafilatura.extract` (fallback: `document.body.innerText`). `paginate(text, page, max_chars=MAX_CHARS) -> (chunk, total_pages)` cuts on paragraph or sentence breaks, never mid-word. Collapse blank lines and repeated whitespace.
- **Done when:** tests show nav and footer text are absent from `article.html`, every chunk is at most 1500 characters, and joining all pages returns the full text.

### B5. Numbered elements
- **Files:** `harness/browser/elements.py`, `harness/browser/elements.js`, `tests/test_elements.py`, `tests/pages/form.html`
- **Steps:** `elements.js` collects visible `a`, `button`, `input`, `select`, `textarea`, `[role=button]`, `[role=link]`, tags each with `data-hn="<n>"`, and returns `{n, kind, label}` where label is text, `aria-label`, `placeholder` or `name`, cut to 50 characters. Skip items with no label or zero size. `list_elements(page, filter=None)` returns lines like `3. button "Sign in"`, at most 40 lines. `click(n)` and `type_into(n, text, enter)` find `[data-hn="n"]`.
- **Done when:** on `form.html` the test lists the fields, types into one, clicks submit and sees the result text.

### B6. Page state detection
- **Files:** `harness/browser/state.py`, `tests/test_state.py`, `tests/pages/captcha.html`, `tests/pages/login.html`
- **Steps:** `classify(page) -> "OK" | "BLOCKED" | "LOGIN" | "ERR"`. BLOCKED: title or text matches a short list (`are you a robot`, `unusual traffic`, `verify you are human`, `captcha`, `access denied`) or a known challenge iframe is present. LOGIN: a visible password field. ERR: HTTP status 400 or above, or navigation failure.
- **Done when:** each fixture page gets the right label and `article.html` gets `OK`.
- **Do not:** add code that tries to pass a challenge.

### B7. Tool facade and registry
- **Files:** `harness/browser/tools.py`, `harness/registry.py`, `harness/__main__.py`, `tests/test_tools.py`
- **Steps:** implement the six tools from the table above as functions returning strings with the status line. Register them in `registry.py` (`TOOLS`, `GROUPS["web"]`). `__main__.py` gives a CLI: `uv run python -m harness goto https://example.com`, `... read 2`, `... elements`. A shared test helper asserts every tool result is at most 1500 characters and starts with a known status word.
- **Done when:** tests pass, and the CLI prints a status line and text for a local fixture page.

### B8. Sign-in mode (HUMAN to verify)
- **Files:** `harness/browser/login.py`, addition to `harness/__main__.py`, `docs/plan/notes-login.md`
- **Steps:** `uv run python -m harness login <url>` stops the hidden session, then starts the same Chromium binary directly with `subprocess` and `--user-data-dir=PROFILE_DIR`, with a visible window and **no** automation or remote-debugging flags. The user signs in and closes the window. The hidden session then starts again on the same profile. Refuse to start if the profile is locked by another process.
- **Why:** Google blocks sign-in when it sees a debugging port or an automated tab. Signing in once in a plain window and reusing the profile is the reported way around it.
- **Done when:** the user signs in to one site, and a later headless `goto` to that site returns `OK`, not `LOGIN`. Write what happened (worked, blocked, 2-step prompts) in `notes-login.md`.

### B9. SPIKE: bot-wall rate, live
- **Files:** `scripts/live_check.py`, `docs/plan/notes-botwalls.md`
- **Steps:** visit 15 common sites (Reddit, Wikipedia, a news site, a weather site, Stack Overflow, GitHub and so on) with plain Playwright, then with `patchright` swapped in. Record status and time per site.
- **Done when:** the notes file has a table and a one-line recommendation: stay on Playwright or switch.

### B10. Timing and size report
- **Files:** `scripts/bench.py`, `docs/plan/notes-bench.md`
- **Steps:** measure cold start, warm `goto` + `read` on 5 fixture pages, memory of the Chromium process tree, and install size on disk.
- **Done when:** numbers are in the notes file. Target: warm `goto` + `read` under 2 seconds on a local page.

## Later, not now

- Loading uBlock Origin Lite as an extension.
- Copying selected sign-ins from the user's Chrome (opt-in, per site).
- More than one tab.
