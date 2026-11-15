#!/usr/bin/env bash
# Build app/dist/Muse.dmg for another Mac: Muse.app (no repo path baked in),
# INSTALL.html and setup.sh. No models, keys or bank data. No Developer ID signing.
#   app/make_dmg.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DIST="$HERE/dist"
STAGE="$DIST/stage"

rm -rf "$STAGE" "$DIST/Muse.dmg"
mkdir -p "$STAGE"
MUSE_APP_OUT="$STAGE" MUSE_NO_REPO=1 "$HERE/build.sh"   # separate folder: app/build/ is untouched
cp "$HERE/dmg/INSTALL.html" "$HERE/dmg/setup.sh" "$STAGE/"
chmod +x "$STAGE/setup.sh"
ln -s /Applications "$STAGE/Applications"
hdiutil create -quiet -volname Muse -srcfolder "$STAGE" -format UDZO -ov "$DIST/Muse.dmg"
rm -rf "$STAGE"
echo "Built $DIST/Muse.dmg ($(du -h "$DIST/Muse.dmg" | cut -f1))"
