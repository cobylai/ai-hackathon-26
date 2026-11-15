# The window

The chat page (`reason/web.py`) and the Mac app that shows it.

## The page

`python -m reason.web` serves one page (`PAGE` in `reason/web.py`): HTML, CSS and a small script, with no frameworks and nothing loaded from the internet. It opens and works with the network blocked.

### Layout

- **Bar:** the chats button at the far left, the name, Speak, Discover, one status line (online or offline, items in the bank), and the bank button at the far right. Clicking the status line also shows the bank.
- **Chats (left):** saved conversations, grouped under day headings (Today, Yesterday, then the date) with the open chat tinted. The pencil button starts a new chat. Delete is two clicks: hover a chat and click ×, which turns into a red "Delete" for 3 seconds, and click it again to delete. In wide windows the chats column shows by default and is remembered. In the compact panel it starts hidden, and when opened it covers the whole panel with a **Done** button; Escape, opening a chat or starting a new one closes it.
- **Conversation:** it reads like a document. Each question is a small grey line, and the answer is plain text under it. Answer lines of the form `- when  what` (two spaces) become a table with the dates aligned. Other `- ` lines become a list. A short line ending in `:` becomes a heading. An indented line becomes a note under the row above it.
- **Under each answer:** a muted line with the source and the route and time. A bank source opens that entry in the bank. A web source opens the page.
- **Actions:** when `/ask` returns `pending`, the first line of the answer (what will happen) and **Cancel / Yes, do it** sit in one row under the answer. The result replaces the buttons in that row. Escape is Cancel.
- **Speak:** the Speak button beside Discover turns spoken answers on or off (off by default; blue when on; the browser remembers it). When on, `/ask` carries `speak: true` and the server reads the answer with the Mac's `say`, without the Source line. Asking again, starting to talk (button, ⌥ or the Mac app's hotkey) or turning it off stops the speech.
- **Follow-ups:** "and Friday?", "the first one", "who sent that?", "open it" lean on the last answer (`playbooks/followup.md`). The server keeps one conversation for the page, in memory only.
- **Suggested** (brief W): under an answer's foot, a small "Suggested" label and at most two rows (`.sugg .suggest#suggest-<n>`), each one line, one button and a ×. The button posts `/suggest/<id>`. A reply opens the draft box in that row's place; a page opens and the row says so. The × posts `/suggest/<id>/dismiss`.
- **Draft box** (`.draft`): To, Subject, an optional "Say" line with Write (replies only; posts `/draft/<id>/write`), the body (resizable), the entries used, "Nothing is sent.", **Discard** and **Open in Mail** (the only primary button; posts `/draft/open`, and the server runs `open mailto:…`, so the page and the Mac app panel behave the same). A compose answer shows its head line and the box. Keys typed in the box stay there.
- **Discover:** the Discover button in the top bar sends `discover` to `/ask`. While a discovery question is held, `/ask` returns `choices` and the answer gets **Yes / No / Skip / Stop** buttons; each reply (and the next question) is a new turn. Escape is Stop. See `playbooks/discover.md`.
- **The bank (right):** a slide-over from the right, grouped into Mail, Coursework, Notes about you and People. Each group collapses. Clicking an item shows its summary, ask and due dates. Clicking a person asks "Who is …?". People are the senders of mail in the bank.
- **Empty state:** three example questions from the playbooks (due, calendar, person). Clicking one asks it.
- **Input:** one text field with a send button and a talk button. Return sends.

### Talk

The talk control has three states:

| state | how it looks |
|---|---|
| idle | mic icon |
| listening | red level bars and "Listening". The field says "Listening — release to ask" |
| working | spinner while the words are written down |

Hold the mic button, or hold **⌥ (Option)** on its own, to talk. Release to ask, and the transcript appears as the question with a small mic before it. Escape while listening cancels it, and nothing is asked. The voice code returns the words only on release, so the window shows the level bars rather than live words.

Keyboard focus goes back to the text field after every action, except while listening. Errors say what happened and what to do, in one line, where they happened.

### Sizes

- **Show / hide the bank** at any width: the bank button at the top right (it looks pressed while the bank is shown), **Done** at the top of the bank, Escape, or ⌘B. It starts hidden.
- **Wider than 760 px:** the choice is remembered in this browser (localStorage). From 1000 px up, the open bank pushes the conversation left. Between 761 and 999 px it slides over the conversation, and asking a question closes it.
- **760 px or narrower** (the ~640 pt hotkey panel): the bank always starts hidden. When it's open it covers the whole panel, so it never hides part of an answer or the input. Asking a question, or clicking a person, closes it. The page background is transparent, so the panel's system material shows through.
- **480 px or narrower:** each table row puts its date above the item.
- The conversation column is at most 680 px wide and centred at full screen.

