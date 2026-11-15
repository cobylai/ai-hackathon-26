"""Nudge state in ~/.flux/nudges.json (outside git; FLUX_NUDGES_FILE overrides): config, shown, dismissed, snoozed."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from .rules import nudges, Nudge


def path() -> Path:
    return Path(os.environ.get("FLUX_NUDGES_FILE") or "~/.flux/nudges.json").expanduser()


def enabled() -> bool:
    return os.environ.get("FLUX_NUDGES") == "1"


def load(p: Path | None = None) -> dict:
    try:
        d = json.loads((p or path()).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save(state: dict, p: Path | None = None) -> None:
    p = p or path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True))
    tmp.replace(p)


def record_shown(state: dict, ns, now: datetime) -> list:
    """Mark nudges as shown; returns the ones not shown before (what to notify). Prunes old ids."""
    shown = state.setdefault("shown", {})
    new = [n for n in ns if n.id not in shown]
    for n in new:
        shown[n.id] = now.isoformat(timespec="seconds")
    cut = now - timedelta(days=30)
    for k in [k for k, t in shown.items() if datetime.fromisoformat(t) < cut]:
        del shown[k]
    return new


def dismiss(state: dict, nid: str) -> None:
    ids = state.setdefault("dismissed", [])
    if nid not in ids:
        ids.append(nid)


def snooze(state: dict, nid: str, now: datetime, minutes: int = 60) -> None:
    state.setdefault("snoozed", {})[nid] = (now + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def notify(n: Nudge, run=subprocess.run) -> None:
    """macOS notification through osascript, text passed as arguments (never spliced into the script)."""
    script = "on run argv\ndisplay notification (item 1 of argv) with title \"Flux\"\nend run"
    run(["osascript", "-e", script, n.text], capture_output=True, timeout=10)


def poll(now: datetime, bank: list, events: list, p: Path | None = None, osascript: bool = False,
         run=subprocess.run) -> list:
    """One poll: compute, record what's new, optionally notify. Returns every live nudge (dicts)."""
    state = load(p)
    ns = nudges(now, bank, events, state, state.get("config"))
    new = record_shown(state, ns, now)
    if new:
        save(state, p)
        if osascript:
            for n in new:
                notify(n, run)
    return [n.to_dict() for n in ns]
