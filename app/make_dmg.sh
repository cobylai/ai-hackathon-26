#!/usr/bin/env bash
# Build app/dist/Muse.dmg for another Mac, signed and notarized:
#   app/make_dmg.sh                    # needs the "Muse-notarize" notarytool profile
#   MUSE_NOTARIZE=0 app/make_dmg.sh    # signed, not notarized (testing)
#   MUSE_REPO_URL=https://… app/make_dmg.sh   # where setup.sh clones the code from (else: "ask whoever gave you Muse")
#   MUSE_DMG_OUT=app/dist/Muse-test.dmg app/make_dmg.sh   # another output name
# Order: build + sign Muse.app (app/build.sh, Developer ID, hardened runtime) -> notarize + staple
# the app -> DMG with the drag window (dmgbuild via uvx) -> sign -> notarize + staple the DMG -> check.
# Contents: Muse.app (no repo path baked in), INSTALL.html, setup.sh, Applications link. No models,
# keys or bank data. app/build/ (your own app) is untouched.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DIST="$HERE/dist"
STAGE="$DIST/stage"
ART="$DIST/art"
DMG="${MUSE_DMG_OUT:-$DIST/Muse.dmg}"
PROFILE="${MUSE_NOTARY_PROFILE:-Muse-notarize}"
DEVID="Developer ID Application: Coby Lai (XD7QDRDR78)"
NOTARIZE="${MUSE_NOTARIZE:-1}"

step() { printf '\n== %s\n' "$1"; }
notarize() {  # notarize <file>: submit, wait, fail loudly with the log on rejection
  local out id
  out="$(xcrun notarytool submit "$1" --keychain-profile "$PROFILE" --wait 2>&1)"; echo "$out" | grep -E "id:|status:" | head -3
  if ! echo "$out" | grep -q "status: Accepted"; then
    id="$(echo "$out" | awk '/ id:/{print $2; exit}')"
    [ -n "$id" ] && xcrun notarytool log "$id" --keychain-profile "$PROFILE"
    echo "Notarization failed for $1" >&2; exit 1
  fi
}

if [ "$NOTARIZE" = 1 ] && ! xcrun notarytool history --keychain-profile "$PROFILE" >/dev/null 2>&1; then
  cat >&2 <<MSG
The notary profile "$PROFILE" isn't usable yet. Once, by hand:
  1. Accept the current agreement at https://developer.apple.com/account
  2. https://appleid.apple.com > Sign-In and Security > App-Specific Passwords > new: "Muse notarize"
  3. xcrun notarytool store-credentials "$PROFILE" --apple-id <your Apple ID> --team-id XD7QDRDR78
Or MUSE_NOTARIZE=0 app/make_dmg.sh for a signed, not notarized test build.
MSG
  exit 1
fi

rm -rf "$STAGE" "$ART" "$DMG"
mkdir -p "$STAGE" "$ART"

step "Build and sign Muse.app"
MUSE_APP_OUT="$STAGE" MUSE_NO_REPO=1 MUSE_SIGN="$DEVID" "$HERE/build.sh"
# The code's location is one setting; no personal names in the shipped text.
REPO_URL="${MUSE_REPO_URL:-}"
if [ -n "$REPO_URL" ]; then
  REPO_LINE="Get it from <a href=\"$REPO_URL\">$REPO_URL</a>. If it's private, ask whoever gave you Muse for access."
else
  REPO_URL="&lt;repo URL&gt;"; REPO_LINE="Ask whoever gave you Muse where to get it (the repo URL)."
fi
python3 - "$HERE/dmg/INSTALL.html" "$STAGE/INSTALL.html" "$REPO_URL" "$REPO_LINE" <<'PY'
import sys; src, dst, url, line = sys.argv[1:]
open(dst, "w").write(open(src).read().replace("@REPO_LINE@", line).replace("@REPO_URL@", url))
PY
sed "s|@REPO_URL@|${MUSE_REPO_URL:-not set}|" "$HERE/dmg/setup.sh" > "$STAGE/setup.sh"
chmod +x "$STAGE/setup.sh"

if [ "$NOTARIZE" = 1 ]; then
  step "Notarize and staple Muse.app"
  ditto -c -k --keepParent "$STAGE/Muse.app" "$DIST/Muse-app.zip"
  notarize "$DIST/Muse-app.zip"
  rm -f "$DIST/Muse-app.zip"
  xcrun stapler staple "$STAGE/Muse.app"
fi

step "Make the DMG window (background drawn by app/dmg/art.swift)"
swift "$HERE/dmg/art.swift" "$ART" >/dev/null
tiffutil -cathidpicheck "$ART/background.png" "$ART/background@2x.png" -out "$ART/background.tiff" 2>/dev/null
uvx --quiet --python 3.12 dmgbuild -s "$HERE/dmg/dmg_settings.py" -D stage="$STAGE" -D art="$ART" "Muse" "$DMG"

step "Sign the DMG"
codesign --force --timestamp -s "$DEVID" "$DMG"

if [ "$NOTARIZE" = 1 ]; then
  step "Notarize and staple the DMG"
  notarize "$DMG"
  xcrun stapler staple "$DMG"
  step "Check"
  xcrun stapler validate "$DMG"
  spctl -a -vvv -t open --context context:primary-signature "$DMG"
  spctl -a -vvv "$STAGE/Muse.app"
fi

rm -rf "$STAGE" "$ART"
echo "Built $DMG ($(du -h "$DMG" | cut -f1))$([ "$NOTARIZE" = 1 ] && echo ', notarized and stapled' || echo ', signed, NOT notarized')"
