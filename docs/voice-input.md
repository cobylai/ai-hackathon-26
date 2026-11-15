# Voice input (push to talk, Argmax)

You speak a question and Python gets it back as text. Speech-to-text runs on-device through the Argmax Pro SDK, and it needs no network. The plan is in `docs/plans/voice-input.md`.

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
cd voice/swift && swift build -c release && cd ../..     # once, ~65 s
export ARGMAX_API_KEY="$(bw get password 'Argmax API key - ai-hackathon-26')"   # needs BW_SESSION
python -m voice.listen        # Enter to start, Enter to stop; prints text and stop-to-text time
```

Any Python 3.10+ works, since it uses the standard library only. I tested with `samples/bonsai-models/mlx/.venv/bin/python` in the main checkout.

## Two lines for the chat loop

```python
from voice.listen import Voice; voice = Voice()   # once, at startup (≈1.5 s warm)
question = voice.listen()                          # instead of input(): Enter to start talking, Enter to stop
```

`listen(wait_for_stop)` takes any blocking function, for example a UI button event. The default is `input`. Call `voice.close()` on exit.

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

Not verified: a real Wi-Fi-off run. That happens later, once, for the whole app. `sandbox-exec` blocks connections, but macOS still sees a network.

## Steps for Coby

**Once, now:**

1. Build: `cd voice/swift && swift build -c release`. This is already done in this worktree.
2. First launch: done (250 s compile). The cache is in `~/Library/Caches/argmax-voice/` (129 MB). Don't clear it before the demo. The program name `argmax-voice` is fixed for this reason.
3. Keychain: if a prompt asks whether `argmax-voice` may use the Keychain, click **Always Allow**. It's a new binary, so it asks again even though meeting-scribe was allowed.
4. Microphone: run `python -m voice.listen` from the terminal app you'll demo from, and press Enter. Click **Allow** on the microphone prompt. If no prompt appears and you get "microphone permission denied", go to System Settings → Privacy & Security → Microphone and turn your terminal app on. Then restart the command.

**Mic test (online, then with the network denied):**

```bash
cd ~/code/ai-hackathon-26/.claude/worktrees/argmax-runtime-test-743dfa
```
```bash
export BW_SESSION="$(bw unlock --raw)"
```
```bash
export ARGMAX_API_KEY="$(bw get password 'Argmax API key - ai-hackathon-26')"
```
```bash
~/code/ai-hackathon-26/samples/bonsai-models/mlx/.venv/bin/python -m voice.listen
```

Say these three: "What's due this week?", "Remind me to buy oat milk tomorrow at nine.", "Who emailed me about the lab report?". Then Ctrl+C and run it again with the network denied:

```bash
sandbox-exec -p '(version 1)(allow default)(deny network-outbound (remote ip))' ~/code/ai-hackathon-26/samples/bonsai-models/mlx/.venv/bin/python -m voice.listen
```

**Check that `bw unlock` works with no network.** The demo needs this if you unlock after Wi-Fi is off. It prints only ok or FAIL:

```bash
sandbox-exec -p '(version 1)(allow default)(deny network-outbound (remote ip))' bw unlock --raw > /dev/null && echo "bw unlock offline: ok" || echo "bw unlock offline: FAIL"
```

**At the demo (Wi-Fi off):** the safe order is to load the key **before** turning Wi-Fi off. Run the `bw unlock` and `export ARGMAX_API_KEY=...` lines above while you're online. Then turn Wi-Fi off and start the app from that same terminal. `bw get` with an existing session and `bw unlock` both work with no network (tested with `sandbox-exec`), so unlocking after Wi-Fi is off also works.
