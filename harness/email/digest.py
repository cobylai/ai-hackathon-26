"""A short digest of questions and dates across the inbox.

Read-only: it searches recent mail, opens the newest threads the fast way and
prints the lines ``email_asks`` would show, grouped by thread. Nothing is
drafted or sent, so it is safe to run unattended (the plan's daily digest).
"""

from __future__ import annotations

from harness.email.asks import cap_lines, scan

HINT = "[more: raise days or limit]"
LINE_CHARS = 200


def build(days: int = 1, limit: int = 8) -> str:
    """``OK n threads, m asks | newer_than:Nd`` plus one block per thread."""
    status, entries = scan(days=days, threads=limit)
    if not status.startswith("OK"):
        return status

    total = sum(len(sentences) for _, sentences in entries)
    head = f"OK {len(entries)} threads, {total} asks | newer_than:{days}d"
    lines: list[str] = []
    for row, sentences in entries:
        if not sentences:
            continue
        lines.append(f"{row.n}. {row.subject[:60]} ({len(sentences)})")
        lines.extend(f"   - {sentence[:LINE_CHARS]}" for sentence in sentences)
    return cap_lines(head, lines, hint=HINT)
