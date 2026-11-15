# Plan: voice-input

Branch `voice-input`, cut from `argmax-runtime-test` at c0f7935. Nothing gets built until Coby types OK.

## Approach

A single Swift program, `muse-voice`, starts once and stays running. Python talks to it over stdin and stdout. Push to talk:

1. **Launch.** It loads the model once, from the on-disk folder, with downloading turned off. That folder comes from `ARGMAX_MODEL_FOLDER` and defaults to `~/Documents/huggingface/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB`. Run F showed this setup works with no network. The key is read from `ARGMAX_API_KEY`, just as in the sample.
2. **Microphone.** I will record with Apple's `AVAudioEngine`, converted to 16 kHz mono, and keep the audio only between `start` and `stop`. When `stop` arrives, it calls `whisperKitPro.transcribe(audioArray:)` once and prints the text.
   - Reason for not using the SDK's `LiveTranscriber`: it streams partial text and decides by itself when speech ends. Push to talk only needs one transcription per question, and this way has fewer moving parts.
3. **Python.** `voice/listen.py` starts the program, waits for the ready line, and offers a single call that returns the text.

I copy only what I need from `samples/`. `samples/` and `reason/` stay untouched.

## File layout

- `voice/swift/Package.swift`: tools-version 6.0. It uses the same `argmax-sdk-swift` 3.1.8 from the registry. Swift 5 language mode, so strict concurrency doesn't get in the way.
- `voice/swift/Sources/MuseVoice/main.swift`: the whole program, about 150 lines.
- `voice/listen.py`: the Python side, standard library only.
- `voice/__init__.py`: empty.
- `docs/voice-input.md`: how to run it, timings, the chat-loop lines, and Coby's steps.
- `docs/INTERFACES.md` §6: flipped to **built** when done.
- `.gitignore`: add `voice/swift/.build/` and `voice/swift/Package.resolved`.

## Interface

**stdin to Swift** (one word per line):

| Command | Effect |
|---|---|
| `start` | begin recording |
| `stop` | end recording and transcribe |
| `file <path>` | transcribe a WAV. Used for my tests without a microphone. |
| `quit` | exit |

**Swift to stdout** (one JSON object per line, flushed after each):

| Line | When |
|---|---|
| `{"event":"ready"}` | once, after the license and model load |
| `{"event":"recording"}` | after `start` |
| `{"event":"text","text":"...","seconds":2.4}` | after `stop`. `seconds` is the length of the audio. |
| `{"event":"error","message":"..."}` | on a microphone denial, license failure, missing model folder, empty recording, or bad command |

Errors before ready are followed by exit code 1. All logs go to stderr, so stdout stays clean.

**Python** (`voice/listen.py`):

- `Voice()` starts `voice/swift/.build/release/muse-voice` and waits for `ready`. The wait times out after 600 s on the first launch (the compile step) and raises `VoiceError` on an error line or exit.
- `Voice.listen(wait_for_stop=input) -> str` sends `start`, calls `wait_for_stop()`, sends `stop`, and returns the text.
- `Voice.close()` sends `quit`.
- Try it with `python -m voice.listen`. Press Enter to start, Enter to stop. It prints the text and the time from stop to text, and loops until Ctrl+C.

Two lines for the chat loop (I add them to the doc, not to `reason/`):

```python
from voice.listen import Voice; voice = Voice()   # once, at startup
question = voice.listen()                          # instead of input()
```

## Test fixtures

- Without a mic (me):
  - The `say` clip from the last test, through `file`, three times in one process.
  - The same again with the whole Python process under `sandbox-exec -p '(version 1)(allow default)(deny network-outbound (remote ip))'`, so the network is denied for it and its Swift child.
- With the mic (Coby):
  - `python -m voice.listen`, saying "What's due this week?", "Remind me to buy oat milk tomorrow at nine." and "Who emailed me about the lab report?".
  - Then the same under `sandbox-exec`.
- Key without network: I check `bw get password` with an existing session under `sandbox-exec`. Coby checks `bw unlock` under `sandbox-exec`, since only he can type the master password.
- Timing: `listen.py` measures stop to text for every question. I report each one.

## Done-when

- Coby's three spoken questions come back as the right text in one session, both online and with the network denied.
- `docs/voice-input.md` and `docs/INTERFACES.md` §6 are updated. Pushed, and the sha is reported to helper 0b.

**Steps for Coby (also in the doc):**

1. Before any of this: do the first `muse-voice` launch early. A new name means the ~4-minute Neural Engine compile runs again.
2. Click **Always Allow** on the Keychain prompt for `muse-voice`. It's a new binary, so it asks again.
3. Allow the microphone for your terminal app on the first `start`, or in System Settings → Privacy & Security → Microphone.
4. Speak the three test questions, online and then under `sandbox-exec`.
5. At the demo, load the key while still online with `export ARGMAX_API_KEY="$(bw get password 'Argmax API key - ai-hackathon-26')"`, then turn Wi-Fi off.

## Open questions

1. Executable name `muse-voice`? It's final, because the compile cache is tied to it. **Default: yes.**
2. Keep the hidden `file <path>` command? It lets tests run without a microphone. **Default: yes.**
3. Test whether a dummy `ax_` key works offline once the license is cached? It could remove the need for the vault at the demo. **Default: no.** There's a small risk it replaces the cached license, so I'd only do it with your OK.