Colours follow the system's light and dark modes. The only accent is system blue, used for the Yes button, a selected bank item and the focus ring.

### Hooks for other code

Keep these working:

- `#q` (the text field), `#send`, `#talk`, `#status`, `#speak` (the Speak switch).
- `window.museTalk.start()` / `window.museTalk.stop()`: start and stop listening, the same as holding and releasing the talk control. These are for the Mac app's hotkey.
- `window.museFocus()`: puts the cursor in the text field (it does nothing while listening).
- `POST /ask` → `pending: true` shows Cancel / Yes. Yes and Cancel send `yes` / `no` to `/ask`.
- `POST /ask` → `choices: [[label, word]]` (discovery) shows those buttons instead; each sends its word to `/ask`. `#discover` is the Discover button.
- `#chats`: the left column, the saved chats (worker 18, brief T2). The bar's `#chatsbtn` and `body.chatsopen` show it; `#chatsclose` is Done in the panel. The list draws into `#chatlist`; `#newchat` (the pencil) sits in its head. It holds day headings (`.chday`: Today, Yesterday, then the date) and one `.chat[data-id]` per chat, newest first, titled by its first question (`.chtitle`), with `.on` on the open chat and a delete control (`.chdel`: the first click shows "Delete", the second deletes the file). `window.museChats.refresh() / .open(id) / .new() / .remove(id)`. It is a 232 px column in wide windows, and a full-panel overlay in the compact panel.
- Saved chats: `GET /chats`, `GET /chats/<id>`, `POST /chats/new`, `POST /chats/<id>/open`, `POST /chats/<id>/delete` (`reason/web.py` docstring). A reopened chat redraws its answers as they were given, with no rerun; a follow-up runs fresh against the current bank. Each launch starts a new chat.
- `#side` / `#sidebtn` / `#sideclose` and `body.bankopen`: the bank slide-over and its toggles.
- `GET /bank` rows carry `folder` (course, person, other, me) and `id`, which the sidebar groups by and the source line links by.

### Before and after

At the 640 pt panel size, light and dark (the before shots are from before the redesign):

| | light | dark |
|---|---|---|
| before | ![](window/before-panel-light.png) | ![](window/before-panel-dark.png) |
| after | ![](window/after-panel-light.png) | ![](window/after-panel-dark.png) |
| after, empty | ![](window/after-panel-empty-light.png) | ![](window/after-panel-empty-dark.png) |
| after, long due list | ![](window/after-panel-list-light.png) | ![](window/after-panel-list-dark.png) |
| after, bank open | ![](window/after-panel-bank-light.png) | ![](window/after-panel-bank-dark.png) |
| after, bank hidden | ![](window/after-panel-hidden-light.png) | ![](window/after-panel-hidden-dark.png) |
| after, bar | ![](window/after-panel-bar-light.png) | ![](window/after-panel-bar-dark.png) |
| after, chats open | ![](window/after-panel-chats-light.png) | ![](window/after-panel-chats-dark.png) |
| after, chats, delete armed | | ![](window/after-panel-chats-delete-dark.png) |

At 420 px, rows stack: ![](window/after-narrow-light.png)

Full width, bank open and hidden:

| | light | dark |
|---|---|---|
| before | ![](window/before-wide-light.png) | ![](window/before-wide-dark.png) |
| after | ![](window/after-wide-light.png) | ![](window/after-wide-dark.png) |
| after, bank hidden | ![](window/after-wide-hidden-light.png) | ![](window/after-wide-hidden-dark.png) |
| after, chats | ![](window/after-wide-chats-light.png) | ![](window/after-wide-chats-dark.png) |

The approved mock is `window/mock.html`, with its screenshots in `window/mock-*.png`.

### Checks

- `uv run python -m pytest reason/tests/test_web.py`: the page loads nothing remote, the hooks are present, and the `/bank` rows include folder and id.
- Network blocked: run the server under `sandbox-exec` with outbound network denied except localhost, then open the page and ask a question. The browser's network log shows only `localhost` requests.


## Mac app (menu bar + Fn-Space)

`app/` holds a small native app, **Muse.app**. It sits in the menu bar and shows the same local page (`python -m reason.web`, :8765) in a floating, Spotlight-style panel. It has no answer logic of its own.

### Build and run

```bash
app/build.sh                 # -> app/build/Muse.app, ad-hoc signed, ~10 s
open app/build/Muse.app
```

