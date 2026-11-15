# Argmax speech-to-text: runtime test results

Tested 2026-11-14 on Coby's MacBook Pro (MacBookPro18,2, macOS 26.6.2) with SDK 3.1.8 and the real `ax_` key. The plan is in `docs/plans/argmax-runtime-test.md`.

## Result in one paragraph

**Argmax runs with no network, once the model is on disk and loaded from its folder.**

- The sample transcribed an audio file with the real key, unchanged.
- Each launch contacts Argmax's server (`api.argmaxinc.com`) and Hugging Face, even when warm.
- **The license:** a failed check doesn't stop the app. With the model loaded from its folder (`ARGMAX_MODEL_FOLDER`, i.e. `modelFolder:` and `download: false`), the transcription worked with all network denied (run F).
- **The downloader:** without that folder setting, the Hugging Face downloader hangs for 60 s when connections are blocked, because macOS still reports a network.
- **The app:** Flux's voice program (`argmax-voice`, `docs/voice-input.md`) always loads from the folder. It was proven by voice with the network denied in both the chat loop and the window.
- **Still unproven:** one real Wi-Fi-off run of the whole app (`docs/PARTNER-TESTING.md`).

**New tester or Mac:** you need your own `ax_` key (one per application, from Argmax at the event; don't use Coby's), plus the registry login below. The first run must be online to activate the license and download the model.

## How to run it

```bash
cd samples/argmax-pro-sdk/native
swift build -c release                     # once; ~65 s
export ARGMAX_API_KEY="$(bw get password 'Argmax API key - ai-hackathon-26')"   # needs BW_SESSION
.build/release/meeting-scribe file <clip.wav> --no-speakers --out <folder>
```

Test clip used (6.7 s, 16 kHz mono):

```bash
say -o clip.wav --data-format=LEI16@16000 "Flux, remind me to buy oat milk tomorrow at nine. The quick brown fox jumps over the lazy dog."
```

The transcript was: `Flux, remind me to buy oat milk tomorrow at 9. The quick brown fox jumps over the lazy dog.` Language detected: en. Every word is correct, and "nine" was written as "9".

The sample built and ran unchanged on main. One change was added afterwards for offline use:

- `samples/argmax-pro-sdk/native/Sources/MeetingScribe/Bootstrap.swift`: a new env var, `ARGMAX_MODEL_FOLDER`. When it's set, `WhisperKitProConfig` gets `modelFolder:` and `download: false`, so the Hugging Face downloader is skipped entirely. When it's unset, the sample behaves as before. It applies to both `file` and `live`.

## Speed

