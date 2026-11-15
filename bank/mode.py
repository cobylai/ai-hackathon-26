"""Demo or live: which data Flux answers from. One setting, read by every part.

    from bank import mode
    mode.current()        # "demo" | "live"
    mode.bank_default()   # ~/flux-demo-bank (demo) | ~/flux-bank (live)
    mode.calendar()       # "Flux demo" (demo) | the calendar you named (live), "" if none yet
    mode.reminders()      # "Flux demo" (demo) | "" = the Reminders default list (live)

The setting is the file ~/.flux/mode ("demo" or "live"); no file means live. FLUX_MODE
overrides the file. `scripts/flux-mode demo|live` writes it. Switching never copies data:
the two states use different folders, calendars and lists. Live mode reads ONE calendar, the
one you name (`scripts/flux-mode live --calendar "Home"`, saved in ~/.flux/calendar): reading
every calendar on a busy Mac takes over a minute. An explicit FLUX_BANK_DIR,
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


def calendar_file() -> Path:
    return mode_file().with_name("calendar")


def calendar() -> str:
    if is_demo():
        return DEMO_CALENDAR
    try:
        return calendar_file().read_text().strip()
    except OSError:
        return ""


def set_calendar(name: str) -> Path:
    name = name.strip()
    if not name or name == DEMO_CALENDAR:
        raise ValueError(f"live mode needs your own calendar, not {name!r}")
    p = calendar_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(name + "\n")
    return p


def reminders() -> str:
    return DEMO_REMINDERS if is_demo() else ""


def label() -> str:
    """Plain words for the status line."""
    return "Demo data" if is_demo() else "Your data"
