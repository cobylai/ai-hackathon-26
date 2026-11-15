# Voice input (push to talk, Argmax)

You speak a question and Python gets it back as text. Speech-to-text runs on-device through the Argmax Pro SDK, and it needs no network.

**Status (main 0e65978): built and wired in.**
- `uv run python -m reason`: an empty line starts talking, and Enter stops.
- `uv run python -m reason.web`: hold the "Hold to talk" button.
- In both, typing still works if voice can't start (no key, no binary, mic denied), and the reason is shown.
- Voice was proven with the network denied in both.

The original plan is in `docs/plans/voice-input.md`.

## Pieces

- **`voice/swift/` → `argmax-voice`:** one Swift program that stays running.
  - At launch it activates the license and loads Whisper large-v3 turbo (`large-v3-v20240930_626MB`) from `ARGMAX_MODEL_FOLDER`. If that isn't set, it uses `~/Documents/huggingface/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB`. Downloading is off.
  - It records the microphone only between `start` and `stop`.
- **`voice/listen.py`:** starts that program and gives Python one call.

### Protocol

| stdin (one per line) | stdout (one JSON line each) |
|---|---|
| (launch) | `{"event":"ready"}` once the model is loaded |
| `start` | `{"event":"recording"}` |
| `stop` | `{"event":"text","text":"...","seconds":2.4}` (`seconds` = audio length) |
| `file <path.wav>` | same `text` line (for tests without a mic) |
| `quit` | exits |

- **Errors:** any failure prints `{"event":"error","message":"..."}`. That covers microphone denied, a license or model failure, a missing model folder, a recording shorter than 0.25 s, and an unknown command. A failure before `ready` also exits with code 1.
- **stderr:** logs only.
- **Python:** `VoiceError` is raised on an error line, when the process exits, or after a timeout. That's 600 s for `ready` (the first launch compiles) and 60 s otherwise. So Python never hangs silently.

## How to run

```bash
cd voice/swift && swift build -c release && cd ../..     # once, ~65 s (needs the Argmax registry login, docs/argmax.md)
export ARGMAX_API_KEY=ax_...                               # your own key, see below
uv run python -m voice.listen   # try it alone: Enter to start, Enter to stop; prints text and stop-to-text time
uv run python -m reason         # chat loop: empty line = talk
uv run python -m reason.web     # window at http://localhost:8765: hold to talk
```

- **Other binary:** set `MUSE_VOICE_BIN` to use a built `argmax-voice` from another path, for example another checkout (`reason/speech.py`). The default is `voice/swift/.build/release/argmax-voice`.
- **Model folder:** set `ARGMAX_MODEL_FOLDER` if the model isn't at the default path above.
- **Turning voice off:** `--no-voice` on either command means typing only.

### The key

- **Coby:** the key comes from the vault, loaded while still online:
  `export BW_SESSION="$(bw unlock --raw)"` then `export ARGMAX_API_KEY="$(bw get password 'Argmax API key - ai-hackathon-26')"`.
  Both `bw unlock` and `bw get` were tested with the network denied and work. So unlocking after Wi-Fi is off also works.
- **Partner or any other tester:** you need **your own** `ax_` key. Argmax issues one per application, from Andrew at the event. Don't use Coby's key. The first launch on a new Mac also has to be online, to activate the license and download the model (`docs/argmax.md`).

## How it's wired

`reason/speech.py` holds the glue:
- `start_voice()` returns `(Voice, None)` when voice works, or `(None, reason)` when it doesn't.
- `HoldToTalk` turns `Voice.listen(wait_for_stop)` into `start()`/`stop()` calls for the window's button.

The chat loop calls `voice.listen(wait_for_stop=lambda: input(...))`. `listen` takes any blocking function, and recording stops when it returns.

## Results

| Test | Result |
|---|---|
| First launch (Neural Engine compile, one time) | ready after **250 s** |
| Warm launch | ready after **1.5 s** |
| `say` clip (6.7 s), 3× in one process, online | correct all 3 times: "Muse, remind me to buy oat milk tomorrow at 9. The quick brown fox jumps over the lazy dog." **1.37–1.55 s** each |
| Same, with all outbound IP denied for the Python process and its Swift child (`sandbox-exec`) | correct all 3 times, 1.37–1.48 s; ready in 1.5 s |
| `bw get password` with an existing session, network denied | works |
| Live mic, Coby speaking, online, 3 questions in one session | all right: "What's due this week?" / "Remind me to buy oat milk tomorrow at 9:00." / "Who emailed me about the lab report?" Stop to text **1.18 / 1.25 / 1.15 s**. Ready in 1.7 s. |
| Live mic, same 3 questions, network denied (`sandbox-exec`) | all right ("...at 9." this time). Stop to text **1.12 / 1.19 / 1.13 s**. Ready in 1.4 s. |
| `bw unlock` with no network (`sandbox-exec`) | **works** |

Stop to text is about 1.1–1.25 s for a spoken question. "Nine" comes back as "9" or "9:00", and the reasoning layer should treat these the same.

The chat loop and the window were later proven by voice with the network denied too. Their logs are on main, in the step 2 and step 3 live results.

## Setup on a new Mac (once, online)

1. Build: `cd voice/swift && swift build -c release`.
2. First launch: run `uv run python -m voice.listen` once.
   - It compiles for the Neural Engine for about **250 s**.
   - The cache is in `~/Library/Caches/argmax-voice/` (129 MB). Don't clear it before a demo.
   - The program name `argmax-voice` is fixed for this reason.
3. Keychain: click **Always Allow** when asked whether `argmax-voice` may use the Keychain.
4. Microphone: press Enter in `voice.listen` from the terminal app you'll demo from, and click **Allow**. If you get "microphone permission denied", turn the terminal on in System Settings → Privacy & Security → Microphone and restart.

On Coby's Mac all four are done.

## Still to do

- One real Wi-Fi-off run of the whole app: window, Bonsai and voice. Start everything while online, then turn Wi-Fi off and speak the demo questions. `sandbox-exec` blocks connections, but macOS still sees a network. The steps are in `docs/PARTNER-TESTING.md`.
