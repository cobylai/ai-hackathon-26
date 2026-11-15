"""One way to ask a model: an OpenAI-compatible chat completions endpoint.

`ask` is the only function the rest of the harness uses, so swapping the local
model for another runtime is a config change (`LLM_BASE_URL`, `LLM_MODEL`),
not a code change. Replies are plain strings; when `choices` is given the
request asks for a JSON enum and the reply is mapped back to one of them.
"""

from __future__ import annotations

import json
import os

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8080/v1"
DEFAULT_MODEL = "local"
TIMEOUT_SECONDS = 120.0

SYSTEM = "You are a small, careful assistant. Answer only what is asked, briefly."

# Token counts reported by the server for the most recent successful call.
last_usage: dict[str, int] = {}


def base_url() -> str:
    return os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def model() -> str:
    return os.environ.get("LLM_MODEL", DEFAULT_MODEL)


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
    """Send one user turn; return the reply, mapped onto ``choices`` if given.

    Exact token counts for the call are left in ``last_usage`` (empty on failure).
    """
    global last_usage
    last_usage = {}
    payload: dict = {
        "model": model(),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    # Reasoning models (qwen3 and friends) spend ``max_tokens`` on hidden thinking
    # and return empty content. ``LLM_REASONING_EFFORT=none`` turns that off.
    effort = os.environ.get("LLM_REASONING_EFFORT")
    if effort:
        payload["reasoning_effort"] = effort
    if choices:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "choice",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"choice": {"type": "string", "enum": list(choices)}},
                    "required": ["choice"],
                    "additionalProperties": False,
                },
            },
        }
    try:
        response = httpx.post(
            f"{base_url()}/chat/completions", json=payload, timeout=TIMEOUT_SECONDS
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
    except Exception:
        # The caller decides what an empty answer means; a dead model must not crash a tool.
        return ""
    if usage:
        last_usage = {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
        }
    return _coerce(str(content or ""), choices)


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
