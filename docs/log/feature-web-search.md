# Log: feature/web-search

- S1: `harness/search/google.py` parses organic results from `<a>` wrapping `<h3>` (old `div.g` and current markup); drops ads, "People also ask" cards and results beyond 2 per domain; snippets cut to 120 chars. `__init__.py` starts the package.
- S1 note: Google served `/sorry/` bot walls to both plain fetch and headless Chromium, so `tests/pages/google_results.html` is a real 2019 results page (query "test", 10 results) saved from the Wayback Machine instead of retrying the wall.
- S2: `ddg.py` parses `html.duckduckgo.com` results, unwrapping `/l/?uddg=` links and dropping `result--ad` blocks; `engine.search()` tries Google, falls back to DDG on a non-OK page or zero results, and keeps DDG for 10 minutes (`engine.in_fallback()`, `last_status`).
- S2 note: html.duckduckgo.com answered curl with HTTP 202, its own bot check, so the DDG fixture is a Wayback copy of the "python" results page (13 organic results, python.org twice, which exercises the per-domain cap).
- S3: `harness/search/tools.py` adds `search` (numbered `title (domain) snippet` lines, list trimmed to fit the 1500 cap, only shown results stay openable) and `open_result(n)` (opens through the shared browser, returns status line plus first page of text).
- S3 note: registry entries required updating the exact TOOLS set assertion in `tests/test_tools.py`. Search got its own group `search` rather than joining `web`, which already holds six browser tools, against the five-tool rule.
- S4: `rank.py` splits text on paragraph boundaries into ~600-char chunks (long paragraphs cut at sentence/word breaks) and scores them with `rank-bm25` over lowercased, stop-word-filtered question terms; `top_chunks()` returns the best k in page order, and the opening chunks when nothing matches.
