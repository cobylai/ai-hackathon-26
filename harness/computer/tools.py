"""The computer-control tools the model sees, all returning short plain text."""

from __future__ import annotations

from harness import config
from harness.computer import direct, policy

# file_open(n) refers to the last file_find listing.
_last_files: list[str] = []


def _cap(text: str) -> str:
    text = text.strip()
    if len(text) <= config.MAX_CHARS:
        return text
    room = config.MAX_CHARS - len("\n[end]") - 1
    body = text[:room].rstrip()
    if "\n" in body:
        body = body.rsplit("\n", 1)[0]
    return f"{body}\n[end]"


def _verdict_line(verdict: str, what: str) -> str | None:
    """None if the action may run, else the status line to return."""
    if verdict == policy.DENY:
        return f"ERR not allowed: {what}"
    if verdict == policy.CONFIRM:
        return f"CONFIRM {what}"
    return None


def app_open(name: str) -> str:
    """Open an app by name, after the policy check."""
    if policy.stopped():
        return policy.STOPPED_MESSAGE
    name = name.strip()
    verdict = policy.check(name, "open")
    if (line := _verdict_line(verdict, f"open app '{name}'")) is not None:
        return line
    ok, message = direct.open_app(name)
    if not ok:
        return _cap(f"ERR app_open '{name}' failed | {message}")
    return f"OK opened {name}"


def file_find(query: str) -> str:
    """Find files by name (Spotlight, home folder only); numbered paths."""
    global _last_files
    if policy.stopped():
        return policy.STOPPED_MESSAGE
    query = query.strip()
    if not query:
        return "ERR file_find needs a search word"
    policy.log_action("Finder", "file_find", query, policy.ALLOW)
    try:
        _last_files = direct.find_files(query)
    except Exception as exc:
        _last_files = []
        message = " ".join(str(exc).split())[:80]
        return _cap(f"ERR file_find '{query}' failed | {message}")
    if not _last_files:
        return f"OK file_find '{query}' | 0 results"
    listing = "\n".join(f"{i}. {p}" for i, p in enumerate(_last_files, 1))
    return _cap(f"OK file_find '{query}' | {len(_last_files)} results\n{listing}")


def file_open(n: int) -> str:
    """Open result N from the last file_find list."""
    if policy.stopped():
        return policy.STOPPED_MESSAGE
    n = int(n)
    if not _last_files or not 1 <= n <= len(_last_files):
        return f"ERR no file {n}; call file_find first"
    path = _last_files[n - 1]
    verdict = policy.check("Finder", "file_open", path)
    if (line := _verdict_line(verdict, f"open file '{path}'")) is not None:
        return line
    ok, message = direct.open_path(path)
    if not ok:
        return _cap(f"ERR file_open {n} failed | {message}")
    return f"OK opened {n}. {path}"
