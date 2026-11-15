"""Spoken answers with the Mac's built-in `say` (local, works with the network off).

    sp = Speaker()
    sp.speak(answer.text)   # stops anything still speaking, then reads this answer
    sp.stop()               # when the user starts talking, or asks something new

The Source line is not read. Off by default: the chat loop has --speak, the window has a Speak switch.
"""
from __future__ import annotations

import re
import shutil
import subprocess

_SOURCE = re.compile(r"^\s*Source:", re.I)


def speakable(text: str) -> str:
    """The answer as it should be read: no Source line, no list dashes, rows as sentences."""
    out = []
    for line in (text or "").splitlines():
        if not line.strip() or _SOURCE.match(line):
            continue
        line = re.sub(r"^\s*[-•]\s+", "", line).strip()
        line = re.sub(r"\s{2,}", ", ", line)  # "9am  Submit the quiz" -> "9am, Submit the quiz"
        line = line.replace("–", " to ")
        out.append(line if re.search(r"[.!?:]$", line) else line + ".")
    return " ".join(out)


class Speaker:
    def __init__(self, cmd: str | None = None, popen=subprocess.Popen):
        self.cmd = cmd or shutil.which("say") or "/usr/bin/say"
        self._popen = popen
        self._p = None

    def speak(self, text: str) -> bool:
        self.stop()
        words = speakable(text)
        if not words:
            return False
        try:
            self._p = self._popen([self.cmd, "-f", "-"], stdin=subprocess.PIPE,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._p.stdin.write(words.encode())
            self._p.stdin.close()
        except (OSError, ValueError):
            self._p = None
            return False
        return True

    def speaking(self) -> bool:
        return self._p is not None and self._p.poll() is None

    def stop(self) -> None:
        p, self._p = self._p, None
        if p is not None and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=1)
            except subprocess.TimeoutExpired:
                p.kill()
