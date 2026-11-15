#!/usr/bin/env bash
# Build Flux.app (menu-bar panel + Fn-Space). No Xcode project.
#   app/build.sh            # -> app/build/Flux.app, runs servers from the main checkout
#   FLUX_APP_OUT=app/dist FLUX_NO_REPO=1 app/build.sh   # for the DMG: no path baked in
# Signing: "Developer ID Application: Coby Lai (XD7QDRDR78)" with the hardened runtime when that
# identity is in the keychain, so macOS keeps Flux's permissions across rebuilds; else ad hoc.
# FLUX_SIGN=adhoc forces ad hoc; FLUX_SIGN="<identity>" picks another.
# The app runs the servers from the main checkout (models live only there);
# FLUX_REPO_URL at build time: where Set Up clones the code from (empty: it asks).
# FLUX_REPO at build time, or `defaults write local.ai-hackathon-26.flux FluxRepo <path>`, points it elsewhere.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
TOP="$(cd "$HERE/.." && pwd)"
REPO="${FLUX_REPO:-${TOP%%/.claude/worktrees/*}}"
[ -n "${FLUX_NO_REPO:-}" ] && REPO=""
OUT="${FLUX_APP_OUT:-$HERE/build}"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
APP="$OUT/Flux.app"
DEVID="Developer ID Application: Coby Lai (XD7QDRDR78)"
SIGN="${FLUX_SIGN:-}"
if [ -z "$SIGN" ]; then
  if security find-identity -v -p codesigning | grep -q "$DEVID"; then SIGN="$DEVID"; else SIGN="adhoc"; fi
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -o "$APP/Contents/MacOS/Flux" "$HERE/Flux.swift" \
  -framework Cocoa -framework WebKit -framework Carbon -framework AVFoundation -framework Security
ART="$(mktemp -d)"
swift "$HERE/dmg/art.swift" "$ART" >/dev/null
iconutil -c icns "$ART/Flux.iconset" -o "$APP/Contents/Resources/Flux.icns"
rm -rf "$ART"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Flux</string>
  <key>CFBundleDisplayName</key><string>Flux</string>
  <key>CFBundleIdentifier</key><string>local.ai-hackathon-26.flux</string>
  <key>CFBundleExecutable</key><string>Flux</string>
  <key>CFBundleIconFile</key><string>Flux</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.2</string>
  <key>CFBundleVersion</key><string>$(date +%Y%m%d%H%M)</string>
  <key>LSMinimumSystemVersion</key><string>15.0</string>
  <key>LSUIElement</key><true/>
  <key>NSAppleEventsUsageDescription</key><string>Flux reads your calendar, and adds events, reminders or opens an email when you ask.</string>
  <key>NSMicrophoneUsageDescription</key><string>Flux listens only while you hold the hotkey or the talk button.</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
  <key>FluxRepo</key><string>$REPO</string>
  <key>FluxRepoURL</key><string>${FLUX_REPO_URL:-}</string>
</dict></plist>
PLIST
if [ "$SIGN" = "adhoc" ]; then
  codesign --force -s - "$APP"
else
  codesign --force --options runtime --timestamp --entitlements "$HERE/Flux.entitlements" -s "$SIGN" "$APP"
fi
codesign --verify --strict "$APP"
echo "Built $APP (signed: $SIGN; servers from ${REPO:-~/ai-hackathon-26 or defaults FluxRepo})"
