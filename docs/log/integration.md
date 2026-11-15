# Log: integration

- 2026-11-14: merged the partner's four feature branches, sufficiency-check (2a7af5a), context-store (82a70a5, then main 99000fa with 6cec2f6) and reasoning-layer. Conflicts and every change inside harness/ are listed in docs/integration.md.
- 2026-11-14: `harness/llm.ask` routed through `llm.client`; only `llm/client.py` calls a model, localhost only.
- 2026-11-14 ruling (thinker): the Bing fallback lives in `sufficiency/websearch.py`; harness/search stays untouched (ed93e1c reverted).
- 2026-11-14: live gather 3/3 on Bonsai 4B through websearch (Google and DuckDuckGo bot-walled on this network, Bing answered).
- 2026-11-14: live Gmail sync on the test account: 5 threads -> 5 bank entries in ~/muse-bank, re-run 0 added. Fixed the 24-hour Gmail date format the live account uses.
- 2026-11-14 known issue, no fix (thinker ruling): Google's welcome mail gets course "LLC 1600" from its "Google LLC, 1600 Amphitheatre" footer (bank/classify).
