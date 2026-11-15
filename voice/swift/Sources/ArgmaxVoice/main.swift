// argmax-voice: one long-running process. Loads the model once from disk (no downloader),
// then records the microphone only between `start` and `stop` lines on stdin and prints
// the transcript as one JSON line on stdout.
//
// stdin:  start | stop | file <path.wav> | quit
// stdout: {"event":"ready"} {"event":"recording"} {"event":"text","text":"...","seconds":2.4}
//         {"event":"error","message":"..."}
// Logs go to stderr so stdout stays machine-readable.

import Argmax
import AVFoundation
import Foundation

setvbuf(stdout, nil, _IOLBF, 0)

func emit(_ object: [String: Any]) {
    let data = try! JSONSerialization.data(withJSONObject: object, options: [.withoutEscapingSlashes])
    FileHandle.standardOutput.write(data + Data("\n".utf8))
}
func emitError(_ message: String) { emit(["event": "error", "message": message]) }
func log(_ message: String) { FileHandle.standardError.write(Data("[argmax-voice] \(message)\n".utf8)) }
func fail(_ message: String) -> Never { emitError(message); exit(1) }

let defaultModelFolder = FileManager.default.homeDirectoryForCurrentUser
    .appending(path: "Documents/huggingface/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB").path
let modelName = "large-v3-v20240930_626MB"

/// Records the default input device, converted to 16 kHz mono Float32, between start() and stop().
final class Recorder {
    private let engine = AVAudioEngine()
    private let lock = NSLock()
    private var samples: [Float] = []
    private var converter: AVAudioConverter?
    private let target = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 16_000, channels: 1, interleaved: false)!
    private(set) var isRecording = false

    func start() throws {
        lock.withLock { samples.removeAll() }
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0, format.channelCount > 0 else {
            throw NSError(domain: "argmax-voice", code: 1, userInfo: [NSLocalizedDescriptionKey: "no microphone input device"])
        }
        converter = AVAudioConverter(from: format, to: target)
        input.installTap(onBus: 0, bufferSize: 4096, format: format) { [weak self] buffer, _ in
            self?.append(buffer)
        }
        engine.prepare()
        try engine.start()
        isRecording = true
    }

    func stop() -> [Float] {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        isRecording = false
        return lock.withLock { samples }
    }

    private func append(_ buffer: AVAudioPCMBuffer) {
        guard let converter else { return }
        let ratio = target.sampleRate / buffer.format.sampleRate
        let capacity = AVAudioFrameCount(Double(buffer.frameLength) * ratio) + 64
        guard let out = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: capacity) else { return }
        var fed = false
        var error: NSError?
        converter.convert(to: out, error: &error) { _, status in
            if fed { status.pointee = .noDataNow; return nil }
            fed = true
            status.pointee = .haveData
            return buffer
        }
        guard error == nil, let channel = out.floatChannelData?[0] else { return }
        let chunk = Array(UnsafeBufferPointer(start: channel, count: Int(out.frameLength)))
        lock.withLock { samples.append(contentsOf: chunk) }
    }
}

func microphoneAllowed() async -> Bool {
    switch AVCaptureDevice.authorizationStatus(for: .audio) {
    case .authorized: return true
    case .notDetermined: return await AVCaptureDevice.requestAccess(for: .audio)
    default: return false
    }
}

func transcribe(_ whisperKit: WhisperKitPro, _ audio: [Float]) async {
    let seconds = (Double(audio.count) / 16_000 * 10).rounded() / 10
    guard audio.count > 16_000 / 4 else { emitError("recording too short (\(seconds) s)"); return }
    do {
        let options = DecodingOptions(task: .transcribe, language: "en", chunkingStrategy: .vad)
        let results = try await whisperKit.transcribe(audioArray: audio, decodeOptions: options)
        let text = WhisperKitProUtils.mergeTranscriptionResults(results).text
            .trimmingCharacters(in: .whitespacesAndNewlines)
        emit(["event": "text", "text": text, "seconds": seconds])
    } catch {
        emitError("transcription failed: \(error)")
    }
}

// MARK: - Startup: license, then model from disk

guard let key = ProcessInfo.processInfo.environment["ARGMAX_API_KEY"], key.hasPrefix("ax_") else {
    fail("ARGMAX_API_KEY is not set (expected an ax_ key)")
}
let modelFolder = ProcessInfo.processInfo.environment["ARGMAX_MODEL_FOLDER"].flatMap { $0.isEmpty ? nil : $0 } ?? defaultModelFolder
guard FileManager.default.fileExists(atPath: modelFolder) else {
    fail("model folder not found: \(modelFolder)")
}

await ArgmaxSDK.with(ArgmaxConfig(apiKey: key))
log("loading \(modelName) from \(modelFolder)")
let whisperKit: WhisperKitPro
do {
    whisperKit = try await WhisperKitPro(WhisperKitProConfig(model: modelName, modelFolder: modelFolder, download: false))
} catch {
    fail("model or license failed to load: \(error)")
}
let recorder = Recorder()
emit(["event": "ready"])

// MARK: - Command loop

while let line = readLine() {
    let parts = line.trimmingCharacters(in: .whitespaces).split(separator: " ", maxSplits: 1).map(String.init)
    switch parts.first ?? "" {
    case "start":
        guard !recorder.isRecording else { emitError("already recording"); continue }
        guard await microphoneAllowed() else {
            emitError("microphone permission denied: allow your terminal app in System Settings > Privacy & Security > Microphone")
            continue
        }
        do { try recorder.start(); emit(["event": "recording"]) } catch { emitError("microphone failed to start: \(error.localizedDescription)") }
    case "stop":
        guard recorder.isRecording else { emitError("not recording"); continue }
        await transcribe(whisperKit, recorder.stop())
    case "file" where parts.count == 2:
        do { await transcribe(whisperKit, try AudioProcessor.loadAudioAsFloatArray(fromPath: parts[1])) } catch { emitError("could not read audio file: \(error)") }
    case "quit":
        exit(0)
    case "":
        continue
    default:
        emitError("unknown command: \(line)")
    }
}
