"""C7 live check: five small computer-control jobs against real apps.

Scope (per task authorization): TextEdit only from the app allowlist, plus a
read-only Spotlight search. The only text typed is SENTENCE, into a fresh
TextEdit document that is closed WITHOUT saving at the end.

Run:  uv run python scripts/eval_computer.py
Prints a markdown table: calls made, characters returned to the model, time,
and outcome per job.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.computer import tools, ui

SENTENCE = "The quick brown fox jumps over the lazy dog."
FIND_QUERY = "harness"


def _osascript(source: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", source], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _document_names() -> set[str]:
    out = _osascript('tell application "TextEdit" to get name of every document')
    return {n.strip() for n in out.split(",")} if out else set()


def _wait_front(name: str, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        front = ui._front_app()
        if front and front[1] == name:
            return True
        time.sleep(0.5)
    return False


def job_open_app() -> tuple[int, int, bool, list[str]]:
    """Job 1: open TextEdit and make a new document. One call, no screen read."""
    result = tools.app_open("TextEdit")
    _osascript(
        'tell application "TextEdit"\nactivate\nmake new document\nend tell'
    )
    front = _wait_front("TextEdit")
    ok = result.startswith("OK") and front
    return 1, len(result), ok, [result, f"front app is TextEdit: {front}"]


def job_list_controls() -> tuple[int, int, bool, list[str]]:
    """Job 2: what is on my TextEdit window."""
    result = ui.list_controls()
    n = len(ui._last)
    ok = result.startswith("OK TextEdit") and n > 0
    return 1, len(result), ok, [result.splitlines()[0], f"({n} numbered controls)"]


def job_type_sentence() -> tuple[int, int, bool, list[str]]:
    """Job 3: add a note saying the test sentence (ui, then ui_type)."""
    listing = ui.list_controls()
    target = next(
        (i for i, c in enumerate(ui._last, 1) if c["kind"] == "textarea"), None
    )
    if target is None:
        return 2, len(listing), False, [listing.splitlines()[0], "no textarea found"]
    result = ui.ui_type(target, SENTENCE)
    return 2, len(listing) + len(result), result.startswith("OK typed"), [
        f"ui -> textarea is #{target}",
        result,
    ]


def job_read_back() -> tuple[int, int, bool, list[str]]:
    """Job 4: read the note back through the numbered-controls tool."""
    result = ui.list_controls("quick")
    ok = SENTENCE in result
    return 1, len(result), ok, [result.splitlines()[0], result.splitlines()[-1]]


def job_find_files() -> tuple[int, int, bool, list[str]]:
    """Job 5: find files by name (Spotlight, read-only; nothing is opened)."""
    result = tools.file_find(FIND_QUERY)
    ok = result.startswith("OK") and "\n1. " in f"\n{result}"
    return 1, len(result), ok, [result.splitlines()[0]]


JOBS = [
    ("open TextEdit, new document", job_open_app),
    ("what is on my TextEdit window", job_list_controls),
    ("add a note saying the test sentence", job_type_sentence),
    ("read the note back", job_read_back),
    (f"find files named '{FIND_QUERY}' (read-only)", job_find_files),
]


def main() -> int:
    before = _document_names()
    rows = []
    for name, fn in JOBS:
        start = time.time()
        try:
            calls, chars, ok, details = fn()
        except Exception as exc:  # a live job must not kill the eval
            calls, chars, ok, details = 0, 0, False, [f"exception: {exc}"]
        seconds = time.time() - start
        rows.append((name, calls, chars, seconds, "pass" if ok else "FAIL"))
        print(f"[{rows[-1][4]}] {name} ({seconds:.1f}s)")
        for line in details:
            print(f"       {line}")
    # close every document this run created, WITHOUT saving
    for name in _document_names() - before:
        _osascript(
            f'tell application "TextEdit" to close document "{name}" saving no'
        )
    print()
    print("| job | calls | chars to model | time (s) | outcome |")
    print("|---|---|---|---|---|")
    for name, calls, chars, seconds, outcome in rows:
        print(f"| {name} | {calls} | {chars} | {seconds:.1f} | {outcome} |")
    return 0 if all(r[4] == "pass" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
