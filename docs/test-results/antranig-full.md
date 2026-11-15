# Flux full test suite: Antranig, 2026-11-15 (running notes; final report to follow)

Tested on main 91dd76c, MacBook Pro, Apple Silicon. Findings so far, for Coby.

## Findings for Coby

1. **Privacy link is a 404 (first screen).** The Welcome screen of Set Up Flux links to https://cobydev.com/flux/privacy (`app/Flux.swift:557`, `docs/window.md:125`). Both /flux/privacy and /flux return 404 today. `docs/STATE.md:43` says the pages are on cobydev branch `feature/flux-page` and not merged to main. Fix: merge and deploy that branch, or point the link at a page that exists, before anyone is sent the DMG.
2. **Name collision with f.lux.** f.lux installs as `/Applications/Flux.app` (bundle org.herf.Flux). Flux.dmg's app is also `Flux.app`. Dragging it onto Applications replaces f.lux (Finder asks, but a tester can say yes without noticing). My own `cp -R` into /Applications merged the two bundles and damaged f.lux; I restored it from f.lux's official download. Consider a different app file name (or a display name that differs from the file name) in the DMG.
3. **Install prompts add up.** During first run macOS asked about the Documents folder, the Downloads folder, and the login keychain (twice: the old "Muse Argmax key" item and another). Likely causes: the Whisper model path under ~/Documents/huggingface (move it to ~/Library/Application Support/Flux), opening the DMG from Downloads, and Flux reading the old Muse-named keychain item (ask for the key once under the Flux name instead). Not verified screen by screen.
4. **Permissions screen is five separate Allows** (Accessibility, Microphone, Calendar, Reminders, Mail). macOS cannot grant them in one go. Suggest: require only Accessibility and Microphone up front, ask for Calendar, Reminders and Mail on first use, or add one "Allow all" button that runs them in order. Consider a hotkey that needs no Accessibility permission.
5. **Bonsai now binds 127.0.0.1:8080** (`lsof` shows `Python 127.0.0.1:8080`). Round 1 finding is fixed.
6. **Install timing:** first-run Install (Python tools, Bonsai 2 4B about 1.8 GB on disk, voice program build of about 34 s, speech model already present) took about 3 minutes on this Mac.
