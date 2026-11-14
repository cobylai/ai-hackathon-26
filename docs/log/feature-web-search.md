# Log: feature/web-search

- S1: `harness/search/google.py` parses organic results from `<a>` wrapping `<h3>` (old `div.g` and current markup); drops ads, "People also ask" cards and results beyond 2 per domain; snippets cut to 120 chars. `__init__.py` starts the package.
- S1 note: Google served `/sorry/` bot walls to both plain fetch and headless Chromium, so `tests/pages/google_results.html` is a real 2019 results page (query "test", 10 results) saved from the Wayback Machine instead of retrying the wall.
- S2: `ddg.py` parses `html.duckduckgo.com` results, unwrapping `/l/?uddg=` links and dropping `result--ad` blocks; `engine.search()` tries Google, falls back to DDG on a non-OK page or zero results, and keeps DDG for 10 minutes (`engine.in_fallback()`, `last_status`).
- S2 note: html.duckduckgo.com answered curl with HTTP 202, its own bot check, so the DDG fixture is a Wayback copy of the "python" results page (13 organic results, python.org twice, which exercises the per-domain cap).
