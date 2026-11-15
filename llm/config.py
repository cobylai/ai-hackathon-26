"""The one place Bonsai settings live.

Change the model size with the BONSAI_SIZE env var (2B | 4B | 9B). Both the
client and scripts/serve_bonsai.sh read it, and nothing else sets a size.
"""
import os
from pathlib import Path

# Model size. Default 4B; move to 9B only where 4B fails.
BONSAI_SIZE = os.environ.get("BONSAI_SIZE", "4B").upper()

# Local server only. No other provider, no fallback.
BASE_URL = os.environ.get("BONSAI_BASE_URL", "http://localhost:8080/v1").rstrip("/")

# Bonsai 2 context window as set by the hackathon rules (the model card says
# 262k, but the event limit is 32k and we hold to that).
CONTEXT_TOKENS = 32768

# Sampling presets from the model card. mlx-vlm decodes greedily without them
# and never reads presence_penalty / min_p from the model, so send every one.
PRESETS = {
    "thinking": dict(temperature=1.0, top_p=0.95, top_k=20, min_p=0.0,
                     presence_penalty=1.0, repetition_penalty=1.0),
    "non_thinking": dict(temperature=0.7, top_p=0.80, top_k=20, min_p=0.0,
                         presence_penalty=1.5, repetition_penalty=1.0),
}

# Default output reservations (the model card says thinking needs >= 8192).
DEFAULT_MAX_TOKENS = 2048
THINKING_MAX_TOKENS = 8192

# HTTP timeout per call, seconds.
TIMEOUT_S = float(os.environ.get("BONSAI_TIMEOUT_S", "300"))


def _main_checkout(path: Path) -> Path:
    """Worktrees live at <main>/.claude/worktrees/<name>; models only exist in <main>."""
    parts = path.parts
    if ".claude" in parts and "worktrees" in parts:
        i = parts.index(".claude")
        return Path(*parts[:i])
    return path


_REPO = Path(__file__).resolve().parent.parent
MODELS_DIR = Path(os.environ.get(
    "BONSAI_MODELS_DIR",
    _main_checkout(_REPO) / "samples" / "bonsai-models" / "mlx" / "models",
))


def model_dir(size: str = BONSAI_SIZE) -> Path:
    return MODELS_DIR / f"bonsai2-{size.lower()}-mlx"
