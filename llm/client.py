"""The single path for every LLM call in Flux: the local Bonsai 2 server.

    from llm.client import complete, complete_json
    text = complete("Summarise this.", system="Be brief.")
    data = complete_json("Extract ...", json_schema_hint='{"sender": str}')

Only talks to BONSAI_BASE_URL (default http://localhost:8080/v1). No other
provider and no fallback. Standard library only, apart from the optional
`tokenizers` package used for offline token counting.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse

from . import config, tokens
from .tokens import BudgetError  # re-exported for callers

__all__ = ["complete", "complete_json", "chat", "Reply", "BonsaiError",
           "ServerDown", "BudgetError", "loaded_model", "server_up"]

START_HINT = ("Start it with:  scripts/serve_bonsai.sh {size}   "
              "(or BONSAI_SIZE={size} scripts/serve_bonsai.sh)")


def server_up(timeout: float = 0.6) -> bool:
    """True when the Bonsai server answers /models. Used by the window's status line."""
    try:
        with urllib.request.urlopen(config.BASE_URL + "/models", timeout=timeout) as r:
            return 200 <= getattr(r, "status", 200) < 300
    except Exception:  # down, slow, wrong port: not up
        return False


class BonsaiError(RuntimeError):
    pass


class ServerDown(BonsaiError):
    pass


def _check_local(url: str) -> None:
    host = urlparse(url).hostname
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise BonsaiError(f"BONSAI_BASE_URL must point at localhost, got {url!r}.")


def _request(method: str, path: str, body: dict | None = None) -> dict:
    url = config.BASE_URL + path
    _check_local(url)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=config.TIMEOUT_S) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise BonsaiError(f"Bonsai server error {e.code} on {path}: "
                          f"{e.read()[:500].decode(errors='replace')}") from e
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise ServerDown(f"Bonsai server not reachable at {config.BASE_URL} ({e}). "
                         + START_HINT.format(size=config.BONSAI_SIZE)) from e


_model_cache: str | None = None


def loaded_model(refresh: bool = False) -> str:
    """Model id (absolute path) of the loaded entry, checked against BONSAI_SIZE."""
    global _model_cache
    if _model_cache and not refresh:
        return _model_cache
    models = _request("GET", "/models").get("data", [])
    loaded = [m["id"] for m in models if m.get("loaded")]
    if not loaded:
        raise ServerDown("Bonsai server is up but no model is loaded yet (still "
                         "loading?). " + START_HINT.format(size=config.BONSAI_SIZE))
    mid = loaded[0]
    want = f"bonsai2-{config.BONSAI_SIZE.lower()}-mlx"
    if want not in mid:
        raise BonsaiError(f"Server has {mid} loaded but BONSAI_SIZE={config.BONSAI_SIZE}. "
                          "Restart the server with the size you want, or change BONSAI_SIZE.")
    _model_cache = mid
    return mid


@dataclass
class Reply:
    text: str
    prompt_tokens: int | None = None       # as reported by the server
    completion_tokens: int | None = None
    estimated_prompt_tokens: int = 0       # our offline count
    seconds: float = 0.0
    finish_reason: str | None = None
    reasoning: str | None = None
    raw: dict = field(default_factory=dict, repr=False)


_THINK = re.compile(r"<think>(.*?)</think>", re.S)


def _split_thinking(text: str) -> tuple[str, str | None]:
    m = _THINK.search(text)
    if m:
        return _THINK.sub("", text).strip(), m.group(1).strip()
    if "</think>" in text:  # template opened the block for us
        head, _, tail = text.partition("</think>")
        return tail.strip(), head.strip()
    return text.strip(), None


def chat(messages: list[dict], max_tokens: int | None = None,
         thinking: bool = False, sampling: dict | None = None) -> Reply:
    """Send a full message list. Checks the 32k budget first; never truncates.

    `sampling` overrides preset keys for this call only, e.g. {"temperature": 0.2}.
    """
    if max_tokens is None:
        max_tokens = config.THINKING_MAX_TOKENS if thinking else config.DEFAULT_MAX_TOKENS
    est = tokens.check_budget(messages, max_tokens)
    body = {
        "model": loaded_model(),
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": thinking},
        **config.PRESETS["thinking" if thinking else "non_thinking"],
        **(sampling or {}),
    }
    t0 = time.monotonic()
    r = _request("POST", "/chat/completions", body)
    dt = time.monotonic() - t0
    choice = r["choices"][0]
    msg = choice.get("message", {})
    text, reasoning = _split_thinking(msg.get("content") or "")
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or reasoning
    usage = r.get("usage") or {}
    return Reply(text=text, prompt_tokens=usage.get("prompt_tokens"),
                 completion_tokens=usage.get("completion_tokens"),
                 estimated_prompt_tokens=est, seconds=dt,
                 finish_reason=choice.get("finish_reason"), reasoning=reasoning, raw=r)


def _messages(prompt: str, system: str | None) -> list[dict]:
    msgs = [{"role": "system", "content": system}] if system else []
    msgs.append({"role": "user", "content": prompt})
    return msgs


def complete(prompt: str, system: str | None = None, max_tokens: int | None = None,
             json_schema_hint: str | None = None, thinking: bool = False,
             sampling: dict | None = None) -> str:
    """One prompt in, reply text out."""
    if json_schema_hint:
        prompt = (f"{prompt}\n\nReply with only a JSON object, no prose and no code "
                  f"fence, matching this shape:\n{json_schema_hint}")
    return chat(_messages(prompt, system), max_tokens, thinking, sampling).text


class JSONReplyError(BonsaiError):
    pass


def parse_json(text: str):
    """Parse a model reply as JSON, tolerating code fences and leading prose."""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    for open_, close in (("{", "}"), ("[", "]")):
        i, j = t.find(open_), t.rfind(close)
        if i != -1 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except json.JSONDecodeError:
                continue
    raise JSONReplyError(f"Not valid JSON: {text[:300]!r}")


def complete_json(prompt: str, system: str | None = None, max_tokens: int | None = None,
                  json_schema_hint: str | None = None, thinking: bool = False,
                  _stats: dict | None = None, sampling: dict | None = None):
    """Like complete() but returns parsed JSON. Retries once on invalid JSON.

    Pass a dict as _stats to learn whether the first try was valid
    (_stats["first_try_valid"]) and how many calls were made.
    """
    hint = json_schema_hint or "a JSON object"
    msgs = _messages(
        f"{prompt}\n\nReply with only a JSON object, no prose and no code fence, "
        f"matching this shape:\n{hint}", system)
    reply = chat(msgs, max_tokens, thinking, sampling)
    stats = _stats if _stats is not None else {}
    stats["calls"] = 1
    try:
        out = parse_json(reply.text)
        stats["first_try_valid"] = True
        return out
    except JSONReplyError:
        stats["first_try_valid"] = False
    msgs += [{"role": "assistant", "content": reply.text},
             {"role": "user", "content": "That was not valid JSON. Reply again with "
              "only the JSON object, nothing else."}]
    reply = chat(msgs, max_tokens, thinking, sampling)
    stats["calls"] = 2
    return parse_json(reply.text)
