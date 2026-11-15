#!/usr/bin/env bash
# Flux setup for a new Mac (Apple Silicon, macOS 15+). Read it before you run it.
#
#   bash setup.sh                 # installs into ~/ai-hackathon-26
#   MUSE_DIR=~/somewhere bash setup.sh
#
# Each part is installed on its own, and every step prints what it will run.
# It asks before every download or install, skips what's already there, and
# never uses sudo. Nothing is sent anywhere except the downloads named below.
# The same steps by hand, with links: INSTALL.html on the Flux disk image.
set -euo pipefail

DIR="${MUSE_DIR:-$HOME/ai-hackathon-26}"
# Where the Flux code lives. app/make_dmg.sh fills this in from MUSE_REPO_URL; MUSE_REPO_URL overrides it.
REPO_URL="${MUSE_REPO_URL:-@REPO_URL@}"
MLX="$DIR/samples/bonsai-models/mlx"
BONSAI="$MLX/models/bonsai2-4b-mlx"
WHISPER_ROOT="$HOME/Documents/huggingface/models/argmaxinc/whisperkit-coreml"
WHISPER="$WHISPER_ROOT/openai_whisper-large-v3-v20240930_626MB"

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
show() { printf '   $ %s\n' "$*"; }
ask() {  # ask "question" -> 0 for yes
  local a; read -r -p "   $1 [y/N] " a </dev/tty; [[ "$a" == [yY]* ]]
}
run() { show "$@"; "$@"; }
skip() { printf '   already done: %s\n' "$1"; }

[ "$(uname -s)-$(uname -m)" = "Darwin-arm64" ] || { echo "Flux needs an Apple Silicon Mac."; exit 1; }
echo "Flux setup. Code goes in: $DIR"

step "0. Xcode (for building the voice program)"
if xcrun --find swift >/dev/null 2>&1; then skip "$(swift --version 2>/dev/null | head -1)"
else echo "   Install Xcode 16+ from the App Store, open it once, then run this again."; exit 1; fi

step "1. uv (Python package manager) — https://docs.astral.sh/uv/"
if command -v uv >/dev/null; then skip "uv $(uv --version | cut -d' ' -f2)"
else
  show "curl -LsSf https://astral.sh/uv/install.sh | sh"
  ask "Install uv into your home folder?" || exit 1
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

step "2. The Flux code — $REPO_URL"
if [ -d "$DIR/.git" ]; then skip "$DIR"
elif [[ "$REPO_URL" != http* && "$REPO_URL" != git@* ]]; then
  echo "   This copy of setup.sh doesn't say where the code lives. Ask whoever gave you Flux,"
  echo "   then run:  MUSE_REPO_URL=<url> bash setup.sh"; exit 1
else
  ask "Clone it into $DIR?" || exit 1
  run git clone "$REPO_URL" "$DIR"
fi
cd "$DIR"

step "3. Python packages and the browser harness's Chromium — https://playwright.dev/python/"
show "uv sync && uv run playwright install chromium"
if ask "Install them (about 200 MB)?"; then run uv sync; run uv run playwright install chromium; fi

step "4. Bonsai 2 4B, the local language model — https://huggingface.co/prism-ml/Ternary-Bonsai-2-4B-mlx-2bit"
if [ -x "$MLX/.venv/bin/python" ]; then skip "Bonsai venv $MLX/.venv"
elif ask "Make Bonsai's own Python env with mlx-vlm in $MLX/.venv?"; then
  run uv venv --python 3.12 "$MLX/.venv"
  run uv pip install --python "$MLX/.venv/bin/python" -r "$MLX/requirements.txt"
fi
if [ -f "$BONSAI/model.safetensors" ]; then skip "$BONSAI"
elif ask "Download Bonsai 2 4B (about 1 GB) into $BONSAI?"; then
  run "$MLX/.venv/bin/hf" download prism-ml/Ternary-Bonsai-2-4B-mlx-2bit --local-dir "$BONSAI"
fi

step "5. Whisper speech model for Argmax — https://huggingface.co/argmaxinc/whisperkit-coreml"
if [ -d "$WHISPER" ]; then skip "$WHISPER"
elif ask "Download Whisper large-v3 turbo (about 630 MB) into $WHISPER_ROOT?"; then
  run "$MLX/.venv/bin/hf" download argmaxinc/whisperkit-coreml \
    --include "openai_whisper-large-v3-v20240930_626MB/*" --local-dir "$WHISPER_ROOT"
fi

step "6. Argmax SDK and the voice program — https://app.argmaxinc.com"
echo "   You need YOUR OWN Argmax secret token (axst_…) for the SDK download, and your own"
echo "   ax_ key, which Flux asks for at first launch. Each Mac needs its own key."
if [ -x "$DIR/voice/swift/.build/release/argmax-voice" ]; then skip "voice/swift built"
elif ask "Log in to Argmax's Swift package registry and build voice/swift (about 1 min)?"; then
  if [ ! -f "$HOME/.swiftpm/configuration/registries.json" ] || ! grep -q argmaxinc "$HOME/.swiftpm/configuration/registries.json"; then
    run swift package-registry set --global --scope argmaxinc https://api.argmaxinc.com/v1/sdk
    read -r -s -p "   Paste your Argmax secret token (axst_…, hidden): " TOKEN </dev/tty; echo
    show "swift package-registry login https://api.argmaxinc.com/v1/sdk/login --token <hidden>"
    swift package-registry login https://api.argmaxinc.com/v1/sdk/login --token "$TOKEN"
    unset TOKEN
  else skip "registry login"; fi
  (cd voice/swift && run swift build -c release)
fi

step "7. Demo bank: 20 made-up emails, so nobody's real mail is shown"
if [ -f "$HOME/muse-demo-bank/index.md" ]; then skip "$HOME/muse-demo-bank"
elif ask "Write the sample mail and file it into ~/muse-demo-bank (uses Bonsai, about 1 min)?"; then
  STARTED=""
  if ! curl -s -m 2 localhost:8080/v1/models >/dev/null; then
    show "scripts/serve_bonsai.sh 4B &"
    scripts/serve_bonsai.sh 4B >/tmp/muse-setup-bonsai.log 2>&1 & STARTED=$!
    until curl -s -m 2 localhost:8080/v1/models >/dev/null; do sleep 2; done
  fi
  DAY=$(date +%F)
  run uv run python scripts/make_test_mail.py write "$HOME/muse-demo-mail" --today "$DAY"
  MUSE_BANK_DIR="$HOME/muse-demo-bank" run uv run python -m bank.load "$HOME/muse-demo-mail" --kind email
  [ -n "$STARTED" ] && kill "$STARTED"
fi

step "8. Point Flux at this folder"
run defaults write local.ai-hackathon-26.flux MuseRepo "$DIR"

cat <<EOF

Done. Next:
  - Calendar.app: File > New Calendar, name it "Muse demo", add a few made-up events.
  - Drag Flux.app to Applications and open it.
  - "Set Up Flux" walks you through your ax_ key (kept in your Keychain), Accessibility
    (for Fn-Space), the microphone, Calendar, Reminders and Mail, one screen each.
  - The first voice start on a new Mac takes several minutes while macOS compiles the
    speech model (one time only). Leave it running.
EOF
