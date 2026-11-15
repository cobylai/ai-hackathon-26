"""Paths and limits shared by every harness tool."""

import os
from pathlib import Path

HOME_DIR = Path.home() / ".harness"
# `HARNESS_PROFILE_DIR` lets a second harness process (an eval, a test run) use
# its own Chromium profile while another one holds the default.
PROFILE_DIR = Path(os.environ.get("HARNESS_PROFILE_DIR") or HOME_DIR / "profile")
FILTER_DIR = HOME_DIR / "filters"
EXTENSIONS_DIR = HOME_DIR / "extensions"

MAX_CHARS = 1500

# Extension layer (task B3b). Off until it is shown to load headless.
USE_UBOL = False