The build records the main checkout (`~/code/ai-hackathon-26`) as the folder it runs the servers from, because the Bonsai models live only there. Muse looks for the code in this order: `defaults write local.ai-hackathon-26.muse MuseRepo <folder>`, `MUSE_REPO`, the folder recorded at build, then `~/ai-hackathon-26`. If none has the code, the panel says so. Keep that checkout on current `main`, with `voice/swift` built (`swift build -c release`).

### Using it

- **Fn-Space, tap** (Fn = the Globe key): shows or hides the panel, with the cursor in the question box. Escape or clicking another app hides it.
- **Fn-Space, hold:** push to talk. It records while held and stops on release; the panel shows the transcript and the answer. It calls the page's own talk start and stop (`window.museTalk.start()/stop()` when the page has them, else the "Hold to talk" button).
- **Menu bar** (waveform icon): Open, Sync mail (`scripts/sync_email.py 7` into `MUSE_SYNC_BANK_DIR`, default `~/muse-bank`, never the demo bank; the last result shows under it), Discover (presses the page's Discover button), Check setup, Set Argmax key…, Quit Muse.
- The hotkey is two constants at the top of `app/Muse.swift` (`hotKeyCode`, `hotKeyFlags`). The system hotkey call ignores Fn, so Muse reads the keyboard with an event tap, which needs **Accessibility** for Muse. It swallows Fn-Space, so no space reaches the app in front.

### First launch (once, online or off)

1. It asks for the Argmax `ax_` key and keeps it in the login Keychain as **"Muse Argmax key"**. It is never written to the repo, the app or a file. Change it with Set Argmax key….
2. macOS asks for the **microphone**, **Calendar** (Automation) and **Accessibility** (for Fn-Space) for Muse. Allow all three; Accessibility opens System Settings, where you turn Muse on. The hotkey starts working within 2 s, no relaunch. Muse starts the Python server, so macOS charges the microphone and Calendar allows to Muse; asking at launch means nothing asks mid-demo.

### What it does on every launch

1. Reads the key from the Keychain and gives it to the window server it starts as `ARGMAX_API_KEY`. `ARGMAX_MODEL_FOLDER`, `MUSE_BANK_DIR` (default `~/muse-demo-bank`) and `MUSE_CALENDAR` pass through if set.
2. Starts `scripts/serve_bonsai.sh 4B` and `uv run python -m reason.web --no-open` if :8080 or :8765 doesn't answer, and shows "Starting… Bonsai ready · window starting" meanwhile. If one exits, the panel names it and shows the last log lines. Logs: `~/Library/Logs/Muse/`.
3. Checks setup and lists any problem in the panel, one line each with the fix: the key, the Whisper model folder, the `argmax-voice` binary, Bonsai 4B on :8080, voice ready in the window server, microphone allowed, Accessibility allowed, Calendar allowed and the "Muse demo" calendar present, and the checkout not behind `origin/main` (as of its last fetch, no network). All fine: it shows the page.

**After a rebuild:** the app is signed ad hoc, so macOS treats each build as a new app. It may ask for the microphone, Calendar and Keychain again, and Accessibility has to be turned off and on again for Muse. Build once before the demo, then don't rebuild.

**Quit** stops only what Muse started (SIGINT so Python closes voice, then SIGTERM). A Bonsai or window server that was already running stays up.

If the window server was started from a terminal instead, Muse uses it as it is; its voice then depends on that terminal's key and microphone allow, and Check setup says so if voice isn't ready.

### Ship to another Mac

```bash
app/make_dmg.sh              # -> app/dist/Muse.dmg (~100 KB), app/build/ untouched
```

The disk image holds `Muse.app` (no folder recorded, so it looks in `~/ai-hackathon-26` or the `defaults` setting), `INSTALL.html`, `setup.sh` and an Applications shortcut. No models, keys, bank or `data/`.

- **INSTALL.html** has two paths. One command: `bash /Volumes/Muse/setup.sh`. Do it yourself: one numbered step per part, each with its official link and exact command: Xcode, uv, the repo (private), Python packages and Playwright Chromium, Bonsai 2 4B with its own venv, the Whisper model, the Argmax registry login and your own keys, building `voice/swift`, the demo bank and "Muse demo" calendar, then opening Muse. Each part installs on its own, so Bonsai, Argmax and the harness are visibly separate.
- **setup.sh** prints each command before it runs it, asks before every download or install, skips what's already there, never uses `sudo`, and reads the Argmax secret token hidden. It ends with `defaults write … MuseRepo <folder>`.
- **First open:** Muse is ad-hoc signed and not notarized. Right-click → Open, or `xattr -dr com.apple.quarantine /Applications/Muse.app`.
- **Each Mac needs its own Argmax key**, and the first voice start on a new Mac takes several minutes (one-time Neural Engine compile).
