# The window

## Mac app (menu bar + Control-Space)

`app/` holds a small native app, **Muse.app**. It sits in the menu bar and shows the same local page (`python -m reason.web`, :8765) in a floating, Spotlight-style panel. It has no answer logic of its own.

### Build and run

```bash
app/build.sh                 # -> app/build/Muse.app, ad-hoc signed, ~10 s
open app/build/Muse.app
```

The build records the main checkout (`~/code/ai-hackathon-26`) as the folder it runs the servers from, because the Bonsai models live only there. `MUSE_REPO=<folder>` at build or launch time points it somewhere else. Keep that checkout on current `main`, with `voice/swift` built (`swift build -c release`).

### Using it

- **Control-Space, tap:** shows or hides the panel, with the cursor in the question box. Escape or clicking another app hides it.
- **Control-Space, hold:** push to talk. It records while held and stops on release; the panel shows the transcript and the answer. It calls the page's own talk start and stop (`window.museTalk.start()/stop()` when the page has them, else the "Hold to talk" button).
- **Menu bar** (waveform icon): Open, Sync mail (`scripts/sync_email.py 7`; the last result shows under it), Discover (disabled until it's built), Check setup, Set Argmax key…, Quit Muse.
- The hotkey is one constant at the top of `app/Muse.swift` (`hotKeyCode`, `hotKeyModifiers`). It uses the system hotkey call, so it needs no Accessibility permission. Control-Space is also the macOS "previous input source" shortcut; that shortcut is off on Coby's Mac.

### First launch (once, online or off)

1. It asks for the Argmax `ax_` key and keeps it in the login Keychain as **"Muse Argmax key"**. It is never written to the repo, the app or a file. Change it with Set Argmax key….
2. macOS asks for the **microphone** and for **Calendar** (Automation) for Muse. Click Allow on both. Muse starts the Python server, so macOS charges both allows to Muse; asking at launch means nothing asks mid-demo.

### What it does on every launch

1. Reads the key from the Keychain and gives it to the window server it starts as `ARGMAX_API_KEY`. `ARGMAX_MODEL_FOLDER`, `MUSE_BANK_DIR` (default `~/muse-demo-bank`) and `MUSE_CALENDAR` pass through if set.
2. Starts `scripts/serve_bonsai.sh 4B` and `uv run python -m reason.web --no-open` if :8080 or :8765 doesn't answer, and shows "Starting… Bonsai ready · window starting" meanwhile. If one exits, the panel names it and shows the last log lines. Logs: `~/Library/Logs/Muse/`.
3. Checks setup and lists any problem in the panel, one line each with the fix: the key, the Whisper model folder, the `argmax-voice` binary, Bonsai 4B on :8080, voice ready in the window server, microphone allowed, Calendar allowed and the "Muse demo" calendar present. All fine: it shows the page.

**Quit** stops only what Muse started (SIGINT so Python closes voice, then SIGTERM). A Bonsai or window server that was already running stays up.

If the window server was started from a terminal instead, Muse uses it as it is; its voice then depends on that terminal's key and microphone allow, and Check setup says so if voice isn't ready.
