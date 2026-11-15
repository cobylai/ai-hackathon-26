"""Safety policy for computer control: allowlist, blocklist, confirms, log, stop.

State lives in ``~/.harness/`` (overridable for tests):

- ``policy.json``  -- ``allow_apps``, ``block_apps``, ``confirm_words``
- ``actions.log``  -- one line per checked action
- ``STOP``         -- if present, every computer tool returns ``ERR stopped by user``

``block_apps`` always wins over ``allow_apps``; editing ``policy.json`` cannot
unblock a blocked app.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from harness import config

ALLOW = "ALLOW"
CONFIRM = "CONFIRM"
DENY = "DENY"

STOPPED_MESSAGE = "ERR stopped by user"

DEFAULT_POLICY = {
    "allow_apps": ["Finder", "TextEdit", "Notes", "Calendar", "Preview", "Calculator"],
    "block_apps": [
        "System Settings",
        "System Preferences",
        "Keychain Access",
        "Terminal",
        "iTerm",
        "1Password",
        "Bitwarden",
        "Dashlane",
        "Chase",
        "Bank of America",
        "Wells Fargo",
    ],
    "confirm_words": ["delete", "remove", "send", "pay", "buy", "erase", "empty trash"],
}


def _home(home: Path | None) -> Path:
    return Path(home) if home is not None else config.HOME_DIR


def load_policy(home: Path | None = None) -> dict:
    """Read policy.json, writing defaults first if it does not exist."""
    root = _home(home)
    path = root / "policy.json"
    if not path.exists():
        root.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULT_POLICY, indent=2) + "\n")
        return dict(DEFAULT_POLICY)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return dict(DEFAULT_POLICY)
    merged = dict(DEFAULT_POLICY)
    for key in DEFAULT_POLICY:
        if isinstance(data.get(key), list) and all(isinstance(x, str) for x in data[key]):
            merged[key] = data[key]
    return merged


def stopped(home: Path | None = None) -> bool:
    """True when the user has dropped the STOP file."""
    return (_home(home) / "STOP").exists()


def _norm(names: list[str]) -> set[str]:
    return {n.strip().lower() for n in names}


def _has_confirm_word(text: str, words: list[str]) -> bool:
    text = text.lower()
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def verdict(app: str, action: str, label: str = "", home: Path | None = None) -> str:
    """Decide ALLOW, CONFIRM or DENY for an action. Pure; logs nothing.

    Order: block list first (cannot be overridden), then the allow list, then
    confirm words in the action or label. Anything not allowed is denied, so
    a confirm token can never reach an app off the allow list.
    """
    policy = load_policy(home)
    blocked = _norm(policy["block_apps"])
    allowed = _norm(policy["allow_apps"])
    name = app.strip().lower()

    if name in blocked:
        return DENY
    if name not in allowed:
        return DENY
    if _has_confirm_word(f"{action} {label}", policy["confirm_words"]):
        return CONFIRM
    return ALLOW


def check(app: str, action: str, label: str = "", home: Path | None = None) -> str:
    """verdict() plus one line in actions.log."""
    result = verdict(app, action, label, home)
    log_action(app, action, label, result, home)
    return result


def log_action(
    app: str, action: str, label: str, verdict: str, home: Path | None = None
) -> None:
    """Append one line to actions.log: time, verdict, app, action, label."""
    root = _home(home)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fields = [stamp, verdict, app, action, label]
    line = "\t".join(" ".join(f.split()) for f in fields)
    with (root / "actions.log").open("a") as fh:
        fh.write(line + "\n")


# --- one-time confirmation tokens --------------------------------------------
# Seam with the reasoning layer: a tool answers CONFIRM <what> with a token;
# the user is asked out of band; the tool is called again with that token.
# Tokens live in ~/.harness/confirms.json so a replay works across processes,
# and each is deleted on first use (one-time), whether or not it matched.

CONFIRMED = "CONFIRMED"  # actions.log verdict for a token-authorized replay


def _key(app: str, action: str, label: str) -> str:
    return "\t".join((app.strip().lower(), action.strip(), label.strip()))


def _tokens_path(home: Path | None) -> Path:
    return _home(home) / "confirms.json"


def _read_tokens(home: Path | None) -> dict:
    try:
        data = json.loads(_tokens_path(home).read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def issue_token(app: str, action: str, label: str, home: Path | None = None) -> str:
    """Mint a one-time token that authorizes replaying this exact action."""
    token = secrets.token_hex(3)  # 6 hex chars; a small model can repeat it
    tokens = _read_tokens(home)
    tokens[token] = _key(app, action, label)
    path = _tokens_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tokens, indent=2) + "\n")
    return token


def consume_token(
    app: str, action: str, label: str, token: str, home: Path | None = None
) -> bool:
    """True once, if token exists and matches this exact app/action/label."""
    if not token:
        return False
    tokens = _read_tokens(home)
    key = tokens.pop(token.strip(), None)
    _tokens_path(home).write_text(json.dumps(tokens, indent=2) + "\n")
    return key is not None and key == _key(app, action, label)
