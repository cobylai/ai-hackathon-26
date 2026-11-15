// Flux menu-bar app: a Spotlight-style panel that shows the local window page
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
let statusURL = URL(string: "http://localhost:8765/status")!
let panelSize = NSSize(width: 640, height: 440)
let keychainService = "Flux Argmax key"
let keychainAccount = "ARGMAX_API_KEY"

let env = ProcessInfo.processInfo.environment
/// FLUX_<name>, or the old MUSE_<name> (read for one release).
func setting(_ name: String) -> String? { env["FLUX_" + name] ?? env["MUSE_" + name] }
let bonsaiURL = URL(string: setting("BONSAI_URL") ?? "http://localhost:8080/v1/models")!   // FLUX_BONSAI_URL: tests
// Where the repo is: `defaults write local.ai-hackathon-26.flux FluxRepo <path>`, then FLUX_REPO,
// then the path baked in at build time (empty in the DMG build), then ~/ai-hackathon-26.
var repo: String = [UserDefaults.standard.string(forKey: "FluxRepo"), UserDefaults.standard.string(forKey: "MuseRepo"), setting("REPO"),
                    Bundle.main.object(forInfoDictionaryKey: "FluxRepo") as? String]
    .compactMap { $0 }.first { !$0.isEmpty } ?? (NSHomeDirectory() + "/ai-hackathon-26")
let bankDir: String = setting("BANK_DIR") ?? (NSHomeDirectory() + "/flux-demo-bank")
// Sync mail writes real Gmail here, never into the demo bank.
let syncBankDir: String = setting("SYNC_BANK_DIR") ?? (NSHomeDirectory() + "/flux-bank")
let calendarName: String = setting("CALENDAR") ?? "Flux demo"
let modelFolder: String = env["ARGMAX_MODEL_FOLDER"].flatMap { $0.isEmpty ? nil : $0 } ?? (NSHomeDirectory() +
    "/Documents/huggingface/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB")
var voiceBin: String { setting("VOICE_BIN") ?? (repo + "/voice/swift/.build/release/argmax-voice") }
/// Where the code is cloned from: set at build time (FLUX_REPO_URL); empty means Set Up asks.
var repoURL: String = (Bundle.main.object(forInfoDictionaryKey: "FluxRepoURL") as? String) ?? ""
let logDir = NSHomeDirectory() + "/Library/Logs/Flux"

