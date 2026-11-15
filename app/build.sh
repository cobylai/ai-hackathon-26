#!/usr/bin/env bash
# Build app/Muse.app (menu-bar panel + Fn-Space). No Xcode project, no signing identity.
#   app/build.sh            # -> app/build/Muse.app, runs servers from the main checkout
#   MUSE_APP_OUT=app/dist MUSE_NO_REPO=1 app/build.sh   # for the DMG: no path baked in
# The app runs the servers from the main checkout (models live only there);
# MUSE_REPO at build time, or `defaults write local.ai-hackathon-26.muse MuseRepo <path>`, points it elsewhere.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
TOP="$(cd "$HERE/.." && pwd)"
REPO="${MUSE_REPO:-${TOP%%/.claude/worktrees/*}}"
[ -n "${MUSE_NO_REPO:-}" ] && REPO=""
OUT="${MUSE_APP_OUT:-$HERE/build}"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
APP="$OUT/Muse.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -o "$APP/Contents/MacOS/Muse" "$HERE/Muse.swift" \
  -framework Cocoa -framework WebKit -framework Carbon -framework AVFoundation -framework Security
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Muse</string>
  <key>CFBundleIdentifier</key><string>local.ai-hackathon-26.muse</string>
  <key>CFBundleExecutable</key><string>Muse</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>LSMinimumSystemVersion</key><string>15.0</string>
  <key>LSUIElement</key><true/>
  <key>NSAppleEventsUsageDescription</key><string>Muse reads your Muse demo calendar in Calendar to answer schedule questions.</string>
  <key>NSMicrophoneUsageDescription</key><string>Muse listens only while you hold the hotkey or the talk button.</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
  <key>MuseRepo</key><string>$REPO</string>
</dict></plist>
PLIST
codesign --force -s - "$APP"   # ad-hoc, so macOS can remember the microphone allow
echo "Built $APP (servers from ${REPO:-~/ai-hackathon-26 or defaults MuseRepo})"
