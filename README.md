# ai-hackathon-26
AI hackathon 2026

## Run it

On `main`, from the repo root, on an Apple Silicon Mac. Everything runs locally, so it works with Wi-Fi off once set up.

```bash
uv sync                                                    # once, online
scripts/serve_bonsai.sh 4B                                 # Bonsai 2 4B on localhost:8080 (leave running)
MUSE_BANK_DIR=~/muse-demo-bank uv run python -m reason.web  # chat window on the sample-mail bank
```

Voice (push to talk, Argmax) needs `ARGMAX_API_KEY` in the same shell and a one-time `cd voice/swift && swift build -c release`. Without it, typing still works.

- Setup and testing step by step: [docs/PARTNER-TESTING.md](docs/PARTNER-TESTING.md)
- How the halves fit, the demo bank (`~/muse-demo-bank`, and how to rebuild it for the recording day), live Gmail sync, and what changed in harness/: [docs/integration.md](docs/integration.md)

## Hackathon rules that constrain the build (from the 2026-11-14 kickoff)

- **Due noon Sun 2026-11-15** in the Discord submissions channel. Include both names, a one-sentence description, the prizes you're entering, a repo link, and a demo video of 2 minutes or less. Finalist demos start around 12:30.
- **Every LLM call at submission time must be Bonsai 2** (2B/4B/9B). Claude is fine as a stand-in during development only.
- **Argmax is required** for main-track eligibility. Voice input (Argmax speech-to-text) is the natural fit for this project.
- **It must run with Wi-Fi off.** Finalists demo it offline. Download every model in advance.
- Bonsai has a 32k context. Don't feed whole scraped pages into one prompt: chunk or summarize them. Sustainability judging rewards right-sizing the model.
- Argmax Pro keys are issued one per application. DM Andrew on Discord for yours.

`samples/` is a copy of [iBrushC/local-ai-hackathon-samples](https://github.com/iBrushC/local-ai-hackathon-samples) @ `5c72a8d`, with two fixes so the Argmax sample builds against SDK 3.1.8.

## Bonsai 2 (local LLM, MLX)

Models are in `samples/bonsai-models/mlx/models/` (gitignored). The venv uses Homebrew Python 3.12, because the default `python3` here is Anaconda 3.9 and mlx-vlm needs 3.10 or newer.

```bash
cd samples/bonsai-models/mlx
./start.sh        # 4B (default) | ./start.sh 2B | ./start.sh 9B
```

This serves an OpenAI-compatible API at `http://localhost:8080/v1` and opens the chat page. See `samples/bonsai-models/mlx/README.md` for client code.

## Argmax Pro SDK (Swift)

- The registry login is already done (`axst_` token, stored in the macOS keychain). It resolves `argmax-sdk-swift` 3.1.8.
- You still need a runtime `ax_` API key. Argmax hands these out at the event.

```bash
cd samples/argmax-pro-sdk/native
export ARGMAX_API_KEY=ax_...
swift run -c release meeting-scribe live --speakers
```

Changes from upstream:
- `Package.swift` now declares tools-version 6.0. With 5.10, `.macOS(.v15)` fails to compile.
- `LiveCommand.swift`: `speakerKit.makeStreamSession` now needs `try await`.