// ---- Keychain (login keychain, generic password) ----
enum Keychain {
    static var base: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: keychainService,
         kSecAttrAccount as String: keychainAccount]
    }
    /// The key, moving it once from the old "Muse Argmax key" item if that's where it is.
    static func read() -> String? {
        if let k = read(service: keychainService) { return k }
        guard let old = read(service: "Muse Argmax key") else { return nil }
        _ = save(old)
        return old
    }
    static func read(service: String) -> String? {
        var q = base; q[kSecAttrService as String] = service; q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
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
        e["FLUX_BANK_DIR"] = bankDir
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
        let img = NSImage(systemSymbolName: "waveform", accessibilityDescription: "Flux")
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
        m.addItem(withTitle: "Set Up Flux…", action: #selector(openSetup), keyEquivalent: "")
        m.addItem(withTitle: "Check setup", action: #selector(checkSetup), keyEquivalent: "")
        m.addItem(withTitle: "Set Argmax key…", action: #selector(setKey), keyEquivalent: "")
        m.addItem(.separator())
        m.addItem(withTitle: "Quit Flux", action: #selector(quit), keyEquivalent: "q")
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
          if (e.key === 'Escape' && !e.defaultPrevented) window.webkit.messageHandlers.flux.postMessage('hide');
        });
        """
        cfg.userContentController.addUserScript(WKUserScript(source: js, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        cfg.userContentController.add(self, name: "flux")
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
        js("window.fluxFocus ? fluxFocus() : (document.getElementById('q') || {focus(){}}).focus()")
    }
    func talkStart() {
        js("window.fluxTalk ? fluxTalk.start() : (b => b && b.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})))(document.getElementById('talk'))")
    }
    func talkStop() {
        js("window.fluxTalk ? fluxTalk.stop() : (b => b && b.dispatchEvent(new PointerEvent('pointerup', {bubbles: true})))(document.getElementById('talk'))")
    }

    // ---- Hotkey: a keyboard event tap, since the system hotkey call ignores Fn.
    // Needs Accessibility for Flux (asked once at launch). It swallows Fn-Space so
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
        a.informativeText = "Paste your Argmax key (starts with ax_). It is kept in your login Keychain as \"\(keychainService)\" and given to the voice program when Flux starts."
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
        let link = continueLink ? "<p><a href=\"\(windowURL.absoluteString)\" style=\"color:-apple-system-blue\">Continue to Flux</a></p>" : ""
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
            return "Calendar: not allowed. System Settings → Privacy & Security → Automation → Flux → Calendar."
        }
        return "Calendar: could not read it (\(out.prefix(120)))."
    }

    func bringUp() {
        say("Starting…\nAsking for microphone and Calendar access if needed.")
        askMicrophone()   // no-op once setup has asked
        let calProblem = calendarProblem()

        if !FileManager.default.fileExists(atPath: repo + "/scripts/serve_bonsai.sh") {
            return say("Flux code not found at \(repo).\nChoose Set Up Flux… in the menu bar to install it, or point Flux at your copy:\n  defaults write local.ai-hackathon-26.flux FluxRepo /path/to/ai-hackathon-26\nthen reopen Flux.")
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
                         (window.proc == nil ? " (that server was started outside Flux; restart it, or quit it and reopen Flux)" : ""))
            }
        } else { p.append("Window server on :8765 doesn't answer. Log: \(window.log)") }
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized: break
        default: p.append("Microphone: not allowed. System Settings → Privacy & Security → Microphone → Flux.")
        }
        if !AXIsProcessTrusted() {
            p.append("\(hotKeyName): needs Accessibility. System Settings → Privacy & Security → Accessibility → turn on Flux.")
        }
        if let c = calProblem { p.append(c) }
        // Is the checkout the servers run from behind main? Compares to the last fetch only.
        let (rc, n) = run("/usr/bin/git", ["-C", repo, "rev-list", "--count", "HEAD..origin/main"], timeout: 5)
        if rc == 0, let behind = Int(n), behind > 0 {
            p.append("Code: \(repo) is \(behind) commit(s) behind origin/main (as of its last fetch). Run  git pull  there, then reopen Flux.")
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
        // Give the new key to the window server: restart it if Flux started it.
        guard window.proc != nil else {
            showMessage("Key saved. The window server was started outside Flux: restart it (or quit it and reopen Flux) to use the new key.", continueLink: true)
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
            let (_, out) = run("/bin/zsh", ["-l", "-c", "cd \"$FLUX_REPO_DIR\" && FLUX_BANK_DIR=\"$FLUX_BANK\" exec uv run python scripts/sync_email.py 7"], timeout: 900, env: ["FLUX_REPO_DIR": repo, "FLUX_BANK": syncBankDir])
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

// ---- First-run setup: four calm screens (Welcome, Install, Argmax key, Permissions) ----
let privacyURL = URL(string: "https://cobydev.com/flux/privacy")!
let settingsBase = "x-apple.systempreferences:com.apple.preference.security?"
let home = NSHomeDirectory()
let shellPath = "export PATH=\"$HOME/.local/bin:/opt/homebrew/bin:$PATH\"; "

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

func exists(_ p: String) -> Bool { FileManager.default.fileExists(atPath: p) }
func which(_ tool: String) -> Bool {
    ["\(home)/.local/bin/\(tool)", "/opt/homebrew/bin/\(tool)", "/usr/local/bin/\(tool)"].contains { exists($0) }
}

/// One part Flux needs, installed on its own.
struct Part {
    let name: String, size: String?, link: String
    let done: () -> Bool
    let commands: () -> [String]      // shell lines, run in the code folder; shown under Details
}

/// Where Bonsai lives, the same way scripts/serve_bonsai.sh finds it: BONSAI_MODELS_DIR / BONSAI_VENV,
/// else the main checkout (a worktree at <main>/.claude/worktrees/<name> has no models of its own).
func mainCheckout(_ r: String) -> String { r.components(separatedBy: "/.claude/worktrees/").first ?? r }
var bonsaiMLX: String { mainCheckout(repo) + "/samples/bonsai-models/mlx" }
var bonsaiModels: String { env["BONSAI_MODELS_DIR"].flatMap { $0.isEmpty ? nil : $0 } ?? (bonsaiMLX + "/models") }
var bonsaiVenv: String { env["BONSAI_VENV"].flatMap { $0.isEmpty ? nil : $0 } ?? (bonsaiMLX + "/.venv") }
/// Installed = the 4B model file is there, or a Bonsai server already answers.
func bonsaiInstalled() -> Bool { exists(bonsaiModels + "/bonsai2-4b-mlx/model.safetensors") || get(bonsaiURL) != nil }

func parts() -> [Part] {
    let mlx = bonsaiMLX
    let bonsai = bonsaiModels + "/bonsai2-4b-mlx"
    let whisperRoot = home + "/Documents/huggingface/models/argmaxinc/whisperkit-coreml"
    return [
        Part(name: "Flux code", size: nil, link: repoURL.isEmpty ? "" : repoURL,
             done: { exists(repo + "/scripts/serve_bonsai.sh") },
             commands: { ["git clone \(repoURL) \"\(repo)\""] }),
        Part(name: "Python tools", size: "about 300 MB", link: "https://docs.astral.sh/uv/",
             done: { which("uv") && exists(repo + "/.venv/bin/python")
                     && ((try? FileManager.default.contentsOfDirectory(atPath: home + "/Library/Caches/ms-playwright")) ?? []).contains { $0.hasPrefix("chromium-") } },
             commands: { (which("uv") ? [] : ["curl -LsSf https://astral.sh/uv/install.sh | sh"])
                         + ["uv sync", "uv run playwright install chromium"] }),
        Part(name: "Bonsai 2 4B", size: "about 1 GB", link: "https://huggingface.co/prism-ml/Ternary-Bonsai-2-4B-mlx-2bit",
             done: { bonsaiInstalled() },
             commands: { (exists(bonsaiVenv + "/bin/python") ? [] : [
                            "uv venv --python 3.12 \"\(bonsaiVenv)\"",
                            "uv pip install --python \"\(bonsaiVenv)/bin/python\" -r \"\(mlx)/requirements.txt\""])
                         + ["\"\(bonsaiVenv)/bin/hf\" download prism-ml/Ternary-Bonsai-2-4B-mlx-2bit --local-dir \"\(bonsai)\""] }),
        Part(name: "Speech model", size: "about 630 MB", link: "https://huggingface.co/argmaxinc/whisperkit-coreml",
             done: { exists(modelFolder) },
             commands: { ["uvx --from huggingface_hub hf download argmaxinc/whisperkit-coreml --include \"openai_whisper-large-v3-v20240930_626MB/*\" --local-dir \"\(whisperRoot)\""] }),
        Part(name: "Voice program", size: nil, link: "https://app.argmaxinc.com",
             done: { FileManager.default.isExecutableFile(atPath: voiceBin) },
             commands: { (registryReady() ? [] : [
                            "swift package-registry set --global --scope argmaxinc https://api.argmaxinc.com/v1/sdk",
                            "swift package-registry login https://api.argmaxinc.com/v1/sdk/login --token \"$ARGMAX_TOKEN\""])
                         + ["cd voice/swift && swift build -c release"] }),
    ]
}

func registryReady() -> Bool {
    ((try? String(contentsOfFile: home + "/.swiftpm/configuration/registries.json", encoding: .utf8)) ?? "").contains("argmaxinc")
}

/// One row of a checklist: status dot, name, a quiet note, an optional button.
final class Row: NSStackView {
    let dot = NSTextField(labelWithString: "○"), name = NSTextField(labelWithString: ""), note = NSTextField(labelWithString: "")
    var button: NSButton?
    init(_ title: String, note n: String = "", button b: NSButton? = nil) {
        super.init(frame: .zero)
        orientation = .horizontal; spacing = 8; alignment = .firstBaseline
        dot.font = .systemFont(ofSize: 13); name.stringValue = title; name.font = .systemFont(ofSize: 13)
        note.stringValue = n; note.font = .systemFont(ofSize: 11); note.textColor = .tertiaryLabelColor
        let spacer = NSView(); spacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        for v in [dot, name, note, spacer] { addArrangedSubview(v) }
        if let b { b.bezelStyle = .rounded; b.controlSize = .small; addArrangedSubview(b); button = b }
    }
    required init?(coder: NSCoder) { fatalError() }
    func set(_ ok: Bool?, failed: Bool = false) {
        let (s, c): (String, NSColor) = failed ? ("●", .systemRed) : ok == true ? ("●", .systemGreen) : ("○", .secondaryLabelColor)
        dot.stringValue = s; dot.textColor = c
    }
}

final class Setup: NSObject, NSWindowDelegate {
    var win: NSWindow!
    let icon = NSImageView(), titleL = NSTextField(labelWithString: ""), lineL = NSTextField(wrappingLabelWithString: "")
    let body = NSStackView(), mainB = NSButton(), statusL = NSTextField(labelWithString: "")
    let backB = NSButton(), nextB = NSButton(), countL = NSTextField(labelWithString: "")
    let keyField = NSSecureTextField()
    let details = NSTextView(), detailsScroll = NSScrollView(), detailsB = NSButton()
    var installRows: [Row] = [], permRows: [(Row, () -> Bool?)] = []
    var screen = 0, installing = false, failedPart: String?
    var timer: Timer?
    var onDone: () -> Void = {}
    let log = logDir + "/setup.log"

    static func needed() -> Bool {
        !UserDefaults.standard.bool(forKey: "SetupDone") || Keychain.read() == nil || !AXIsProcessTrusted()
            || AVCaptureDevice.authorizationStatus(for: .audio) != .authorized || !exists(repo + "/scripts/serve_bonsai.sh")
    }

    func show(onDone: @escaping () -> Void) {
        self.onDone = onDone
        if win == nil { makeWindow() }
        NSApp.activate(ignoringOtherApps: true)
        win.center(); win.makeKeyAndOrderFront(nil)
        go(Int(setting("SETUP_SCREEN") ?? "") ?? 0)   // FLUX_SETUP_SCREEN=0…3 opens one screen (for screenshots)
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.refresh() }
    }

    func makeWindow() {
        win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 460, height: 520), styleMask: [.titled, .closable],
                       backing: .buffered, defer: false)
        win.title = "Set Up Flux"; win.isReleasedWhenClosed = false; win.delegate = self
        let v = win.contentView!
        icon.image = NSApp.applicationIconImage
        titleL.font = .systemFont(ofSize: 20, weight: .semibold); titleL.alignment = .center
        lineL.font = .systemFont(ofSize: 13); lineL.textColor = .secondaryLabelColor; lineL.alignment = .center
        body.orientation = .vertical; body.alignment = .leading; body.spacing = 10
        mainB.bezelStyle = .rounded; mainB.target = self; mainB.action = #selector(doMain)
        statusL.font = .systemFont(ofSize: 12); statusL.textColor = .secondaryLabelColor; statusL.alignment = .center
        statusL.lineBreakMode = .byTruncatingMiddle
        countL.font = .systemFont(ofSize: 11); countL.textColor = .tertiaryLabelColor
        for (b, t, a) in [(backB, "Back", #selector(back)), (nextB, "Continue", #selector(next))] {
            b.title = t; b.bezelStyle = .rounded; b.target = self; b.action = a
        }
        nextB.keyEquivalent = "\r"
        detailsB.title = "Details"; detailsB.bezelStyle = .inline; detailsB.controlSize = .small
        detailsB.target = self; detailsB.action = #selector(toggleDetails)
        details.isEditable = false; details.font = .monospacedSystemFont(ofSize: 10, weight: .regular)
        details.textColor = .secondaryLabelColor; details.backgroundColor = NSColor.textBackgroundColor.withAlphaComponent(0.4)
        detailsScroll.documentView = details; detailsScroll.hasVerticalScroller = true; detailsScroll.isHidden = true
        detailsScroll.borderType = .noBorder
        details.autoresizingMask = [.width]; details.isVerticallyResizable = true
        for x in [icon, titleL, lineL, body, mainB, statusL, detailsB, detailsScroll, countL, backB, nextB] as [NSView] {
            x.translatesAutoresizingMaskIntoConstraints = false; v.addSubview(x)
        }
        NSLayoutConstraint.activate([
            icon.topAnchor.constraint(equalTo: v.topAnchor, constant: 26), icon.centerXAnchor.constraint(equalTo: v.centerXAnchor),
            icon.widthAnchor.constraint(equalToConstant: 64), icon.heightAnchor.constraint(equalToConstant: 64),
            titleL.topAnchor.constraint(equalTo: icon.bottomAnchor, constant: 12), titleL.centerXAnchor.constraint(equalTo: v.centerXAnchor),
            lineL.topAnchor.constraint(equalTo: titleL.bottomAnchor, constant: 8),
            lineL.leadingAnchor.constraint(equalTo: v.leadingAnchor, constant: 48), lineL.trailingAnchor.constraint(equalTo: v.trailingAnchor, constant: -48),
            body.topAnchor.constraint(equalTo: lineL.bottomAnchor, constant: 22),
            body.leadingAnchor.constraint(equalTo: v.leadingAnchor, constant: 64), body.trailingAnchor.constraint(equalTo: v.trailingAnchor, constant: -64),
            mainB.topAnchor.constraint(equalTo: body.bottomAnchor, constant: 20), mainB.centerXAnchor.constraint(equalTo: v.centerXAnchor),
            statusL.topAnchor.constraint(equalTo: mainB.bottomAnchor, constant: 8),
            statusL.leadingAnchor.constraint(equalTo: v.leadingAnchor, constant: 40), statusL.trailingAnchor.constraint(equalTo: v.trailingAnchor, constant: -40),
            detailsB.topAnchor.constraint(equalTo: statusL.bottomAnchor, constant: 4), detailsB.centerXAnchor.constraint(equalTo: v.centerXAnchor),
            detailsScroll.topAnchor.constraint(equalTo: detailsB.bottomAnchor, constant: 6),
            detailsScroll.leadingAnchor.constraint(equalTo: v.leadingAnchor, constant: 20), detailsScroll.trailingAnchor.constraint(equalTo: v.trailingAnchor, constant: -20),
            detailsScroll.bottomAnchor.constraint(equalTo: nextB.topAnchor, constant: -12),
            nextB.bottomAnchor.constraint(equalTo: v.bottomAnchor, constant: -18), nextB.trailingAnchor.constraint(equalTo: v.trailingAnchor, constant: -20),
            backB.centerYAnchor.constraint(equalTo: nextB.centerYAnchor), backB.leadingAnchor.constraint(equalTo: v.leadingAnchor, constant: 20),
            countL.centerYAnchor.constraint(equalTo: nextB.centerYAnchor), countL.leadingAnchor.constraint(equalTo: backB.trailingAnchor, constant: 12),
        ])
    }

    // ---- screens ----
    func go(_ n: Int) {
        screen = max(0, min(n, 3))
        NSApp.activate(ignoringOtherApps: true)
        body.arrangedSubviews.forEach { $0.removeFromSuperview() }
        installRows = []; permRows = []
        statusL.stringValue = ""; detailsB.isHidden = true; detailsScroll.isHidden = true
        mainB.isHidden = false
        switch screen {
        case 0:
            titleL.stringValue = "Welcome to Flux"
            lineL.stringValue = "Flux runs on this Mac. Let's set it up."
            mainB.title = "How Flux handles your data"
        case 1:
            titleL.stringValue = "Install"
            lineL.stringValue = "Each part runs on this Mac. Parts you already have are skipped."
            for p in parts() {
                let r = Row(p.name, note: p.size ?? ""); installRows.append(r); body.addArrangedSubview(r)
            }
            mainB.title = installing ? "Installing…" : (failedPart == nil ? "Install" : "Try Again")
            detailsB.isHidden = false
        case 2:
            titleL.stringValue = "Argmax key"
            lineL.stringValue = "Voice needs your own key (ax_…). It stays in your Keychain."
            keyField.placeholderString = "ax_…"
            keyField.translatesAutoresizingMaskIntoConstraints = false
            keyField.widthAnchor.constraint(equalToConstant: 300).isActive = true
            body.addArrangedSubview(keyField)
            mainB.title = "Save"
            win.makeFirstResponder(keyField)
        default:
            titleL.stringValue = "Permissions"
            lineL.stringValue = "Flux asks once for each."
            let perms: [(String, () -> Bool?, () -> Void)] = [
                ("Accessibility, for Fn-Space", { AXIsProcessTrusted() }, {
                    _ = AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary)
                    NSWorkspace.shared.open(URL(string: settingsBase + "Privacy_Accessibility")!) }),
                ("Microphone", { AVCaptureDevice.authorizationStatus(for: .audio) == .authorized }, {
                    if AVCaptureDevice.authorizationStatus(for: .audio) == .notDetermined { AVCaptureDevice.requestAccess(for: .audio) { _ in } }
                    else { NSWorkspace.shared.open(URL(string: settingsBase + "Privacy_Microphone")!) } }),
            ] + [("Calendar", "com.apple.iCal"), ("Reminders", "com.apple.reminders"), ("Mail", "com.apple.mail")].map { (n, id) in
                (n, { automationGranted(id) }, {
                    launchHidden(id)
                    DispatchQueue.global().async {
                        Thread.sleep(forTimeInterval: 1.0)
                        if automationGranted(id, ask: true) == false {
                            DispatchQueue.main.async { NSWorkspace.shared.open(URL(string: settingsBase + "Privacy_Automation")!) }
                        }
                    } })
            }
            for (n, check, act) in perms {
                let b = NSButton(title: "Allow", target: nil, action: nil)
                let r = Row(n, button: b)
                b.target = self; b.action = #selector(permButton(_:)); b.tag = permRows.count
                permActions.append(act); permRows.append((r, check)); body.addArrangedSubview(r)
            }
            for id in ["com.apple.iCal", "com.apple.reminders", "com.apple.mail"] { launchHidden(id) }
            mainB.isHidden = true
        }
        backB.isEnabled = screen > 0
        nextB.title = screen == 3 ? "Done" : "Continue"
        countL.stringValue = "\(screen + 1) of 4"
        refresh()
    }
    var permActions: [() -> Void] = []

    func refresh() {
        switch screen {
        case 1:
            for (r, p) in zip(installRows, parts()) { r.set(p.done(), failed: failedPart == p.name) }
            nextB.isEnabled = !installing
            if !installing && failedPart == nil && parts().allSatisfy({ $0.done() }) {
                mainB.title = "Installed"; mainB.isEnabled = false
            } else { mainB.isEnabled = !installing }
        case 2:
            let ok = Keychain.read()?.hasPrefix("ax_") ?? false
            if ok && statusL.stringValue.isEmpty { statusL.stringValue = "● Saved" ; statusL.textColor = .systemGreen }
        case 3:
            for (r, check) in permRows { let ok = check(); r.set(ok); r.button?.isHidden = ok == true }
        default: break
        }
    }

    @objc func permButton(_ b: NSButton) { if b.tag < permActions.count { permActions[b.tag]() } }
    @objc func back() { go(screen - 1) }
    @objc func next() { if screen == 3 { finish() } else { permActions = []; go(screen + 1) } }
    @objc func toggleDetails() { detailsScroll.isHidden.toggle() }

    @objc func doMain() {
        switch screen {
        case 0: NSWorkspace.shared.open(privacyURL)
        case 1: install()
        case 2:
            let k = keyField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
            if k.hasPrefix("ax_"), Keychain.save(k) { keyField.stringValue = ""; statusL.stringValue = "" }
            else { statusL.stringValue = "That doesn't start with ax_."; statusL.textColor = .systemRed }
        default: break
        }
        refresh()
    }

    // ---- install ----
    func say(_ s: String) {
        DispatchQueue.main.async {
            self.details.textStorage?.append(NSAttributedString(string: s + "\n",
                attributes: [.font: NSFont.monospacedSystemFont(ofSize: 10, weight: .regular), .foregroundColor: NSColor.secondaryLabelColor]))
            self.details.scrollToEndOfDocument(nil)
            if let h = FileHandle(forWritingAtPath: self.log) { h.seekToEndOfFile(); h.write(Data((s + "\n").utf8)); h.closeFile() }
        }
    }

    func ask(_ title: String, _ text: String, field: NSTextField? = nil, ok: String = "Continue") -> Bool {
        let a = NSAlert(); a.messageText = title; a.informativeText = text
        a.addButton(withTitle: ok); a.addButton(withTitle: "Cancel")
        if let field { field.frame = NSRect(x: 0, y: 0, width: 320, height: 24); a.accessoryView = field; a.window.initialFirstResponder = field }
        return a.runModal() == .alertFirstButtonReturn
    }

    func install() {
        try? FileManager.default.createDirectory(atPath: logDir, withIntermediateDirectories: true)
        if !exists(log) { FileManager.default.createFile(atPath: log, contents: nil) }
        var todo = parts().filter { !$0.done() }
        if todo.isEmpty { return }
        // Where the code comes from, if it isn't here yet.
        if todo.contains(where: { $0.name == "Flux code" }) && repoURL.isEmpty {
            let f = NSTextField(); f.placeholderString = "https://… or git@…"
            guard ask("Where's the Flux code?", "Paste the git URL you were given. It's cloned into \(repo).", field: f),
                  !f.stringValue.trimmingCharacters(in: .whitespaces).isEmpty else { return }
            repoURL = f.stringValue.trimmingCharacters(in: .whitespaces)
            todo = parts().filter { !$0.done() }
        }
        var token = ""
        if todo.contains(where: { $0.name == "Voice program" }) {
            guard xcodeReady() else {
                statusL.stringValue = "The voice program needs Xcode 16 or later (App Store). Install it, open it once, then try again."
                statusL.textColor = .systemRed; NSWorkspace.shared.open(URL(string: "macappstore://apps.apple.com/app/id497799835")!)
                return
            }
            if !registryReady() {
                let f = NSSecureTextField(); f.placeholderString = "axst_…"
                guard ask("Argmax secret token", "Your own token (axst_…) from app.argmaxinc.com, used once to download Argmax's SDK. Flux doesn't keep it.",
                          field: f), f.stringValue.hasPrefix("axst_") else { return }
                token = f.stringValue
            }
        }
        let sizes = todo.compactMap { p in p.size.map { "\(p.name): \($0)" } }
        guard ask("Install \(todo.count) part\(todo.count == 1 ? "" : "s")?",
                  todo.map { $0.name }.joined(separator: ", ") + "."
                  + (sizes.isEmpty ? "" : "\n\nDownloads:\n" + sizes.joined(separator: "\n"))
                  + "\n\nNothing needs an administrator password.", ok: "Install") else { return }
        installing = true; failedPart = nil; go(1)
        DispatchQueue.global().async {
            for p in todo {
                DispatchQueue.main.async { self.statusL.stringValue = "Installing \(p.name)…"; self.statusL.textColor = .secondaryLabelColor }
                self.say("== \(p.name)")
                for cmd in p.commands() {
                    self.say("$ " + cmd)
                    let wd = p.name == "Flux code" ? home : repo
                    let (code, last) = self.shell(cmd, cwd: wd, env: ["ARGMAX_TOKEN": token])
                    if code != 0 {
                        DispatchQueue.main.async {
                            self.installing = false; self.failedPart = p.name
                            self.statusL.stringValue = "\(p.name) didn't install: \(last). Details has the output."
                            self.statusL.textColor = .systemRed; self.go(1)
                        }
                        return
                    }
                }
                if p.name == "Flux code" { UserDefaults.standard.set(repo, forKey: "FluxRepo") }
            }
            DispatchQueue.main.async {
                self.installing = false
                self.statusL.stringValue = "All parts are installed."; self.statusL.textColor = .systemGreen
                self.go(1)
            }
        }
    }

    func xcodeReady() -> Bool { run("/usr/bin/xcrun", ["--find", "swift"], timeout: 20).0 == 0 }

    /// Run one shell line, streaming its output into Details. Returns (exit code, last output line).
    func shell(_ cmd: String, cwd: String, env extra: [String: String]) -> (Int32, String) {
        let p = Process(); p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        p.arguments = ["-l", "-c", shellPath + cmd]
        p.currentDirectoryURL = URL(fileURLWithPath: cwd)
        var e = env; for (k, v) in extra { e[k] = v }; p.environment = e
        let pipe = Pipe(); p.standardOutput = pipe; p.standardError = pipe; p.standardInput = FileHandle.nullDevice
        var last = ""
        pipe.fileHandleForReading.readabilityHandler = { h in
            let s = String(decoding: h.availableData, as: UTF8.self)
            for line in s.split(whereSeparator: { $0 == "\n" || $0 == "\r" }) where !line.trimmingCharacters(in: .whitespaces).isEmpty {
                last = String(line); self.say(String(line))
                DispatchQueue.main.async { self.statusL.stringValue = String(line.prefix(90)) }
            }
        }
        do { try p.run() } catch { return (-1, error.localizedDescription) }
        p.waitUntilExit()
        pipe.fileHandleForReading.readabilityHandler = nil
        return (p.terminationStatus, last.isEmpty ? "exit \(p.terminationStatus)" : String(last.prefix(120)))
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

if CommandLine.arguments.contains("--parts") {
    for p in parts() { print("\(p.name)\t\(p.done() ? "installed" : "missing")") }
    exit(0)
}

let app = NSApplication.shared
let delegate = App()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
