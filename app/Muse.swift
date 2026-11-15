// Muse menu-bar app: a Spotlight-style panel that shows the local window page
// (python -m reason.web) and one global hotkey. No answer logic here.
//   Tap the hotkey: show/hide the panel, cursor in the text field.
//   Hold it: push to talk (the page's own talk start/stop).
// On launch: asks once for the Argmax key (kept in the login Keychain), asks for the
// microphone and Calendar allows, starts Bonsai and the window server if they aren't
// running, and lists any setup problem in the panel. Quit stops only what it started.
import AVFoundation
import Carbon.HIToolbox
import Cocoa
import Security
import WebKit

// ---- Settings (change here) ----
let hotKeyCode = Int64(kVK_Space)           // the one hotkey: Fn-Space (Fn = the Globe key)
let hotKeyFlags: CGEventFlags = .maskSecondaryFn
let hotKeyName = "Fn-Space"
let holdSeconds = 0.35                       // held longer than this = push to talk
let windowURL = URL(string: "http://localhost:8765/")!
let bonsaiURL = URL(string: "http://localhost:8080/v1/models")!
let statusURL = URL(string: "http://localhost:8765/status")!
let panelSize = NSSize(width: 640, height: 440)
let keychainService = "Muse Argmax key"
let keychainAccount = "ARGMAX_API_KEY"

let env = ProcessInfo.processInfo.environment
// Where the repo is: `defaults write local.ai-hackathon-26.muse MuseRepo <path>`, then MUSE_REPO,
// then the path baked in at build time (empty in the DMG build), then ~/ai-hackathon-26.
let repo: String = [UserDefaults.standard.string(forKey: "MuseRepo"), env["MUSE_REPO"],
                    Bundle.main.object(forInfoDictionaryKey: "MuseRepo") as? String]
    .compactMap { $0 }.first { !$0.isEmpty } ?? (NSHomeDirectory() + "/ai-hackathon-26")
let bankDir: String = env["MUSE_BANK_DIR"] ?? (NSHomeDirectory() + "/muse-demo-bank")
// Sync mail writes real Gmail here, never into the demo bank.
let syncBankDir: String = env["MUSE_SYNC_BANK_DIR"] ?? (NSHomeDirectory() + "/muse-bank")
let calendarName: String = env["MUSE_CALENDAR"] ?? "Muse demo"
let modelFolder: String = env["ARGMAX_MODEL_FOLDER"].flatMap { $0.isEmpty ? nil : $0 } ?? (NSHomeDirectory() +
    "/Documents/huggingface/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB")
let voiceBin: String = env["MUSE_VOICE_BIN"] ?? (repo + "/voice/swift/.build/release/argmax-voice")
let logDir = NSHomeDirectory() + "/Library/Logs/Muse"

// ---- Keychain (login keychain, generic password) ----
enum Keychain {
    static var base: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: keychainService,
         kSecAttrAccount as String: keychainAccount]
    }
    static func read() -> String? {
        var q = base; q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }
    static func save(_ key: String) -> Bool {
        let data = Data(key.utf8)
        if SecItemUpdate(base as CFDictionary, [kSecValueData as String: data] as CFDictionary) == errSecSuccess { return true }
        var q = base; q[kSecValueData as String] = data
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }
}

// ---- Small helpers ----
func get(_ url: URL, timeout: TimeInterval = 1) -> Data? {
    var req = URLRequest(url: url); req.timeoutInterval = timeout
    let sem = DispatchSemaphore(value: 0); var out: Data?
    URLSession.shared.dataTask(with: req) { d, resp, _ in
        if (resp as? HTTPURLResponse)?.statusCode == 200 { out = d ?? Data() }
        sem.signal()
    }.resume()
    sem.wait()
    return out
}

func html(_ s: String) -> String {
    s.replacingOccurrences(of: "&", with: "&amp;").replacingOccurrences(of: "<", with: "&lt;")
}

// ---- Panel ----
final class Panel: NSPanel {
    var onEscape: () -> Void = {}
    override var canBecomeKey: Bool { true }
    override func cancelOperation(_ sender: Any?) { onEscape() }
}

// ---- One server the app may start ----
final class Server {
    let name: String, probe: URL, command: String, log: String
    var proc: Process?
    var failure: String?
    init(name: String, probe: URL, command: String) {
        self.name = name; self.probe = probe; self.command = command
        self.log = logDir + "/\(name.lowercased()).log"
    }

    func answers() -> Bool { get(probe) != nil }

