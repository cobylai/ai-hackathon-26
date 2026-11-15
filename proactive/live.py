"""Live wiring: read the bank and Calendar, poll once, and a background poller on the vendored scheduler."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from . import state


def poll_once(now_fn=datetime.now, entries_fn=None, events_fn=None, p: Path | None = None) -> list:
    from bank import store
    now = now_fn()
    try:
        evs = (events_fn or _events)(now)
    except Exception:  # Calendar unreadable: the bank rules still run
        evs = []
    return state.poll(now, (entries_fn or store.all_entries)(), evs, p,
                      osascript=os.environ.get("FLUX_NUDGES_OSASCRIPT") == "1")


def _events(now):
    import applecal
    return applecal.events(now.date(), now.date())


TASK = "flux-nudge-poll"


def start_poller(interval: int = 60, db: Path | None = None, runner=None):
    """Every `interval` seconds run poll_once on the OpenJarvis TaskScheduler (interval task, SQLite store
    in ~/.flux/scheduler.db). Returns the scheduler (call .stop()). Only started when FLUX_NUDGES=1."""
    from third_party.openjarvis_scheduler import TaskScheduler, SchedulerStore
    db = db or Path("~/.flux/scheduler.db").expanduser()
    db.parent.mkdir(parents=True, exist_ok=True)
    sch = TaskScheduler(SchedulerStore(db), runner or (lambda task: f"{len(poll_once())} nudges"),
                        poll_interval=max(1, min(interval, 60)))
    for t in sch.list_tasks():
        if t.prompt == TASK:
            sch.cancel_task(t.id)
    sch.create_task(TASK, "interval", str(interval))
    sch.start()
    return sch
