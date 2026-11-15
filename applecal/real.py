"""Read the user's real Apple Calendar through EventKit (FLUX_CALENDARS=all). Read-only.

EventKit expands repeating events into one occurrence per day inside the window, and keeps
each event's own time zone, which AppleScript cannot. A small Swift helper (eventkit_read.swift)
is compiled once into ~/.flux/bin and run as a subprocess; it prints JSON. Tests mock that call.

Which calendars count is set by ~/.flux/calendars.json (outside git; FLUX_CALENDARS_CONFIG
overrides the path):
    {"allow": ["Work", "Home"],        # only these (case-insensitive); empty/absent = all
     "deny": ["Spam"],                 # never these; deny beats allow
     "include_subscribed": false,      # holiday / subscribed calendars, default off
     "include_birthdays": false}       # the Birthdays calendar, default off
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time as _time
from datetime import date, datetime, time, timedelta
from pathlib import Path

SRC = Path(__file__).with_name("eventkit_read.swift")
EK_TIMEOUT = 120  # the first run may wait on the macOS permission prompt
_LOCK = threading.Lock()


class AccessDenied(RuntimeError):
    pass


def home() -> Path:
    return Path(os.environ.get("FLUX_HOME") or Path.home() / ".flux")


def config_path() -> Path:
    return Path(os.environ.get("FLUX_CALENDARS_CONFIG") or home() / "calendars.json")


def load_config() -> dict:
    try:
        raw = json.loads(config_path().read_text())
    except (OSError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    names = lambda k: {str(x).strip().lower() for x in raw.get(k) or [] if str(x).strip()}
    return {"allow": names("allow"), "deny": names("deny"),
            "include_subscribed": bool(raw.get("include_subscribed", False)),
            "include_birthdays": bool(raw.get("include_birthdays", False))}


def wanted(name: str, kind: str, cfg: dict) -> bool:
    n = (name or "").strip().lower()
    if n in cfg["deny"]:
        return False
    if cfg["allow"]:
        return n in cfg["allow"]
    if kind == "birthday":
        return cfg["include_birthdays"]
    if kind == "subscription" or "holiday" in n:
        return cfg["include_subscribed"]
    return True


def helper() -> Path:
    """The compiled helper, rebuilt when the Swift source changes."""
    tag = hashlib.sha1(SRC.read_bytes()).hexdigest()[:10]
    exe = home() / "bin" / f"flux-eventkit-{tag}"
    if not exe.exists():
        exe.parent.mkdir(parents=True, exist_ok=True)
        p = subprocess.run(["swiftc", "-O", str(SRC), "-o", str(exe)], capture_output=True,
                           text=True, timeout=300)
        if p.returncode != 0:
            raise OSError("could not compile the EventKit helper: " + p.stderr.strip()[-200:])
    return exe


def _epoch(d: datetime) -> str:
    return str(int(d.timestamp()))


def run_helper(lo: datetime, hi: datetime) -> dict:
    exe = helper()
    p = subprocess.run([str(exe), _epoch(lo), _epoch(hi)], capture_output=True, text=True,
                       timeout=EK_TIMEOUT)
    if p.returncode != 0:
        raise OSError(p.stderr.strip() or "EventKit helper failed")
    return json.loads(p.stdout)


def convert(rec: dict) -> dict:
    """One EventKit record -> an applecal event dict (naive local wall-clock times).
    Timed events are converted from their absolute instant to this Mac's time zone.
    All-day events run from local midnight to the midnight after their last day
    (EventKit ends them at 23:59:59)."""
    s = datetime.fromtimestamp(float(rec["start"]))
    e = datetime.fromtimestamp(float(rec["end"]))
    all_day = bool(rec.get("all_day"))
    if all_day:
        s = datetime.combine(s.date(), time.min)
        e = datetime.combine((e - timedelta(seconds=1)).date() + timedelta(days=1), time.min)
        if e <= s:
            e = s + timedelta(days=1)
    return {"title": (rec.get("title") or "").strip(), "start": s, "end": e,
            "location": (rec.get("location") or "").strip(), "all_day": all_day,
            "calendar": rec.get("calendar") or ""}


def filter_events(payload: dict, cfg: dict) -> list[dict]:
    if payload.get("status") == "denied":
        raise AccessDenied
    evs = [convert(r) for r in payload.get("events") or []
           if wanted(r.get("calendar") or "", r.get("type") or "", cfg)]
    return sorted(evs, key=lambda x: (x["start"], x["title"]))


_CACHE: dict[tuple, tuple[float, list[dict]]] = {}


def read(start: date, end: date, ttl: float = 60.0) -> list[dict]:
    """Events (every occurrence) overlapping the days start..end, both included."""
    lo = datetime.combine(start, time.min)
    hi = datetime.combine(end + timedelta(days=1), time.min)
    key = (lo, hi, repr(sorted((k, sorted(v) if isinstance(v, set) else v)
                               for k, v in load_config().items())))
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and _time.monotonic() - hit[0] < ttl:
            return hit[1]
        evs = filter_events(run_helper(lo, hi), load_config())
        evs = [e for e in evs if e["start"] < hi and (e["end"] > lo or e["start"] >= lo)]
        _CACHE[key] = (_time.monotonic(), evs)
        return evs
