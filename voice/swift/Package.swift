// swift-tools-version: 6.0
//
// argmax-voice: push-to-talk speech-to-text for Python, on the Argmax Pro SDK.
// Needs the one-time Argmax registry login (see samples/argmax-pro-sdk/native/README.md).
// The executable name is fixed: the Neural Engine compile cache lives in
// ~/Library/Caches/argmax-voice/, so renaming it costs a ~4-minute recompile.
import PackageDescription

let package = Package(
    name: "ArgmaxVoice",
    platforms: [.macOS(.v15)],
    products: [.executable(name: "argmax-voice", targets: ["ArgmaxVoice"])],
    dependencies: [
        .package(id: "argmaxinc.argmax-sdk-swift", exact: "3.1.8"),
    ],
    targets: [
        .executableTarget(
            name: "ArgmaxVoice",
            dependencies: [.product(name: "Argmax", package: "argmaxinc.argmax-sdk-swift")],
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
    ]
)
