"""Voice for the chat loop and the window: start argmax-voice once, or say why not.

Uses voice/listen.py as it is. FLUX_VOICE_BIN points at another built argmax-voice
binary (e.g. one built in a different checkout); default is voice/swift/.build/release.
"""
from __future__ import annotations

import os
import threading


def start_voice():
    """(Voice, None) when voice works, else (None, reason)."""
    try:
        from voice.listen import BINARY, Voice
        return Voice((os.environ.get("FLUX_VOICE_BIN") or os.environ.get("MUSE_VOICE_BIN")) or BINARY), None
    except Exception as e:  # VoiceError, missing key or binary, mic denied...
        return None, str(e) or type(e).__name__


class HoldToTalk:
    """start() begins recording and returns at once; stop() ends it and returns the text.

    For a button: the recording runs on a worker thread that waits on an Event.
    """

    def __init__(self, voice):
        self.voice = voice
        self._stop = None
        self._thread = None
        self._result = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop, self._result = threading.Event(), {}
        started = threading.Event()

        def run():
            try:
                self._result["text"] = self.voice.listen(
                    wait_for_stop=lambda: (started.set(), self._stop.wait()))
            except Exception as e:
                self._result["error"] = str(e) or type(e).__name__
            started.set()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        started.wait(timeout=60)  # recording has begun (or failed)

    def stop(self) -> dict:
        if not self._thread:
            return {"error": "not recording"}
        self._stop.set()
        self._thread.join(timeout=90)
        self._thread = None
        return dict(self._result)
