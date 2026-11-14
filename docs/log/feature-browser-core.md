# Log: feature/browser-core

- B1: scaffolded the `harness` package (pyproject, config with `HOME_DIR`/`PROFILE_DIR`/`MAX_CHARS`, smoke test).
- B2: `Session` launches full Chromium (`channel="chromium"`, `--headless=new`) on a persistent profile; `get_session()` is a singleton. Test fixtures serve `tests/pages/` and use temp profiles.
- B3: `blocking.install()` routes every request through adblock-rust (EasyList/EasyPrivacy) and aborts images/media/fonts; stats count blocked URLs. `scripts/fetch_filters.py` fetched 3.6 MB of lists in 0.6 s; engine build ~0.2 s.