    /// Start it unless it already answers. A login shell, so PATH has uv.
    func startIfNeeded(extraEnv: [String: String] = [:]) {
        failure = nil
        if answers() { return }
        try? FileManager.default.createDirectory(atPath: logDir, withIntermediateDirectories: true)
        FileManager.default.createFile(atPath: log, contents: nil)
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        p.arguments = ["-l", "-c", "exec " + command]
        p.currentDirectoryURL = URL(fileURLWithPath: repo)
        var e = env
        e["MUSE_BANK_DIR"] = bankDir
        for (k, v) in extraEnv { e[k] = v }
        p.environment = e
        let fh = FileHandle(forWritingAtPath: log)
        p.standardOutput = fh; p.standardError = fh
        p.standardInput = FileHandle.nullDevice
        do { try p.run(); proc = p } catch { failure = "could not run: \(error.localizedDescription)" }
    }

    var exited: Bool { proc.map { !$0.isRunning } ?? false }

    func lastLog(_ n: Int = 4) -> String {
        let text = (try? String(contentsOfFile: log, encoding: .utf8)) ?? ""
        return text.split(separator: "\n").suffix(n).joined(separator: "\n")
    }

    /// Stop only what this app started: SIGINT (lets Python close voice), then SIGTERM, then SIGKILL.
    func stop() {
        guard let p = proc, p.isRunning else { proc = nil; return }
        p.interrupt()
        var deadline = Date().addingTimeInterval(6)
        while p.isRunning && Date() < deadline { usleep(100_000) }
        if p.isRunning { p.terminate() }
        deadline = Date().addingTimeInterval(3)
        while p.isRunning && Date() < deadline { usleep(100_000) }
        if p.isRunning { kill(p.processIdentifier, SIGKILL) }
        proc = nil
    }
}

