#!/usr/bin/env bash
# What Set Up Flux's Install step detects as installed, run against the real app binary (Flux --parts).
#   app/tests/test_parts.sh
# Bonsai 2 4B counts as installed when the 4B model is in the code folder, in the main checkout
# (when the code folder is a worktree), in BONSAI_MODELS_DIR, or when a Bonsai server already answers.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'kill $SRV 2>/dev/null; rm -rf "$T"' EXIT; SRV=""
swiftc -O -o "$T/Flux" "$HERE/Flux.swift" -framework Cocoa -framework WebKit -framework Carbon \
  -framework AVFoundation -framework Security || { echo "build failed"; exit 1; }
fail=0
code() { mkdir -p "$1/scripts"; touch "$1/scripts/serve_bonsai.sh"; }
model() { mkdir -p "$1/bonsai2-4b-mlx"; touch "$1/bonsai2-4b-mlx/model.safetensors"; }
NOSERVER="http://127.0.0.1:9/v1/models"   # nothing listens on port 9
check() {  # check <name> <want> env...
  local name="$1" want="$2"; shift 2
  local got; got="$(env -i HOME="$HOME" FLUX_BONSAI_URL="$NOSERVER" "$@" "$T/Flux" --parts | awk -F'\t' '$1=="Bonsai 2 4B"{print $2}')"
  if [ "$got" = "$want" ]; then echo "ok    $name"; else echo "FAIL  $name: got '$got', want '$want'"; fail=1; fi
}

code "$T/a"
check "no model, no server"                missing   FLUX_REPO="$T/a"
code "$T/b"; model "$T/b/samples/bonsai-models/mlx/models"
check "model in the code folder"           installed FLUX_REPO="$T/b"
code "$T/main/.claude/worktrees/w"; model "$T/main/samples/bonsai-models/mlx/models"
check "worktree: model in main checkout"   installed FLUX_REPO="$T/main/.claude/worktrees/w"
code "$T/c"; model "$T/elsewhere"
check "BONSAI_MODELS_DIR"                  installed FLUX_REPO="$T/c" BONSAI_MODELS_DIR="$T/elsewhere"
mkdir -p "$T/srv/v1"; echo '{"data":[]}' > "$T/srv/v1/models"
PORT=$((20000 + RANDOM % 20000))
(cd "$T/srv" && exec python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1) & SRV=$!; disown $SRV
for _ in $(seq 1 50); do curl -s -m1 "http://127.0.0.1:$PORT/v1/models" >/dev/null && break; sleep 0.1; done
got="$(env -i HOME="$HOME" FLUX_REPO="$T/a" FLUX_BONSAI_URL="http://127.0.0.1:$PORT/v1/models" "$T/Flux" --parts | awk -F'\t' '$1=="Bonsai 2 4B"{print $2}')"
if [ "$got" = installed ]; then echo "ok    server already answering"; else echo "FAIL  server already answering: got '$got'"; fail=1; fi
exit $fail
