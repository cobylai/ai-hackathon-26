"""Demo or live: which data Flux answers from. One setting, read by every part.

    from bank import mode
    mode.current()        # "demo" | "live"
    mode.bank_default()   # ~/flux-demo-bank (demo) | ~/flux-bank (live)
    mode.calendar()       # "Flux demo" (demo) | "" = every calendar on this Mac (live)
    mode.reminders()      # "Flux demo" (demo) | "" = the Reminders default list (live)

The setting is the file ~/.flux/mode ("demo" or "live"); no file means live. FLUX_MODE
overrides the file. `scripts/flux-mode demo|live` writes it. Switching never copies data:
the two states use different folders, calendars and lists. An explicit FLUX_BANK_DIR,
FLUX_CALENDAR or FLUX_REMINDERS still wins over either mode's default.
"""
from __future__ import annotations

import os
from pathlib import Path

MODES = ("demo", "live")
DEMO_BANK = "~/flux-demo-bank"
LIVE_BANK = "~/flux-bank"
DEMO_CALENDAR = "Flux demo"
DEMO_REMINDERS = "Flux demo"


def mode_file() -> Path:
    return Path(os.environ.get("FLUX_MODE_FILE") or "~/.flux/mode").expanduser()


def current() -> str:
    env = (os.environ.get("FLUX_MODE") or "").strip().lower()
    if env in MODES:
        return env
    try:
        word = mode_file().read_text().strip().lower()
    except OSError:
        return "live"
    return word if word in MODES else "live"


def set_mode(word: str) -> Path:
    if word not in MODES:
        raise ValueError(f"mode must be one of {MODES}, not {word!r}")
    p = mode_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(word + "\n")
    return p


def is_demo() -> bool:
    return current() == "demo"


def bank_default() -> Path:
    return Path(DEMO_BANK if is_demo() else LIVE_BANK).expanduser()


def calendar() -> str:
    return DEMO_CALENDAR if is_demo() else ""


def reminders() -> str:
    return DEMO_REMINDERS if is_demo() else ""


def label() -> str:
    """Plain words for the status line."""
    return "Demo data" if is_demo() else "Your data"
