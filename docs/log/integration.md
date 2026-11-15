# Log: integration

- 2026-11-14: merged the partner's four feature branches, sufficiency-check (2a7af5a), context-store (82a70a5, then main 99000fa with 6cec2f6) and reasoning-layer. Conflicts and every change inside harness/ are listed in docs/integration.md.
- 2026-11-14: `harness/llm.ask` routed through `llm.client`; only `llm/client.py` calls a model, localhost only.
- 2026-11-14 ruling (thinker): the Bing fallback lives in `sufficiency/websearch.py`; harness/search stays untouched (ed93e1c reverted).
- 2026-11-14: live gather 3/3 on Bonsai 4B through websearch (Google and DuckDuckGo bot-walled on this network, Bing answered).
- 2026-11-14: live Gmail sync on the test account: 5 threads -> 5 bank entries in ~/flux-bank, re-run 0 added. Fixed the 24-hour Gmail date format the live account uses.
- 2026-11-14 known issue, no fix (thinker ruling): Google's welcome mail gets course "LLC 1600" from its "Google LLC, 1600 Amphitheatre" footer (bank/classify).
- 2026-11-14 (brief N): test threads built from one saved Gmail page (`scripts/make_test_threads.py`, `scripts/sync_test_threads.py`). 20/20 match on sender, address, date and subject; brief M's check went 32/37, then 36/37 after worker 9's person-route fix.
- 2026-11-14 (brief Q): `--today` flag on the generator and thread scripts; demo bank `~/flux-demo-bank` built for Sun 2026-11-15, 37/38 offline. The live-send demo and the partner's re-sync were dropped for this sample-mail bank.
- 2026-11-14 close-out: the integration branch landed on main at 0e65978 and is retired; use main. Open: the voice run of the video's person questions (needs Coby); test banks hold 20 threads, not 30. Current state is in docs/integration.md.
