# Argmax speech-to-text: runtime test results

Tested 2026-11-14 on Coby's MacBook Pro (MacBookPro18,2, macOS 26.6.2) with SDK 3.1.8 and the real `ax_` key. The plan is in `docs/plans/argmax-runtime-test.md`.

## Result in one paragraph

The sample transcribes an audio file with the real key, unchanged. The model is on disk (615 MB). Each launch contacts Argmax's server (`api.argmaxinc.com`) and Hugging Face, even when warm. With all network blocked for the app, it **failed after 60 s in the model downloader**, not in the license check. The cause is that the downloader only uses its on-disk copy when macOS reports no network link at all. Blocking connections doesn't do that, but turning Wi-Fi off does. So a Wi-Fi-off run should work, but that still has to be proven by Coby's run below.

## How to run it

```bash
cd samples/argmax-pro-sdk/native
swift build -c release                     # once; ~65 s
export ARGMAX_API_KEY="$(bw get password 'Argmax API key - ai-hackathon-26')"   # needs BW_SESSION
.build/release/meeting-scribe file <clip.wav> --no-speakers --out <folder>
```

Test clip used (6.7 s, 16 kHz mono):

```bash
say -o clip.wav --data-format=LEI16@16000 "Muse, remind me to buy oat milk tomorrow at nine. The quick brown fox jumps over the lazy dog."
```

The transcript was: `Muse, remind me to buy oat milk tomorrow at 9. The quick brown fox jumps over the lazy dog.` Language detected: en. Every word is correct, and "nine" was written as "9".

The sample built and ran unchanged on main. One change was added afterwards for offline use:

- `samples/argmax-pro-sdk/native/Sources/MeetingScribe/Bootstrap.swift`: a new env var, `ARGMAX_MODEL_FOLDER`. When it's set, `WhisperKitProConfig` gets `modelFolder:` and `download: false`, so the Hugging Face downloader is skipped entirely. When it's unset, the sample behaves as before. It applies to both `file` and `live`.

## Speed

| Run | What | Time |
|---|---|---|
| A, cold | download + first-time Neural Engine compile + transcribe | ~4–5 min in total. Of that, model load (compile) took 238.6 s and transcription 1.4 s (from the SDK's own timing). |
| B, warm | launch + license + model load + transcribe | **4.5 s** wall clock for the whole process |

Transcription itself is fast (1.4 s for 6.7 s of audio). The warm cost is mostly loading the model at launch. So for Muse, keep one process running rather than launching one per question.

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
   - So for Muse, pass the local model path (`modelFolder:` in the WhisperKit config). That skips the download step entirely and doesn't depend on how macOS reports the network.

**Still unproven:**
- A real Wi-Fi-off run. Coby's steps are below.
- That the license works when it is truly offline: now shown by run F with connections blocked. It is still to be confirmed with Wi-Fi off.
- How long the cached license lasts offline.
- Whether the queue upload or license refresh matters later.
- Live microphone mode (not tested; it needs a mic-permission prompt).
- C/D/D2 only show what happens when connections fail. They can't show offline mode.

## Coby's Wi-Fi-off run

Do steps 1–2 **while still online**.

1. Unlock the vault and load the key into this terminal:
   ```bash
   export BW_SESSION="$(bw unlock --raw)"
   ```
   ```bash
   export ARGMAX_API_KEY="$(bw get password 'Argmax API key - ai-hackathon-26')"
   ```
2. Make the clip and do one online run to be sure everything is cached:
   ```bash
   cd ~/code/ai-hackathon-26/.claude/worktrees/argmax-runtime-test-743dfa/samples/argmax-pro-sdk/native
   ```
   ```bash
   say -o /tmp/clip.wav --data-format=LEI16@16000 "Muse, remind me to buy oat milk tomorrow at nine."
   ```
   ```bash
   .build/release/meeting-scribe file /tmp/clip.wav --no-speakers --out /tmp/transcripts
   ```
3. Turn Wi-Fi off from the menu bar. Also quit any VPN (Tailscale etc.) and unplug Ethernet. If macOS still thinks a network exists, the downloader won't switch to offline mode.
4. Run the same command again, timed:
   ```bash
   time .build/release/meeting-scribe file /tmp/clip.wav --no-speakers --out /tmp/transcripts
   ```
   Also run it with the local model folder, which is the setup Muse should use:
   ```bash
   ARGMAX_MODEL_FOLDER=~/Documents/huggingface/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB .build/release/meeting-scribe file /tmp/clip.wav --no-speakers --out /tmp/transcripts
   ```
5. Paste the whole output into the chat. A transcript means offline works. A license error or the 60 s "Model not found" error means it doesn't, and the error text says which part failed.
6. Turn Wi-Fi back on.

## Coby: microphone permission (required before the demo)

Live mode uses the same model as file mode, so there's nothing extra to download. But macOS has to allow the microphone for the terminal app that will run it, and only you can click that prompt.

1. In the terminal app you'll demo from, with `ARGMAX_API_KEY` set as in step 1 above:
   ```bash
   cd ~/code/ai-hackathon-26/.claude/worktrees/argmax-runtime-test-743dfa/samples/argmax-pro-sdk/native
   ```
   ```bash
   .build/release/meeting-scribe live
   ```
2. Click **Allow** on the microphone prompt. If no prompt appears and nothing is transcribed, go to System Settings → Privacy & Security → Microphone and turn your terminal app on.
3. Say a sentence. You should see the words appear. Press Ctrl+C to stop.
4. If you'll demo from a different app (a Muse app instead of the terminal), that app needs its own permission. Grant it the same way before the demo.

## For Muse

- How text gets to Python, proposed in `docs/INTERFACES.md` section 6: a long-running Swift process writes one line of text per utterance to stdout, and Python reads it.
- The Swift program should pass the local model folder (`modelFolder:` with `download: false`, as `ARGMAX_MODEL_FOLDER` does) so it never tries to download. Run F shows this works with no network.
- Keep the 133 MB compile cache. The Swift program should use a fixed bundle or executable name, because the cache folder is named after it (`~/Library/Caches/meeting-scribe/`). A new name means a ~4-minute recompile on its first launch, so do that first launch before the demo.