// ---- App ----
final class App: NSObject, NSApplicationDelegate, NSWindowDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    var item: NSStatusItem!
    var panel: Panel!
    var web: WKWebView!
    var syncItem: NSMenuItem!
    var syncInfo: NSMenuItem!
    var ready = false
    var hotDown = false, holding = false
    var holdTimer: Timer?
    var sigterm: DispatchSourceSignal?
    var argmaxKey: String?

    let bonsai = Server(name: "Bonsai", probe: bonsaiURL, command: "scripts/serve_bonsai.sh 4B")
    let window = Server(name: "Window", probe: statusURL, command: "uv run python -m reason.web --no-open")

    func applicationDidFinishLaunching(_ n: Notification) {
        makeMenu()
        makePanel()
        registerHotKey()
        signal(SIGTERM, SIG_IGN)   // kill <pid> quits cleanly too
        sigterm = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
        sigterm?.setEventHandler { NSApp.terminate(nil) }
        sigterm?.resume()
        if Setup.needed() { setup.show { self.start() } } else { start() }
    }

    let setup = Setup()

    /// After setup: show the panel and bring the servers up.
    func start() {
        guard !started else { return }
        started = true
        argmaxKey = Keychain.read()
        showMessage("Starting…")
        show()
        DispatchQueue.global().async { self.bringUp() }
    }
    var started = false

    func applicationWillTerminate(_ n: Notification) {
        window.stop(); bonsai.stop()
    }

    // ---- Menu bar ----
    func makeMenu() {
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        let img = NSImage(systemSymbolName: "waveform", accessibilityDescription: "Muse")
        img?.isTemplate = true
        item.button?.image = img
        let m = NSMenu()
        m.autoenablesItems = false
        m.addItem(withTitle: "Open", action: #selector(openPanel), keyEquivalent: "")
        syncItem = m.addItem(withTitle: "Sync mail", action: #selector(syncMail), keyEquivalent: "")
        syncInfo = m.addItem(withTitle: "", action: nil, keyEquivalent: "")
        syncInfo.isEnabled = false; syncInfo.isHidden = true
        m.addItem(withTitle: "Discover", action: #selector(discover), keyEquivalent: "")
        m.addItem(.separator())
        m.addItem(withTitle: "Set Up Muse…", action: #selector(openSetup), keyEquivalent: "")
        m.addItem(withTitle: "Check setup", action: #selector(checkSetup), keyEquivalent: "")
        m.addItem(withTitle: "Set Argmax key…", action: #selector(setKey), keyEquivalent: "")
        m.addItem(.separator())
        m.addItem(withTitle: "Quit Muse", action: #selector(quit), keyEquivalent: "q")
        for i in m.items where i.action != nil { i.target = self }
        item.menu = m
    }

    // ---- Panel ----
    func makePanel() {
        panel = Panel(contentRect: NSRect(origin: .zero, size: panelSize),
                      styleMask: [.borderless, .nonactivatingPanel],   // no title strip: the page owns the top
                      backing: .buffered, defer: false)
        panel.hasShadow = true
        panel.isMovableByWindowBackground = false
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
        panel.backgroundColor = .clear
        panel.isOpaque = false
        panel.delegate = self
        panel.onEscape = { [weak self] in self?.hide() }

        let fx = NSVisualEffectView(frame: NSRect(origin: .zero, size: panelSize))
        fx.material = .popover; fx.blendingMode = .behindWindow; fx.state = .active
        fx.wantsLayer = true; fx.layer?.cornerRadius = 14; fx.layer?.masksToBounds = true
        fx.autoresizingMask = [.width, .height]

        let cfg = WKWebViewConfiguration()
        let js = """
        document.addEventListener('keydown', e => {
          if (e.key === 'Escape' && !e.defaultPrevented) window.webkit.messageHandlers.muse.postMessage('hide');
        });
        """
        cfg.userContentController.addUserScript(WKUserScript(source: js, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        cfg.userContentController.add(self, name: "muse")
        web = WKWebView(frame: fx.bounds, configuration: cfg)
        web.setValue(false, forKey: "drawsBackground")
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self
        fx.addSubview(web)
        panel.contentView = fx
    }

    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        if (m.body as? String) == "hide" { hide() }
    }

    func webView(_ w: WKWebView, didFinish nav: WKNavigation!) {
        if w.url?.host == "localhost" { focusField() }
    }

    func windowDidResignKey(_ n: Notification) { if !holding { hide() } }

    func place() {
        let mouse = NSEvent.mouseLocation
        let screen = NSScreen.screens.first { $0.frame.contains(mouse) } ?? NSScreen.main!
        let f = screen.visibleFrame
        panel.setFrameOrigin(NSPoint(x: f.midX - panelSize.width / 2,
                                     y: f.maxY - f.height * 0.18 - panelSize.height))
    }

    func show() {
        if !panel.isVisible { place() }
        NSApp.activate(ignoringOtherApps: true)
        panel.makeKeyAndOrderFront(nil)
        panel.makeFirstResponder(web)
        focusField()
    }

    func hide() { panel.orderOut(nil) }
    func toggle() { panel.isVisible && panel.isKeyWindow ? hide() : show() }

    func js(_ s: String) { if ready { web.evaluateJavaScript(s, completionHandler: nil) } }

    // Page hooks if the page has them, else its #q field and #talk button.
    func focusField() {
        js("window.museFocus ? museFocus() : (document.getElementById('q') || {focus(){}}).focus()")
    }
    func talkStart() {
        js("window.museTalk ? museTalk.start() : (b => b && b.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})))(document.getElementById('talk'))")
    }
    func talkStop() {
        js("window.museTalk ? museTalk.stop() : (b => b && b.dispatchEvent(new PointerEvent('pointerup', {bubbles: true})))(document.getElementById('talk'))")
    }

    // ---- Hotkey: a keyboard event tap, since the system hotkey call ignores Fn.
    // Needs Accessibility for Muse (asked once at launch). It swallows Fn-Space so
    // no space is typed into the app in front.
    var tap: CFMachPort?

    func registerHotKey() {
        if tap != nil { return }
        let mask = (1 << CGEventType.keyDown.rawValue) | (1 << CGEventType.keyUp.rawValue)
        tap = CGEvent.tapCreate(tap: .cgSessionEventTap, place: .headInsertEventTap, options: .defaultTap,
                                eventsOfInterest: CGEventMask(mask), callback: { _, type, ev, ctx in
            let app = Unmanaged<App>.fromOpaque(ctx!).takeUnretainedValue()
            return app.onKey(type, ev)
        }, userInfo: Unmanaged.passUnretained(self).toOpaque())
        guard let tap else {
            // Not allowed yet: try again until Accessibility is on.
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { self.registerHotKey() }
            return
        }
        CFRunLoopAddSource(CFRunLoopGetMain(), CFMachPortCreateRunLoopSource(nil, tap, 0), .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)
    }

    func onKey(_ type: CGEventType, _ ev: CGEvent) -> Unmanaged<CGEvent>? {
        if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
            if let tap { CGEvent.tapEnable(tap: tap, enable: true) }
            return Unmanaged.passUnretained(ev)
        }
        guard ev.getIntegerValueField(.keyboardEventKeycode) == hotKeyCode else { return Unmanaged.passUnretained(ev) }
        let others: CGEventFlags = [.maskCommand, .maskControl, .maskAlternate, .maskShift]
        if type == .keyDown {
            guard ev.flags.contains(hotKeyFlags), ev.flags.intersection(others).isEmpty else {
                return Unmanaged.passUnretained(ev)
            }
            if ev.getIntegerValueField(.keyboardEventAutorepeat) == 0 { hotPressed() }
            return nil
        }
        if type == .keyUp && hotDown {   // Fn may already be up: end it anyway
            hotReleased()
            return nil
        }
        return Unmanaged.passUnretained(ev)
    }

    func hotPressed() {
        if hotDown { return }   // key repeat
        hotDown = true
        holdTimer = Timer.scheduledTimer(withTimeInterval: holdSeconds, repeats: false) { [weak self] _ in
            guard let self, self.hotDown, self.ready else { return }
            self.holding = true
            self.show()
            self.talkStart()
        }
    }

    func hotReleased() {
        hotDown = false
        holdTimer?.invalidate()
        if holding { holding = false; talkStop() } else { toggle() }
    }

    // ---- Argmax key ----
    /// Ask for the key. Returns true when a new one was saved.
    @discardableResult func askForKey() -> Bool {
        NSApp.activate(ignoringOtherApps: true)
        let a = NSAlert()
        a.messageText = "Argmax key"
        a.informativeText = "Paste your Argmax key (starts with ax_). It is kept in your login Keychain as \"\(keychainService)\" and given to the voice program when Muse starts."
        let field = NSSecureTextField(frame: NSRect(x: 0, y: 0, width: 300, height: 24))
        field.placeholderString = "ax_…"
        a.accessoryView = field
        a.addButton(withTitle: "Save"); a.addButton(withTitle: "Skip (typing only)")
        a.window.initialFirstResponder = field
        while a.runModal() == .alertFirstButtonReturn {
            let k = field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
            if k.hasPrefix("ax_") && Keychain.save(k) { argmaxKey = k; return true }
            a.informativeText = k.hasPrefix("ax_") ? "Could not save it in the Keychain. Try again."
                                                     : "That doesn't start with ax_. Paste the Argmax key."
        }
        return false
    }

    // ---- Start-up: allows first (so nothing asks mid-demo), then servers, then checks ----
    func showMessage(_ text: String, continueLink: Bool = false) {
        let link = continueLink ? "<p><a href=\"\(windowURL.absoluteString)\" style=\"color:-apple-system-blue\">Continue to Muse</a></p>" : ""
        web.loadHTMLString("""
        <html><body style="margin:0;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;
        font:14px/1.5 -apple-system;color:-apple-system-label;color-scheme:light dark;background:transparent;padding:24px;box-sizing:border-box">
        <div style="white-space:pre-wrap;max-width:560px">\(html(text))</div>\(link)</body></html>
        """, baseURL: nil)
    }

    func say(_ s: String) { DispatchQueue.main.async { self.showMessage(s) } }

    func askMicrophone() {
        guard AVCaptureDevice.authorizationStatus(for: .audio) == .notDetermined else { return }
        let sem = DispatchSemaphore(value: 0)
        AVCaptureDevice.requestAccess(for: .audio) { _ in sem.signal() }
        sem.wait()
    }

    /// The same kind of osascript read applecal does, so the Calendar allow is asked now.
    /// Returns nil when fine, else the problem.
    func calendarProblem() -> String? {
        let (code, out) = run("/usr/bin/osascript", ["-e", "tell application \"Calendar\" to get name of calendars"], timeout: 120)
        if code == 0 {
            let names = out.components(separatedBy: ", ")
            return names.contains(calendarName) ? nil
                : "Calendar: no calendar named \"\(calendarName)\" (docs/calendar.md)."
        }
        if out.contains("-1743") {
            return "Calendar: not allowed. System Settings → Privacy & Security → Automation → Muse → Calendar."
        }
        return "Calendar: could not read it (\(out.prefix(120)))."
    }

    func bringUp() {
        say("Starting…\nAsking for microphone and Calendar access if needed.")
        askMicrophone()   // no-op once setup has asked
        let calProblem = calendarProblem()

        if !FileManager.default.fileExists(atPath: repo + "/scripts/serve_bonsai.sh") {
            return say("Muse code not found at \(repo).\nRun setup.sh from the Muse disk image, or point Muse at your copy:\n  defaults write local.ai-hackathon-26.muse MuseRepo /path/to/ai-hackathon-26\nthen reopen Muse.")
        }
        let started = Date()
        var extra: [String: String] = [:]
        if let k = argmaxKey { extra["ARGMAX_API_KEY"] = k }
        bonsai.startIfNeeded()
        window.startIfNeeded(extraEnv: extra)
        while true {
            let b = bonsai.answers(), w = window.answers()
            if b && w { break }
            for s in [bonsai, window] where !s.answers() {
                if let f = s.failure { return say("\(s.name) did not start: \(f)") }
                if s.exited { return say("\(s.name) did not start:\n\(s.lastLog())\n\nLog: \(s.log)") }
            }
            if Date().timeIntervalSince(started) > 180 {
                return say("Still waiting after 3 minutes for: " +
                           [b ? nil : "Bonsai (:8080)", w ? nil : "window (:8765)"].compactMap { $0 }.joined(separator: ", ") +
                           "\nLogs: \(logDir)")
            }
            say("Starting…\n" + (b ? "Bonsai ready" : "Bonsai starting") + " · " + (w ? "window ready" : "window starting"))
            Thread.sleep(forTimeInterval: 0.5)
        }
        let problems = checks(calProblem: calProblem)
        DispatchQueue.main.async {
            self.ready = true
            if problems.isEmpty {
                self.web.load(URLRequest(url: windowURL))
            } else {
                self.showMessage("Setup problems:\n• " + problems.joined(separator: "\n• "), continueLink: true)
            }
        }
    }

    /// One line per problem; empty when everything is ready.
    func checks(calProblem: String?) -> [String] {
        var p: [String] = []
        let key = Keychain.read()
        if key == nil { p.append("Argmax key: none saved. Menu → Set Argmax key…") }
        else if !(key!.hasPrefix("ax_")) { p.append("Argmax key: doesn't start with ax_. Menu → Set Argmax key…") }
        if !FileManager.default.fileExists(atPath: modelFolder) { p.append("Whisper model folder missing: \(modelFolder)") }
        if !FileManager.default.isExecutableFile(atPath: voiceBin) {
            p.append("Voice program not built: run  swift build -c release  in \(repo)/voice/swift")
        }
        if let d = get(bonsaiURL), let s = String(data: d, encoding: .utf8) {
            if !s.lowercased().contains("4b") { p.append("Bonsai on :8080 isn't the 4B model.") }
        } else { p.append("Bonsai on :8080 doesn't answer. Log: \(bonsai.log)") }
        if let d = get(statusURL), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
            if (j["voice"] as? Bool) != true {
                let why = (j["voice_why"] as? String) ?? "unknown"
                p.append("Voice isn't ready in the window server: \(why)" +
                         (window.proc == nil ? " (that server was started outside Muse; restart it, or quit it and reopen Muse)" : ""))
            }
        } else { p.append("Window server on :8765 doesn't answer. Log: \(window.log)") }
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized: break
        default: p.append("Microphone: not allowed. System Settings → Privacy & Security → Microphone → Muse.")
        }
        if !AXIsProcessTrusted() {
            p.append("\(hotKeyName): needs Accessibility. System Settings → Privacy & Security → Accessibility → turn on Muse.")
        }
        if let c = calProblem { p.append(c) }
        // Is the checkout the servers run from behind main? Compares to the last fetch only.
        let (rc, n) = run("/usr/bin/git", ["-C", repo, "rev-list", "--count", "HEAD..origin/main"], timeout: 5)
        if rc == 0, let behind = Int(n), behind > 0 {
            p.append("Code: \(repo) is \(behind) commit(s) behind origin/main (as of its last fetch). Run  git pull  there, then reopen Muse.")
        }
        return p
    }

    // ---- Menu actions ----
    @objc func openPanel() { show() }
    @objc func openSetup() { setup.show { self.start() } }

    /// The page's own Discover button: it asks "discover" and shows the Yes/No/Skip/Stop choices.
    @objc func discover() {
        show()
        js("(b => b && b.click())(document.getElementById('discover'))")
    }
    @objc func quit() { NSApp.terminate(nil) }

    @objc func checkSetup() {
        show()
        guard ready else { return }
        showMessage("Checking…")
        DispatchQueue.global().async {
            let problems = self.checks(calProblem: self.calendarProblem())
            DispatchQueue.main.async {
                self.showMessage(problems.isEmpty ? "Everything is ready." : "Setup problems:\n• " + problems.joined(separator: "\n• "),
                                 continueLink: true)
            }
        }
    }

    @objc func setKey() {
        guard askForKey(), ready else { return }
        // Give the new key to the window server: restart it if Muse started it.
        guard window.proc != nil else {
            showMessage("Key saved. The window server was started outside Muse: restart it (or quit it and reopen Muse) to use the new key.", continueLink: true)
            return show()
        }
        ready = false
        show()
        DispatchQueue.global().async {
            self.window.stop()
            self.bringUp()
        }
    }

    @objc func syncMail() {
        syncItem.isEnabled = false; syncItem.title = "Syncing mail…"
        syncInfo.isHidden = true
        DispatchQueue.global().async {
            let (_, out) = run("/bin/zsh", ["-l", "-c", "cd \"$MUSE_REPO_DIR\" && MUSE_BANK_DIR=\"$MUSE_BANK\" exec uv run python scripts/sync_email.py 7"], timeout: 900, env: ["MUSE_REPO_DIR": repo, "MUSE_BANK": syncBankDir])
            let last = out.split(separator: "\n").last.map(String.init) ?? "done"
            DispatchQueue.main.async {
                self.syncItem.isEnabled = true; self.syncItem.title = "Sync mail"
                self.syncInfo.title = "Last sync: " + String(last.prefix(70))
                self.syncInfo.isHidden = false
                self.js("typeof refresh === 'function' && refresh()")
            }
        }
    }
}

/// Run a command, return (exit code, stdout+stderr). Gives up after `timeout` seconds.
func run(_ path: String, _ args: [String], timeout: TimeInterval, env extra: [String: String] = [:]) -> (Int32, String) {
    let p = Process(); p.executableURL = URL(fileURLWithPath: path); p.arguments = args
    var e = env; for (k, v) in extra { e[k] = v }; p.environment = e
    let pipe = Pipe(); p.standardOutput = pipe; p.standardError = pipe
    do { try p.run() } catch { return (-1, error.localizedDescription) }
    // Read as it comes so long output can't fill the pipe and stall.
    var data = Data()
    let reader = DispatchQueue(label: "sync-read")
    reader.async { data = pipe.fileHandleForReading.readDataToEndOfFile() }
    let deadline = Date().addingTimeInterval(timeout)
    while p.isRunning && Date() < deadline { usleep(200_000) }
    if p.isRunning { p.terminate(); return (-2, "timed out") }
    reader.sync {}
    return (p.terminationStatus, String(data: data, encoding: .utf8) ?? "")
}

// ---- First-run setup: one permission per screen (after Jot's Accessibility window) ----
let privacyURL = URL(string: "https://cobydev.com/muse/privacy")!   // placeholder until the page is up
let settingsBase = "x-apple.systempreferences:com.apple.preference.security?"

/// Automation status for one app, without asking. nil = can't tell (app not running).
func automationGranted(_ bundleID: String, ask: Bool = false) -> Bool? {
    let target = NSAppleEventDescriptor(bundleIdentifier: bundleID)
    let st = AEDeterminePermissionToAutomateTarget(target.aeDesc, typeWildCard, typeWildCard, ask)
    if st == noErr { return true }
    if st == OSStatus(procNotFound) { return nil }
    return false   // -1743 denied, -1744 would ask
}

/// Launch an app hidden in the background, so its Automation status can be read.
func launchHidden(_ bundleID: String) {
    guard NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).isEmpty,
          let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleID) else { return }
    let cfg = NSWorkspace.OpenConfiguration(); cfg.activates = false; cfg.hides = true
    NSWorkspace.shared.openApplication(at: url, configuration: cfg, completionHandler: nil)
}

/// The app's own icon, draggable into the Accessibility list (Jot's DraggableAppIconView).
final class DragIcon: NSView, NSDraggingSource {
    override init(frame: NSRect) { super.init(frame: frame) }
    required init?(coder: NSCoder) { fatalError() }
    override func draw(_ r: NSRect) { NSApp.applicationIconImage.draw(in: bounds) }
    override func resetCursorRects() { addCursorRect(bounds, cursor: .openHand) }
    func draggingSession(_ s: NSDraggingSession, sourceOperationMaskFor c: NSDraggingContext) -> NSDragOperation { .copy }
    override func mouseDown(with e: NSEvent) {
        let item = NSDraggingItem(pasteboardWriter: Bundle.main.bundleURL as NSURL)
        item.setDraggingFrame(bounds, contents: NSApp.applicationIconImage)
        beginDraggingSession(with: [item], event: e, source: self)
    }
}

struct Step {
    let title: String, body: String, button: String?
    var pane: String? = nil
    var granted: () -> Bool? = { nil }       // nil: nothing to check (Continue is always on)
    var act: (Setup) -> Void = { _ in }
    var onShow: () -> Void = {}
}

final class Setup: NSObject, NSWindowDelegate {
    var win: NSWindow!
    let icon = NSImageView(), titleL = NSTextField(labelWithString: ""), bodyL = NSTextField(wrappingLabelWithString: "")
    let slot = NSView(), actionB = NSButton(), statusL = NSTextField(labelWithString: ""), countL = NSTextField(labelWithString: "")
    let backB = NSButton(), skipB = NSButton(), nextB = NSButton()
    let keyField = NSSecureTextField()
    var steps: [Step] = []
    var i = 0
    var timer: Timer?
    var onDone: () -> Void = {}

    static func needed() -> Bool {
        !UserDefaults.standard.bool(forKey: "SetupDone") || Keychain.read() == nil || !AXIsProcessTrusted()
            || AVCaptureDevice.authorizationStatus(for: .audio) != .authorized
    }

    func automationStep(_ name: String, _ bundleID: String, _ why: String) -> Step {
        Step(title: name, body: why + " Muse asks \(name) through AppleScript; macOS asks you once.",
             button: "Allow \(name)…", pane: settingsBase + "Privacy_Automation",
             granted: { automationGranted(bundleID) },
             act: { s in
                 launchHidden(bundleID)
                 DispatchQueue.global().async {
                     Thread.sleep(forTimeInterval: 1.0)   // let it finish launching
                     let ok = automationGranted(bundleID, ask: true)
                     if ok == false { DispatchQueue.main.async { s.openPane() } }
                 }
             },
             onShow: { launchHidden(bundleID) })
    }

    func build() {
        steps = [
            Step(title: "Welcome to Muse",
                 body: "Muse answers from your mail, calendar and notes, on this Mac. The language model (Bonsai) and speech to text (Argmax) run here, and your mail bank stays in your home folder.\n\nWhat leaves this Mac: a web search when the bank has no answer and you're online, a mail sync when you choose Sync mail or Discover, and Argmax's licence check when voice starts. Nothing else.\n\nThe next screens ask for one permission each.",
                 button: "How Muse handles your data", act: { _ in NSWorkspace.shared.open(privacyURL) }),
            Step(title: "Argmax key",
                 body: "Voice needs your own Argmax key (ax_…, from app.argmaxinc.com). Muse keeps it in your login Keychain as \"\(keychainService)\" and gives it only to its voice program. Each Mac needs its own key.",
                 button: "Save key", granted: { Keychain.read()?.hasPrefix("ax_") ?? false },
                 act: { s in
                     let k = s.keyField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
                     if k.hasPrefix("ax_"), Keychain.save(k) { s.keyField.stringValue = "" }
                     else { s.statusL.stringValue = "That doesn't start with ax_." }
                 }),
            Step(title: "Accessibility",
                 body: "For the \(hotKeyName) hotkey: tap it to open Muse from any app, hold it to talk. Muse only watches for that one key. Click the button, then turn Muse on in the list, or drag this icon into it.",
                 button: "Open Accessibility Settings", pane: settingsBase + "Privacy_Accessibility",
                 granted: { AXIsProcessTrusted() },
                 act: { s in
                     _ = AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary)
                     s.openPane()
                 }),
            Step(title: "Microphone",
                 body: "So you can talk to Muse. It listens only while you hold \(hotKeyName) or the talk button.",
                 button: "Allow Microphone", pane: settingsBase + "Privacy_Microphone",
                 granted: { AVCaptureDevice.authorizationStatus(for: .audio) == .authorized },
                 act: { s in
                     if AVCaptureDevice.authorizationStatus(for: .audio) == .notDetermined {
                         AVCaptureDevice.requestAccess(for: .audio) { _ in }
                     } else { s.openPane() }
                 }),
            automationStep("Calendar", "com.apple.iCal", "To read your \"\(calendarName)\" calendar and add events you ask for."),
            automationStep("Reminders", "com.apple.reminders", "To add reminders you ask for."),
            automationStep("Mail", "com.apple.mail", "To open an email in Mail when you ask Muse to show it. Muse doesn't send mail."),
            Step(title: "You're set",
                 body: "Tap \(hotKeyName) to ask from any app; hold it to talk and let go to get the answer. The waveform in the menu bar has the rest, including Set Up Muse… to come back here.",
                 button: nil),
        ]
    }

    func show(onDone: @escaping () -> Void) {
        self.onDone = onDone
        if win == nil { build(); makeWindow() }
        NSApp.activate(ignoringOtherApps: true)
        win.center(); win.makeKeyAndOrderFront(nil)
        go(0)
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.refresh() }
    }

    func makeWindow() {
        win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 460, height: 520), styleMask: [.titled, .closable],
                       backing: .buffered, defer: false)
        win.title = "Set Up Muse"; win.isReleasedWhenClosed = false; win.delegate = self
        let v = win.contentView!
        icon.image = NSApp.applicationIconImage
        titleL.font = .systemFont(ofSize: 20, weight: .semibold); titleL.alignment = .center
        bodyL.font = .systemFont(ofSize: 13); bodyL.textColor = .secondaryLabelColor; bodyL.alignment = .center
        keyField.placeholderString = "ax_…"
        actionB.bezelStyle = .rounded; actionB.target = self; actionB.action = #selector(doAction)
        statusL.font = .systemFont(ofSize: 12); statusL.alignment = .center
        countL.font = .systemFont(ofSize: 11); countL.textColor = .tertiaryLabelColor
        for (b, t, a) in [(backB, "Back", #selector(back)), (skipB, "Skip", #selector(skip)), (nextB, "Continue", #selector(next))] {
            b.title = t; b.bezelStyle = .rounded; b.target = self; b.action = a
        }
        nextB.keyEquivalent = "\r"
        for x in [icon, titleL, bodyL, slot, actionB, statusL, countL, backB, skipB, nextB] as [NSView] {
            x.translatesAutoresizingMaskIntoConstraints = false; v.addSubview(x)
        }
        NSLayoutConstraint.activate([
            icon.topAnchor.constraint(equalTo: v.topAnchor, constant: 28), icon.centerXAnchor.constraint(equalTo: v.centerXAnchor),
            icon.widthAnchor.constraint(equalToConstant: 72), icon.heightAnchor.constraint(equalToConstant: 72),
            titleL.topAnchor.constraint(equalTo: icon.bottomAnchor, constant: 14), titleL.centerXAnchor.constraint(equalTo: v.centerXAnchor),
            bodyL.topAnchor.constraint(equalTo: titleL.bottomAnchor, constant: 10),
            bodyL.leadingAnchor.constraint(equalTo: v.leadingAnchor, constant: 36), bodyL.trailingAnchor.constraint(equalTo: v.trailingAnchor, constant: -36),
            slot.topAnchor.constraint(equalTo: bodyL.bottomAnchor, constant: 16), slot.centerXAnchor.constraint(equalTo: v.centerXAnchor),
            slot.widthAnchor.constraint(equalToConstant: 280), slot.heightAnchor.constraint(equalToConstant: 64),
            actionB.topAnchor.constraint(equalTo: slot.bottomAnchor, constant: 12), actionB.centerXAnchor.constraint(equalTo: v.centerXAnchor),
            statusL.topAnchor.constraint(equalTo: actionB.bottomAnchor, constant: 10), statusL.centerXAnchor.constraint(equalTo: v.centerXAnchor),
            nextB.bottomAnchor.constraint(equalTo: v.bottomAnchor, constant: -20), nextB.trailingAnchor.constraint(equalTo: v.trailingAnchor, constant: -20),
            skipB.centerYAnchor.constraint(equalTo: nextB.centerYAnchor), skipB.trailingAnchor.constraint(equalTo: nextB.leadingAnchor, constant: -8),
            backB.centerYAnchor.constraint(equalTo: nextB.centerYAnchor), backB.leadingAnchor.constraint(equalTo: v.leadingAnchor, constant: 20),
            countL.centerYAnchor.constraint(equalTo: nextB.centerYAnchor), countL.leadingAnchor.constraint(equalTo: backB.trailingAnchor, constant: 12),
        ])
    }

    func go(_ n: Int) {
        i = max(0, min(n, steps.count - 1))
        let s = steps[i]
        NSApp.activate(ignoringOtherApps: true)
        titleL.stringValue = s.title; bodyL.stringValue = s.body
        actionB.isHidden = s.button == nil; actionB.title = s.button ?? ""
        slot.subviews.forEach { $0.removeFromSuperview() }
        if s.title == "Argmax key" {
            keyField.frame = NSRect(x: 20, y: 20, width: 240, height: 24); slot.addSubview(keyField)
            win.makeFirstResponder(keyField)
        } else if s.title == "Accessibility" {
            slot.addSubview(DragIcon(frame: NSRect(x: 108, y: 0, width: 64, height: 64)))
        }
        backB.isEnabled = i > 0
        skipB.isHidden = s.granted() == nil && s.title != "Accessibility" || i == steps.count - 1
        nextB.title = i == steps.count - 1 ? "Done" : "Continue"
        countL.stringValue = "\(i + 1) of \(steps.count)"
        statusL.stringValue = ""
        s.onShow()
        refresh()
    }

    func openPane() { if let p = steps[i].pane, let u = URL(string: p) { NSWorkspace.shared.open(u) } }

    func refresh() {
        let s = steps[i]
        guard let ok = s.granted() else { nextB.isEnabled = true; statusL.stringValue = ""; return }
        if ok {
            statusL.attributedStringValue = NSAttributedString(string: "●  Allowed", attributes: [.foregroundColor: NSColor.systemGreen])
            nextB.isEnabled = true
            skipB.isHidden = true
        } else {
            if !statusL.stringValue.hasPrefix("That") {
                statusL.attributedStringValue = NSAttributedString(string: "○  Not yet", attributes: [.foregroundColor: NSColor.secondaryLabelColor])
            }
            nextB.isEnabled = false
            skipB.isHidden = i == steps.count - 1
        }
    }

    @objc func doAction() { steps[i].act(self); refresh() }
    @objc func back() { go(i - 1) }
    @objc func skip() { go(i + 1) }
    @objc func next() {
        if i == steps.count - 1 { finish() } else { go(i + 1) }
    }

    func finish() {
        UserDefaults.standard.set(true, forKey: "SetupDone")
        timer?.invalidate(); timer = nil
        win.orderOut(nil)
        let done = onDone; onDone = {}
        done()
    }

    func windowWillClose(_ n: Notification) {   // closing it counts as done for now
        timer?.invalidate(); timer = nil
        let done = onDone; onDone = {}
        done()
    }
}

let app = NSApplication.shared
let delegate = App()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
