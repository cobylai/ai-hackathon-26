# Plan: argmax-runtime-test

Branch `argmax-runtime-test`. Nothing runs until Coby types OK.
`N` = `samples/argmax-pro-sdk/native`. `SP` = this chat's scratchpad, outside the repo.

## Approach

I will test with an **audio file**, not the live mic. The sample has `meeting-scribe file`, so no microphone prompt is needed.

**What the SDK source says (3.1.8 and argmax-oss-swift 1.1.1):**
- Models come through a built-in copy of the Hugging Face downloader (`HubApi.swift`). They are fetched from `huggingface.co`, repo `argmaxinc/whisperkit-pro`.
- That downloader **ignores `HF_HUB_OFFLINE`**. It switches to on-disk files only when macOS reports no network link (`NWPathMonitor`). A real Wi-Fi-off run does that; blocking connections does not. So I will not set `HF_HUB_OFFLINE`.
- Licensing: the first run checks the `ax_` key online and caches a per-device license in the Keychain. The CHANGELOG says init needs internet only if the Keychain is unavailable. The license code is closed, so whether it contacts the server at every launch has to be observed.

**Commands, in order:**
1. `cd N && swift build -c release`, then run `N/.build/release/meeting-scribe` directly (not `swift run`).
2. Coby unlocks the vault (see the steps for Coby below). I check that `bw status` says unlocked.
3. Each run gets the key like this. It is never printed, written to a file, or passed as `--api-key`:
   `K=$(BW_SESSION=$(cat SP/bw_session) bw get password "Argmax API key - ai-hackathon-26")`, then
   `[[ $K == ax_* && ${#K} -eq 34 ]]`, which prints only "ok" or "fail", then
   `ARGMAX_API_KEY=$K N/.build/release/meeting-scribe file SP/clip.wav --no-speakers --out SP/transcripts`.
4. **Run A, online and cold:** downloads the model and activates the license. Timed with `/usr/bin/time -p`. A background `lsof -nP -i -a -p <pid> -r 1 > SP/netA.log` records every remote IP, which I resolve with `dig -x`.
5. **Run B, online and warm:** same command and logging. If B connects to Argmax's server (`api.argmaxinc.com`), the license is checked online at every launch.
6. **Run C, network blocked for this process only:** the same command under `sandbox-exec -p '(version 1)(allow default)(deny network-outbound (remote ip))'`. Wi-Fi stays on and no settings change.
7. **Run D:** like C, with `HF_ENDPOINT=http://127.0.0.1:9` (an env var the downloader does honor). If C fails in the downloader, D shows whether the failure is the model step or the license step.
8. `rm SP/bw_session` (no `bw lock`, which would lock every chat).

**How I'll read the results:**
- If B contacts Argmax's server, the license is checked online at every launch.
- If C prints a transcript, the license works offline. If C fails with a license or activation error, it **needs the network at launch**.
- If C fails only in the model download step, the result is inconclusive. The link is still up, so the downloader doesn't switch to on-disk files. Only Coby's real Wi-Fi-off run settles it.

**Expected sample changes:** none. If a change is needed to build or run, I'll list each one in `docs/argmax.md`.

## File layout

- `docs/plans/argmax-runtime-test.md`: this plan.
- `docs/argmax.md`: results, how to run it, model paths, and the Wi-Fi-off steps.
- Outside the repo:
  - The models. I expect them under `~/Documents/huggingface/models/argmaxinc/whisperkit-pro/` (the downloader's default is `~/Documents/huggingface`). I'll confirm with `find -newer SP/marker` and size them with `du -sh`.
  - The clip, transcripts and logs, all in `SP`.

## Interface

The command line only. Muse code is not touched.

## Test fixtures

- Clip: `say -o SP/clip.wav --data-format=LEI16@16000 "Muse, remind me to buy oat milk tomorrow at nine. The quick brown fox jumps over the lazy dog."`
- Model: `large-v3-v20240930_626MB` (Whisper large-v3 turbo, about 626 MB per its name). It is the sample's default.
- `--no-speakers`, so the Pyannote diarizer is not downloaded.

## Done-when

- A transcript of the clip from the real key, with its speed (cold and warm).
- The model path and size recorded.
- An offline answer: whether the license is checked at every launch, and whether it runs with connections blocked. What stays unproven is stated.
- `docs/argmax.md` committed and pushed, with the sha sent to helper 0b.

**Steps for Coby:**
1. Now: run `bw unlock --raw > SP/bw_session && chmod 600 SP/bw_session` in your terminal. I'll send the full path.
2. Later, the real Wi-Fi-off run: turn Wi-Fi off, then run `cd N && ARGMAX_API_KEY=... .build/release/meeting-scribe file <clip> --no-speakers`. The exact line goes in `docs/argmax.md`. Paste me the output, then turn Wi-Fi back on.
3. Required before the demo: run `meeting-scribe live` once and allow the microphone for your terminal app. It uses the same model, so there's no extra download.

Adjustments from thinker 0 after approval: the Wi-Fi-off run comes right after A and B pass, and the microphone step is required. The 34-character key check stays, because `samples/argmax-pro-sdk/shared/.env.example` documents that ax_ keys are 34 chars.

## Open questions

1. Test only the file mode now and leave live mic to Coby? **Default: yes.**
2. Use the sample's 626 MB turbo model, even if Muse later picks a smaller one? **Default: yes.**
3. Also do one run with speakers (downloads Pyannote) so that model is cached too? **Default: no, unless Muse needs speaker labels.**
