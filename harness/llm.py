"""One way to ask a model: the project's single Bonsai client, ``llm.client``.

`ask` is the only function the rest of the harness uses. Since integration it
routes every call through ``llm.client.chat`` (localhost Bonsai 2 only, 32k
budget check), so the server address and model size are set in one place:
``BONSAI_BASE_URL`` / ``BONSAI_SIZE`` (see llm/config.py). Replies are plain
strings; when ``choices`` is given the prompt lists them and the reply is
mapped back to one of them.
"""

from __future__ import annotations

import json
import sys

from llm import client

SYSTEM = "You are a small, careful assistant. Answer only what is asked, briefly."

# Token counts reported by the server for the most recent successful call.
last_usage: dict[str, int] = {}


def _coerce(reply: str, choices: list[str] | None) -> str:
    """Map a model reply onto one of ``choices``; '' when it fits none."""
    text = (reply or "").strip()
    if not choices:
        return text
    if text.startswith(("{", '"')):
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                value = value.get("choice", "")
            text = str(value)
        except (json.JSONDecodeError, TypeError):
            pass
    text = text.strip().strip('"').strip()
    lowered = text.lower()
    for choice in choices:
        if lowered == choice.lower():
            return choice
    # Longest first, so "NONE" is not swallowed by "NO".
    for choice in sorted(choices, key=len, reverse=True):
        if choice.lower() in lowered:
            return choice
    return ""


def ask(prompt: str, choices: list[str] | None = None, max_tokens: int = 64) -> str:
    """Ask one user turn; return the reply, mapped onto ``choices`` if given.

    Exact token counts for the call are left in ``last_usage`` (empty on failure).
    """
    global last_usage
    last_usage = {}
    if choices:
        prompt = f"{prompt}\n\nReply with exactly one of: {', '.join(choices)}."
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    try:
        reply = client.chat(messages, max_tokens=max_tokens)
    except Exception as e:
        # The caller decides what an empty answer means; a dead model must not crash
        # a tool. Say why on stderr so a down server is not silent.
        print(f"harness.llm: {type(e).__name__}: {e}", file=sys.stderr)
        return ""
    if reply.prompt_tokens is not None:
        last_usage = {
            "prompt_tokens": int(reply.prompt_tokens or 0),
            "completion_tokens": int(reply.completion_tokens or 0),
        }
    return _coerce(reply.text, choices)


class FakeLLM:
    """Scripted stand-in for tests: returns replies in order, then ``default``."""

    def __init__(self, replies: list[str] | None = None, default: str = "") -> None:
        self.replies = list(replies or [])
        self.default = default
        self.prompts: list[str] = []

    def ask(self, prompt: str, choices: list[str] | None = None, max_tokens: int = 64) -> str:
        self.prompts.append(prompt)
        reply = self.replies.pop(0) if self.replies else self.default
        return _coerce(reply, choices) if choices else (reply or "").strip()
