# Argmax runtime test: plan

Branch `argmax-runtime-test`. Nothing below runs until Coby OKs this file.
`SP` = this session's scratchpad (outside the repo). `N` = `samples/argmax-pro-sdk/native`.

## 1. Build (no key needed)

```bash
cd N && swift build -c release      # binary: N/.build/release/meeting-scribe
```

I run the built binary directly, not `swift run`, so the network test below sees only the app.
I change the sample only if it fails to build or run, and list each change in docs/argmax.md.

## 2. Key: vault to process, never printed

1. Coby runs `bw unlock --raw > SP/bw_session && chmod 600 SP/bw_session` in his own terminal (master password stays with him). I check it says `"status":"unlocked"`.
2. Each run reads the key into a shell variable and passes it only through the environment:
   ```bash
   K=$(BW_SESSION=$(cat SP/bw_session) bw get password "Argmax API key - ai-hackathon-26")
   [[ $K == ax_* && ${#K} -eq 34 ]] || { echo "key check failed"; exit 1; }   # prints pass/fail only
   ARGMAX_API_KEY=$K N/.build/release/meeting-scribe file ...
   ```
   Not `--api-key` (that would show in `ps` and the transcript). The key is never echoed, written to a file, or committed.
3. When done: `rm SP/bw_session`. No `bw lock` (it would lock other chats).

## 3. Test clip

The sample has a `file` mode, so no microphone is needed:

```bash
say -o SP/clip.wav --data-format=LEI16@16000 \
  "Muse, remind me to buy oat milk tomorrow at nine. The quick brown fox jumps over the lazy dog."
```

Run: `meeting-scribe file SP/clip.wav --no-speakers --out SP/transcripts`.
Model: the sample default, `large-v3-v20240930_626MB` (Whisper large-v3 turbo).
`--no-speakers` skips the Pyannote download; one diarized run follows if the first works.
Speed: wall clock from `/usr/bin/time -p`, on a cold run (first, includes the download) and a warm run.

## 4. Where the models go

`touch SP/marker` before the first run, then
`find ~/Documents ~/Library/Caches ~/Library/Application\ Support ~/.cache -newer SP/marker -maxdepth 6 -type d`,
then `du -sh` on what turns up. Expected: `~/Documents/huggingface/models/argmaxinc/...` (WhisperKit's default download base), to be confirmed.

## 5. Does it need the network after the first run?

What the docs say: the key is checked online on first use, and a per-device license is cached in the Keychain. CHANGELOG 3.x says init needs internet only if the Keychain is unavailable, and model loading falls back to on-disk files when offline.

Tests:
1. **Watch the online runs.** During the cold and warm runs, a background `lsof -nP -i -a -p <pid> -r 1` logs every connection's remote IP and port to `SP/net-*.log`. I resolve the IPs with `dig -x` to tell argmaxinc.com from huggingface.co.
2. **Block the network for the app only.** Warm run under
   `sandbox-exec -p '(version 1)(allow default)(deny network-outbound (remote ip))' ...`
   This denies every outbound IP connection from that process, and nothing else on the Mac. If it transcribes, the license check and model load work with no network. Wi-Fi stays on and I don't touch system settings.
3. Same as test 2 with the key variable unset, to see whether the cached license alone is enough.

Not proven by this (it goes in the doc): a real Wi-Fi-off run, which DNS or reachability checks behave differently with no interface (the sandbox makes the connection fail, it doesn't make the link go down), and how long the cached license stays valid offline.

## 6. Deliverables

`docs/argmax.md` covers how to run it, the model paths and sizes, what a Wi-Fi-off run needs, and Coby's exact Wi-Fi-off steps. Committed to `argmax-runtime-test` and pushed. I report the sha to helper 0b.

## Open questions

- How long does the cached license stay valid with no network (expiry or grace period)? I'll read `ArgmaxSDK.licenseInfo()` output if I can get it without changing the sample; otherwise it stays open.
- Muse will use live mic. Live mode needs a microphone prompt in Coby's terminal, so I won't test it here unless he asks.
- Is the 626 MB turbo model the one Muse ships with? I'm using it because it's the sample's default, not because I picked it for Muse.