| Run | What | Time |
|---|---|---|
| A, cold | download + first-time Neural Engine compile + transcribe | ~4–5 min in total. Of that, model load (compile) took 238.6 s and transcription 1.4 s (from the SDK's own timing). |
| B, warm | launch + license + model load + transcribe | **4.5 s** wall clock for the whole process |

Transcription itself is fast (1.4 s for 6.7 s of audio). The warm cost is mostly loading the model at launch. So for Flux, keep one process running rather than launching one per question.

## Where the models are

All of these are outside the repo:

| Path | Size | What |
|---|---|---|
| `~/Documents/huggingface/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB/` | 615 MB | The ASR model (`AudioEncoder`, `TextDecoder`, `MelSpectrogram` `.mlmodelc`) |
| `~/Documents/huggingface/models/openai/whisper-large-v3/` | 2.7 MB | Tokenizer files |
| `~/Library/Caches/meeting-scribe/` | 133 MB | The compiled Neural Engine cache. Without it the next launch spends ~4 min recompiling. Don't clear it before the demo. |
| `~/Library/Application Support/com.argmax.sdk/argmax.queueFolder/` | ~40 KB | The SDK's usage-event queue (model loaded, inference done). It is sent on the next online launch, and the online runs did flush it. |

Model: `large-v3-v20240930_626MB` (Whisper large-v3 turbo, the sample default). It comes from the open-source Hugging Face repo `argmaxinc/whisperkit-coreml`, not `whisperkit-pro`.

## The offline question

**Update (run F): the license works with no network.** With `ARGMAX_MODEL_FOLDER` set and all outbound IP blocked for the process, `file` mode transcribed the clip correctly. The first such launch took 27.9 s, a one-time load from the new folder path. The next two took **3.2 s** each, one blocked and one online. No connection succeeded (only `*:*` sockets were seen, none connected). So with the model loaded from a folder, nothing in the launch needs the network. The key is still checked online when a network exists, but a failed check doesn't stop the app. The details of the earlier runs follow.

**What was observed:** remote connections, logged with `lsof` every 0.2 s while the process ran.

| Run | Setup | Result | Connections seen |
|---|---|---|---|
| A | online, cold | transcribed | `huggingface.co` (CloudFront 3.168.73.x), `api.argmaxinc.com` (3.16.240.40), and several other AWS us-east hosts (54.147.56.11, 54.225.198.112, 34.231.87.187; owner not resolved) |
| B | online, warm | transcribed | `api.argmaxinc.com` (18.188.193.42) and `huggingface.co` |
| C | all outbound IP blocked (`sandbox-exec`) | **failed at 60 s**: `Model not found ... downloadError("The request timed out.")` | none (blocked) |
| D | as C, plus `HF_ENDPOINT=http://127.0.0.1:9` | same failure | none |
| D2 | as D, with localhost allowed | same failure, 60 s | none |
| E | online, with `HF_ENDPOINT=http://127.0.0.1:9` | transcribed | `api.argmaxinc.com` and still `huggingface.co` |

**What that means:**

1. **The key is checked with Argmax's server at every launch.** Run B, warm, connected to `api.argmaxinc.com`. Whether that's the license refresh or the usage queue upload can't be told apart from outside, since both go to that host.
2. **A failed check doesn't stop the launch.** In C, the only error came from the Hugging Face downloader (`WhisperKit.swift`, "Model not found"). The whole run took 60.2 s, which is exactly one download timeout, so the license step didn't stall or throw before it. This matches the docs: the license is cached per device in the Keychain, and init needs internet only if the Keychain is unavailable.
3. **The model step needs either a real "no network" signal or a local folder.**
   - The downloader (`HubApi.swift` in argmax-oss-swift) uses on-disk files only when `NWPathMonitor` reports no link. Wi-Fi off triggers that. Blocked connections don't, so C timed out.
   - It **ignores `HF_HUB_OFFLINE`**.
   - `HF_ENDPOINT` is honored by part of it, but WhisperKit's model download passes its own `huggingface.co` endpoint (run E still connected there).
   - So for Flux, pass the local model path (`modelFolder:` in the WhisperKit config). That skips the download step entirely and doesn't depend on how macOS reports the network.

**Still unproven:**
- A real Wi-Fi-off run. Coby's steps are below.
- That the license works when it is truly offline: now shown by run F with connections blocked. It is still to be confirmed with Wi-Fi off.
- How long the cached license lasts offline.
- Whether the queue upload or license refresh matters later.
- Live microphone mode (not tested; it needs a mic-permission prompt).
- C/D/D2 only show what happens when connections fail. They can't show offline mode.

## Wi-Fi-off run

The sample-only Wi-Fi-off run and the microphone step that used to be here are replaced:
- The microphone is granted and voice is proven through `argmax-voice` (`docs/voice-input.md`).
- The one remaining Wi-Fi-off run covers the whole app. Load the key while online, start Bonsai and the window, turn Wi-Fi off, then ask the demo questions. Steps are in `docs/PARTNER-TESTING.md`.

## For Flux (done)

- `voice/` is built and on main. `argmax-voice` stays running, loads from the model folder with downloads off, and does push to talk over stdin/stdout. See `docs/voice-input.md`.
- Its compile cache is `~/Library/Caches/argmax-voice/`; meeting-scribe's own cache is `~/Library/Caches/meeting-scribe/`. Each is named after its executable, so a rename means a ~4-minute recompile.
