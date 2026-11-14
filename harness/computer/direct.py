"""Direct commands: open an app, find a file, open a file. No screen reading.

All subprocess calls pass arguments as a list, never through a shell string.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

MAX_RESULTS = 10


def open_app(name: str) -> tuple[bool, str]:
    """Launch an app with ``open -a``. Returns (ok, error_message)."""
    try:
        result = subprocess.run(
            ["open", "-a", name], capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, " ".join(str(exc).split())[:80]
    if result.returncode != 0:
        message = " ".join((result.stderr or "").split())[:80] or f"exit {result.returncode}"
        return False, message
    return True, ""


def find_files(query: str, home: Path | None = None) -> list[str]:
    """Spotlight search by file name, limited to the home folder.

    Returns at most MAX_RESULTS paths; hidden and Library paths are dropped.
    """
    root = Path(home) if home is not None else Path.home()
    result = subprocess.run(
        ["mdfind", "-name", query, "-onlyin", str(root)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    paths = []
    for line in result.stdout.splitlines():
        path = line.strip()
        if path and not _is_hidden_or_library(path):
            paths.append(path)
        if len(paths) >= MAX_RESULTS:
            break
    return paths


def open_path(path: str) -> tuple[bool, str]:
    """Open a file with its default app. Returns (ok, error_message)."""
    try:
        result = subprocess.run(
            ["open", path], capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, " ".join(str(exc).split())[:80]
    if result.returncode != 0:
        message = " ".join((result.stderr or "").split())[:80] or f"exit {result.returncode}"
        return False, message
    return True, ""


def _is_hidden_or_library(path: str) -> bool:
    return any(part.startswith(".") or part == "Library" for part in Path(path).parts)
