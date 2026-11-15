"""Push-to-talk voice input: speak a question, get it back as text.

Starts the long-running Swift program voice/swift/.build/release/argmax-voice (Argmax
speech-to-text, model loaded once from disk, no network needed) and talks to it over
stdin/stdout. Needs ARGMAX_API_KEY in the environment.

    from voice.listen import Voice
    voice = Voice()            # waits until the model is loaded
    text = voice.listen()      # records until wait_for_stop() returns (default: Enter)

Try it by hand:  python -m voice.listen   (Enter to start, Enter to stop)
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

BINARY = Path(__file__).resolve().parent / "swift" / ".build" / "release" / "argmax-voice"
READY_TIMEOUT = 600.0  # the first launch compiles the model for the Neural Engine (~4 min)
REPLY_TIMEOUT = 60.0


class VoiceError(RuntimeError):
    """The Swift side reported an error, exited, or went silent."""


class Voice:
    def __init__(self, binary: Path | str = BINARY, ready_timeout: float = READY_TIMEOUT):
        if not Path(binary).exists():
            raise VoiceError(f"{binary} not found: run `swift build -c release` in voice/swift")
        if not os.environ.get("ARGMAX_API_KEY", "").startswith("ax_"):
            raise VoiceError("ARGMAX_API_KEY is not set (expected an ax_ key)")
        self._proc = subprocess.Popen(
            [str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1
        )
        self._lines: queue.Queue[dict | None] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self._expect("ready", ready_timeout)

    def listen(self, wait_for_stop: Callable[[], object] = input) -> str:
        """Record from the microphone until wait_for_stop() returns, then return the text."""
        self._send("start")
        self._expect("recording", REPLY_TIMEOUT)
        wait_for_stop()
        self._send("stop")
        return self._expect("text", REPLY_TIMEOUT)["text"]

    def transcribe_file(self, path: str | Path) -> str:
        """Transcribe a WAV file (for tests without a microphone)."""
        self._send(f"file {Path(path).resolve()}")
        return self._expect("text", REPLY_TIMEOUT)["text"]

    def close(self) -> None:
        if self._proc.poll() is None:
            try:
                self._send("quit")
                self._proc.wait(timeout=5)
            except (VoiceError, subprocess.TimeoutExpired):
                self._proc.kill()

    def __enter__(self) -> "Voice":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- internals

    def _read(self) -> None:
        for line in self._proc.stdout:
            line = line.strip()
            if line:
                try:
                    self._lines.put(json.loads(line))
                except json.JSONDecodeError:
                    self._lines.put({"event": "error", "message": f"bad line from argmax-voice: {line}"})
        self._lines.put(None)  # process exited

    def _send(self, command: str) -> None:
        if self._proc.poll() is not None:
            raise VoiceError(f"argmax-voice exited (code {self._proc.returncode})")
        self._proc.stdin.write(command + "\n")
        self._proc.stdin.flush()

    def _expect(self, event: str, timeout: float) -> dict:
        try:
            msg = self._lines.get(timeout=timeout)
        except queue.Empty:
            raise VoiceError(f"no '{event}' from argmax-voice after {timeout:.0f} s") from None
        if msg is None:
            raise VoiceError(f"argmax-voice exited (code {self._proc.wait()})")
        if msg.get("event") == "error":
            raise VoiceError(msg.get("message", "unknown error"))
        if msg.get("event") != event:
            raise VoiceError(f"expected '{event}', got {msg}")
        return msg


def main() -> None:
    t0 = time.monotonic()
    print("Loading the speech model...")
    with Voice() as voice:
        print(f"Ready in {time.monotonic() - t0:.1f} s. Press Enter to start talking, Enter again to stop. Ctrl+C quits.")
        stopped = {}

        def wait_for_stop() -> None:
            input("  recording... press Enter to stop ")
            stopped["at"] = time.monotonic()

        while True:
            try:
                input("\nPress Enter to talk ")
                text = voice.listen(wait_for_stop)
                print(f"  text: {text}")
                print(f"  stop to text: {time.monotonic() - stopped['at']:.2f} s")
            except VoiceError as e:
                print(f"  error: {e}")
            except (KeyboardInterrupt, EOFError):
                print()
                break


if __name__ == "__main__":
    main()
