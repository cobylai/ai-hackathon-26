# Log: feature/browser-core

- B1: scaffolded the `harness` package (pyproject, config with `HOME_DIR`/`PROFILE_DIR`/`MAX_CHARS`, smoke test).
- B2: `Session` launches full Chromium (`channel="chromium"`, `--headless=new`) on a persistent profile; `get_session()` is a singleton. Test fixtures serve `tests/pages/` and use temp profiles.
- B3: `blocking.install()` routes every request through adblock-rust (EasyList/EasyPrivacy) and aborts images/media/fonts; stats count blocked URLs. `scripts/fetch_filters.py` fetched 3.6 MB of lists in 0.6 s; engine build ~0.2 s.
- B3 fix: first navigation passes an empty frame URL to adblock-rust, which then matches stray document filters; fall back to the request URL as source. Tests now build engines from a temp dir so downloads do not change results.
- B4: `page_text()` runs trafilatura with an lxml body-text fallback; `paginate()` cuts at paragraph > sentence > word boundaries and chunks join back byte-for-byte. Article fixture spans 3 pages.
