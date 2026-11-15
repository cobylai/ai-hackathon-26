#!/usr/bin/env bash
# Headless Bonsai 2 server for Muse. Never downloads, never opens a browser.
#   scripts/serve_bonsai.sh          # BONSAI_SIZE or 4B
#   scripts/serve_bonsai.sh 9B       # 2B | 4B | 9B
# Env: PORT (8080), BONSAI_MODELS_DIR, BONSAI_VENV.
# Binds 127.0.0.1 only: mlx_vlm.server defaults to 0.0.0.0, which the local network can reach.
set -euo pipefail

SIZE="$(echo "${1:-${BONSAI_SIZE:-4B}}" | tr 'b' 'B')"
PORT="${PORT:-8080}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
# Worktrees sit at <main>/.claude/worktrees/<name>; models live only in <main>.
MAIN="${HERE%%/.claude/worktrees/*}"
MLX="$MAIN/samples/bonsai-models/mlx"
MODELS="${BONSAI_MODELS_DIR:-$MLX/models}"
VENV="${BONSAI_VENV:-$MLX/.venv}"

case "$SIZE" in 2B|4B|9B) ;; *) echo "Size must be 2B, 4B or 9B (got $SIZE)" >&2; exit 1 ;; esac
[ "$(uname -s)-$(uname -m)" = "Darwin-arm64" ] || { echo "MLX needs an Apple Silicon Mac." >&2; exit 1; }

MODEL="$MODELS/bonsai2-$(echo "$SIZE" | tr 'B' 'b')-mlx"
if [ ! -f "$MODEL/model.safetensors" ]; then
  echo "Model missing: $MODEL/model.safetensors" >&2
  echo "This script never downloads. With internet, run once:" >&2
  echo "  (cd $MLX && ./start.sh $SIZE)   # or: hf download prism-ml/Ternary-Bonsai-2-$SIZE-mlx-2bit --local-dir $MODEL" >&2
  exit 1
fi
if [ ! -x "$VENV/bin/python" ]; then
  echo "Venv missing: $VENV (needs Python 3.10+ with mlx-vlm; see $MLX/README.md)" >&2
  exit 1
fi
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use. Only one Bonsai server at a time; stop the other first." >&2
  exit 1
fi

export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
echo "Serving Bonsai 2 $SIZE from $MODEL on http://localhost:$PORT/v1 (offline)"
exec "$VENV/bin/python" -m mlx_vlm.server --model "$MODEL" --host 127.0.0.1 --port "$PORT"
