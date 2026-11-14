# Log: feature/browser-core

- B1: scaffolded the `harness` package (pyproject, config with `HOME_DIR`/`PROFILE_DIR`/`MAX_CHARS`, smoke test).
- B2: `Session` launches full Chromium (`channel="chromium"`, `--headless=new`) on a persistent profile; `get_session()` is a singleton. Test fixtures serve `tests/pages/` and use temp profiles.
