"""Paths and limits shared by every harness tool."""

from pathlib import Path

HOME_DIR = Path.home() / ".harness"
PROFILE_DIR = HOME_DIR / "profile"
FILTER_DIR = HOME_DIR / "filters"
EXTENSIONS_DIR = HOME_DIR / "extensions"

MAX_CHARS = 1500

# Extension layer (task B3b). Off until it is shown to load headless.
USE_UBOL = False
