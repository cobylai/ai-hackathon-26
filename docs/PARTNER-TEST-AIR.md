# Partner test on a MacBook Air (cheaper hardware), 2026-11-15

Same guide (`docs/PARTNER-TESTING.md`), same code (`main` at 0e65978), run over ordinary SSH on a MacBook Air, reached through Tailscale. Compared with the MacBook Pro results in `docs/PARTNER-TEST-REPORT.md`. Web search and gather skipped; voice and the Wi-Fi-off run were not run (they need someone at the Air).

## Hardware

| | MacBook Pro (earlier run) | MacBook Air (this run) |
|---|---|---|
| Chip | Apple M5 | Apple M1 |
| RAM | 32 GB | **8 GB** |
| macOS | 27 | 15.8.2 |
| Free disk | plenty | 158 GB of 228 GB |
| Preinstalled | uv, Python 3.15, Homebrew | **none** (system Python 3.9.6 only; no uv, no Homebrew) |
| Network | open | Cornell eduroam (campus Wi-Fi) |

## Results

| Item | Result on the Air |
|---|---|
| `uv run pytest -q` | **272 passed, 3 skipped** in 65 s (Pro: 274 passed in 70 s). The 3 skips are the uBlock Origin Lite tests; that extension isn't installed on the Air. |
| `unittest` reason / bank / sufficiency | 30 / 49 / 41 OK |
| Demo bank check | **37/38**, same single miss (hackathon team-name options). Check took 21 s. |
| Typed demo questions (9 asked) | Same answers as the Pro. Person and due routes 0.0 s. |
| Bank questions (Bonsai 2 4B) | **3.0 to 4.0 s** per answer on the Air versus 0.8 to 1.5 s on the Pro: about 3x slower. |
| Bonsai 2 4B server | Loads in about 2 s from a warm copy; resident memory about 225 to 380 MB; system memory 39 to 45% free while running the app, the model and the tests together. Fits comfortably on 8 GB. |
| Voice | not run |
| Wi-Fi off | not run |

## Setup time and problems on the Air

| Step | Result |
|---|---|
| Reach the Air | Tailscale ping 12 ms. SSH needed a key added once on the Air (Tailscale SSH was not enabled there). |
| `uv` | not installed; copied the binary from the Pro (no download needed) |
| Repo | copied with rsync (2.2 MB, no GitHub login needed for a private repo) |
| `uv sync` | 5 s (it fetched Python 3.12.16 and the packages) |
| `playwright install chromium` | **FAILED on the Air**: `read ECONNRESET` from `cdn.playwright.dev` on campus Wi-Fi, though pypi.org and huggingface.co were reachable. Worked around by copying `chromium-1255` and `chromium_headless_shell-1255` from the Pro (2 minutes). |
| Bonsai 2 4B model | copied from the Pro (1.8 GB, 3 min 53 s); the guide's download path was not used |
| mlx-vlm venv | built fresh with `uv venv --python 3.12` and `uv pip install mlx-vlm` (11 s). The Pro's venv could not be reused (system Python 3.9 is too old). |

## Findings for Coby

1. **`localhost` does not work on the Air; `127.0.0.1` does.** `curl http://localhost:8080/v1/models` gets "connection reset" because `localhost` resolves to `::1` first and the server listens on IPv4 only. The default `BONSAI_BASE_URL` is `http://localhost:8080/v1`, so on this Air the app fails unless you set `BONSAI_BASE_URL=http://127.0.0.1:8080/v1`. `llm/client.py` already accepts 127.0.0.1. Suggest making that the default, or trying both.
2. **The guide's server command binds `*:8080` (all interfaces).** On a campus network that exposes the model to other devices. I ran the server with `--host 127.0.0.1` on the Air. Suggest adding that flag to `scripts/serve_bonsai.sh`.
3. **Playwright's Chromium download fails on eduroam.** A fresh machine on campus Wi-Fi may not be able to run the guide's `playwright install chromium`. Workarounds: another network, or copy `~/Library/Caches/ms-playwright/chromium-1255` from a machine that has it.
4. **The guide assumes uv and a modern Python.** A stock Mac has neither; the Air needed uv first (the guide never says to install it) and Python 3.12 came from uv.
5. **Test count differs by one** (275 total on the Air vs 274 on the Pro). Not investigated; likely a test that depends on the Bonsai server being reachable.
6. **The guide's `DAY=2026-11-15` hard-code** matched the Air's date this time (the Air's clock was already on Nov 15).

## Left on the Air (clean up when done)

- `~/air-tests/` (repo copy, model, venv, logs, demo bank) and the copied Chromium in `~/Library/Caches/ms-playwright/`.
- `~/.local/bin/uv`, `~/.local/bin/uvx`.
- One extra line in `~/.ssh/authorized_keys` ending `claude-air-tests-2026-11-15`. Remove it when finished.
- Bonsai (port 8080, localhost only) and the demo window (port 8765) may still be running.
