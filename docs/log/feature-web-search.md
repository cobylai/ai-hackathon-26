# Log: feature/web-search

- S1: `harness/search/google.py` parses organic results from `<a>` wrapping `<h3>` (old `div.g` and current markup); drops ads, "People also ask" cards and results beyond 2 per domain; snippets cut to 120 chars. `__init__.py` starts the package.
- S1 note: Google served `/sorry/` bot walls to both plain fetch and headless Chromium, so `tests/pages/google_results.html` is a real 2019 results page (query "test", 10 results) saved from the Wayback Machine instead of retrying the wall.
