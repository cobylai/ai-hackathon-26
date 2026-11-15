"""Confirmed send: the ONLY place in Flux that can send an email. Off by default.

The flow follows the interrupt / approve (human-in-the-loop) pattern: ``prepare_send``
pauses and returns a preview plus a one-time token; ``send_draft`` resumes only with an
explicit ``UserApproval`` built from a clicked Send button in the Flux window. Nothing
else (typed or spoken text, a playbook route, model output, text inside an email) can
produce an approval, and every gate fails closed by raising ``SendRefused``:

  1. flag       env FLUX_ALLOW_SEND is exactly "1" (checked by prepare and by send)
  2. flux draft the draft id was made by Flux in this window (``is_flux_draft``)
  3. click      ``approval`` is a ``UserApproval`` from the window's Send click
  4. token      known, unused (single use, consumed on any attempt), under 5 minutes old
  5. content    sha256 of the exact To / Subject / body equals the one the token was issued for
  6. one person exactly one plain address; no Cc / Bcc (there is no parameter for them)
  7. allowlist  the address is in ~/.flux/send_allow.json "allow", or is the user's own
                address ("self" in that file, or FLUX_SELF_ADDRESS); missing file = empty
  8. secrets    no API key, token, private key, SSN or card number in Subject or body
                (patterns from OpenJarvis' scanner, third_party/openjarvis)
  9. rate       at most 3 sends (or unconfirmed attempts) in the last hour, from the log
 10. gmail      a fresh blank "New Message" (a restored draft is refused, draft.py's checks),
                exactly that one recipient after typing, and the typed text read back equal

Every prepare and attempt is appended to ~/.flux/send_log.jsonl (never rewritten): time,
recipient, a short content hash, outcome. Never a subject or a body.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from third_party.openjarvis.scanner import PIIScanner, SecretScanner, ThreatLevel

ALLOW_ENV = "FLUX_ALLOW_SEND"
SELF_ENV = "FLUX_SELF_ADDRESS"
DIR_ENV = "FLUX_SEND_DIR"          # tests point this at a temp folder
TOKEN_SECONDS = 300.0
MAX_PER_HOUR = 3
CLICK_HEADER = "X-Flux-Send-Click"  # a custom header: a cross-site page cannot set it without CORS
CLICK_VALUE = "clicked"
SENT = "OK sent"

ADDRESS = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
_SCANNERS = (SecretScanner(), PIIScanner())


class SendRefused(Exception):
    """A gate said no. ``gate`` names it; nothing was sent."""

    def __init__(self, gate: str, why: str):
        super().__init__(f"{gate}: {why}")
        self.gate, self.why = gate, why


# ---- files outside git --------------------------------------------------------

def home() -> Path:
    return Path(os.environ.get(DIR_ENV) or Path.home() / ".flux")


def allow_path() -> Path:
    return home() / "send_allow.json"


def log_path() -> Path:
    return home() / "send_log.jsonl"


def enabled() -> bool:
    return os.environ.get(ALLOW_ENV) == "1"


def _allow_file() -> dict:
    try:
        got = json.loads(allow_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def own_address() -> str:
    got = os.environ.get(SELF_ENV) or _allow_file().get("self") or ""
    return got.strip().lower() if isinstance(got, str) else ""


def allowed_addresses() -> set[str]:
    got = _allow_file().get("allow") or []
    if not isinstance(got, list):
        return set()
    return {a.strip().lower() for a in got if isinstance(a, str) and a.strip()}


def _log(event: str, to: str, digest: str = "", gate: str = "", now: float | None = None) -> None:
    """Append one line; never a subject or body. A log that can't be written refuses the send."""
    line = {"at": round(now if now is not None else time.time(), 3), "event": event,
            "to": (to or "").strip().lower()[:200], "hash": digest[:12]}
    if gate:
        line["gate"] = gate
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def recent_sends(now: float | None = None) -> int:
    """Send attempts (sent, failed or unknown) in the last hour. Unreadable log: raises (fail closed)."""
    now = now if now is not None else time.time()
    path = log_path()
    if not path.exists():
        return 0
    n = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        # One "attempt" line is written before every driver call, whatever the outcome.
        if row.get("event") == "attempt" and now - float(row.get("at") or 0) < 3600:
            n += 1
    return n


# ---- content checks -----------------------------------------------------------

def content_hash(to: str, subject: str, body: str) -> str:
    """Bound to the exact text: any change to To, Subject or body gives another hash."""
    blob = json.dumps([to, subject, body], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def one_recipient(to: str) -> str:
    if not isinstance(to, str):
        raise SendRefused("one recipient", "no address")
    address = to.strip()
    if not address:
        raise SendRefused("one recipient", "To is empty")
    if any(c in address for c in ",;<> \t\r\n") or not ADDRESS.match(address):
        raise SendRefused("one recipient", "To must be exactly one plain address")
    return address.lower()


def check_allowed(address: str) -> None:
    me = own_address()
    if me and address == me:
        return
    if address in allowed_addresses():
        return
    raise SendRefused("allowlist", f"{address} is not in {allow_path()} and is not your own address")


def check_secrets(subject: str, body: str) -> None:
    text = f"{subject}\n{body}"
    found = [f for s in _SCANNERS for f in s.scan(text) if f.level >= ThreatLevel.HIGH]
    if found:
        raise SendRefused("secrets", "the email contains " + ", ".join(sorted({f.description for f in found})))


def check_text(subject: str, body: str) -> None:
    if not isinstance(subject, str) or not isinstance(body, str):
        raise SendRefused("content", "Subject and body must be text")
    if "\r" in subject or "\n" in subject:
        raise SendRefused("content", "Subject has a line break")
    if not body.strip():
        raise SendRefused("content", "the body is empty")


# ---- interrupt: prepare -------------------------------------------------------

@dataclass(frozen=True)
class Pending:
    token: str
    to: str
    subject: str
    body: str
    digest: str
    draft_id: str
    issued: float

    def preview(self) -> dict:
        """What the window shows, read-only, above the Send button."""
        return {"token": self.token, "to": self.to, "subject": self.subject, "body": self.body,
                "expires_in": int(TOKEN_SECONDS), "draft_id": self.draft_id}


_pending: dict[str, Pending] = {}
_lock = threading.Lock()


def _not_flux(_draft_id: str) -> bool:
    return False


def prepare_send(to: str, subject: str, body: str, *, draft_id: str = "",
                 is_flux_draft: Callable[[str], bool] = _not_flux, now: float | None = None) -> dict:
    """Pause before sending: check what can be checked, return a preview and a one-time token.

    Nothing is sent here. The token is bound to a hash of exactly these three strings."""
    if not enabled():
        raise SendRefused("flag", f"sending is off ({ALLOW_ENV} is not 1)")
    if not draft_id or not is_flux_draft(draft_id):
        raise SendRefused("flux draft", "only a draft Flux made in this window can be sent")
    address = one_recipient(to)
    check_text(subject, body)
    check_allowed(address)
    check_secrets(subject, body)
    if recent_sends(now) >= MAX_PER_HOUR:
        raise SendRefused("rate", f"already {MAX_PER_HOUR} sends in the last hour")
    now = now if now is not None else time.time()
    digest = content_hash(to, subject, body)
    p = Pending(secrets.token_urlsafe(24), to, subject, body, digest, draft_id, now)
    with _lock:
        for t in [t for t, old in _pending.items() if now - old.issued > TOKEN_SECONDS]:
            del _pending[t]
        _pending[p.token] = p
    _log("prepared", address, digest, now=now)
    return p.preview()


def cancel(token: str) -> bool:
    """The preview's Cancel (deny): the token can no longer be used."""
    with _lock:
        p = _pending.pop(token, None) if isinstance(token, str) else None
    if p is not None:
        _log("cancelled", p.to, p.digest)
    return p is not None


def forget_all() -> None:
    """Drop every outstanding token (tests; a new chat)."""
    with _lock:
        _pending.clear()


# ---- the approval event -------------------------------------------------------

_KEY = object()


class UserApproval:
    """Proof that a person clicked Send in the Flux window. Only ``from_click`` makes one."""

    def __init__(self, key, at: float):
        if key is not _KEY:
            raise SendRefused("click", "an approval comes only from a clicked Send button")
        self.at = at

    @classmethod
    def from_click(cls, method: str, path: str, headers, allowed_origins: tuple[str, ...]) -> "UserApproval":
        """Built by the window server for POST /send/confirm with the click header."""
        if method != "POST" or path != "/send/confirm":
            raise SendRefused("click", "not the Send button's request")
        get = getattr(headers, "get", None)
        if get is None or get(CLICK_HEADER) != CLICK_VALUE:
            raise SendRefused("click", "the request did not come from a Send click")
        origin = get("Origin")
        if origin and origin not in allowed_origins:
            raise SendRefused("click", "the click came from another page")
        return cls(_KEY, time.time())


# ---- resume: send -------------------------------------------------------------

def send_draft(token: str, to: str, subject: str, body: str, *, approval: UserApproval,
               driver: Callable[[str, str, str], str] | None = None, now: float | None = None) -> str:
    """Send exactly the previewed email, once, after every gate. Returns ``OK sent``.

    Raises ``SendRefused`` for any gate; the driver is only called when all of them pass."""
    attempt_to = to if isinstance(to, str) else ""
    try:
        if not enabled():
            raise SendRefused("flag", f"sending is off ({ALLOW_ENV} is not 1)")
        if not isinstance(approval, UserApproval):
            raise SendRefused("click", "an approval comes only from a clicked Send button")
        now = now if now is not None else time.time()
        with _lock:
            p = _pending.pop(token, None) if isinstance(token, str) else None  # single use, even on refusal
        if p is None:
            raise SendRefused("token", "unknown or already used; press Send… again for a new preview")
        if now - p.issued > TOKEN_SECONDS:
            raise SendRefused("token", "the preview is older than 5 minutes; make a new one")
        if not isinstance(to, str) or not isinstance(subject, str) or not isinstance(body, str) \
                or content_hash(to, subject, body) != p.digest:
            raise SendRefused("content", "To, Subject or body changed after the preview")
        address = one_recipient(to)
        check_text(subject, body)
        check_allowed(address)
        check_secrets(subject, body)
        if recent_sends(now) >= MAX_PER_HOUR:
            raise SendRefused("rate", f"already {MAX_PER_HOUR} sends in the last hour")
    except SendRefused as e:
        _log("refused", attempt_to, gate=e.gate)
        raise
    if driver is None and os.environ.get("PYTEST_CURRENT_TEST"):
        _log("refused", address, p.digest, gate="test")
        raise SendRefused("test", "tests never drive the real Gmail send")
    _log("attempt", address, p.digest, now=now)  # counts toward the rate limit even if it fails
    result = (driver or gmail_send)(to.strip(), subject, body)
    event = "sent" if result == SENT else ("unknown" if result.startswith("UNKNOWN") else "failed")
    _log(event, address, p.digest)
    if event == "failed":
        raise SendRefused("gmail", result)
    return result


# ---- the Gmail driver -----------------------------------------------------------

# Gmail's Send control inside a compose; this file is the only one allowed to name it.
SEND_BUTTON = ("div[role='button'][aria-label^='Send']", "div[role='button'][data-tooltip^='Send']")
SENT_TOAST = "text=Message sent"


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def gmail_send(to: str, subject: str, body: str) -> str:
    """Type a fresh compose with draft.py's checks, read it back, click Send once."""
    from harness.browser.session import get_session
    from harness.email import draft
    from harness.email.status import LOGIN_LINE, signed_in

    page = get_session().start().page
    if not signed_in(page):
        return LOGIN_LINE
    try:
        draft.close_open_composes(page)
        draft.open_compose(page)
        box = draft._wait_visible(page, "compose_body", timeout_ms=10000)
        if not box.count():
            return "ERR mail.google.com | compose did not open | nothing sent"
        problem = draft.blank_problem(draft.compose_state(page, box))
        if problem:
            draft.close_compose(page)
            return f"ERR mail.google.com | refused a restored draft | {problem} | nothing sent"
        draft._wait_visible(page, "compose_to", timeout_ms=10000).fill(to)
        page.keyboard.press("Enter")
        problem = draft.wait_recipient_problem(page, box, to)
        if problem:
            draft.close_compose(page)
            return f"ERR mail.google.com | {problem} | nothing sent"
        draft._wait_visible(page, "compose_subject").fill(subject)
        box.fill(body)
        page.wait_for_timeout(300)
        state = draft.compose_state(page, box)
        problem = draft.recipient_problem(state, to)
        if not problem and (state.get("subject") or "") != subject:
            problem = "Subject read back differently"
        if not problem and _norm(draft._body_without_signature(state.get("body") or "")) != _norm(
                draft._body_without_signature(body)):
            problem = "body read back differently"
        if problem:
            draft.close_compose(page)
            return f"ERR mail.google.com | {problem} | saved as a draft, nothing sent"
        root = box.locator("xpath=ancestor::*[.//input[@name='subjectbox']][1]")
        buttons = [b for sel in SEND_BUTTON for b in root.locator(sel).all() if b.is_visible()]
        if len(buttons) != 1:
            draft.close_compose(page)
            return f"ERR mail.google.com | found {len(buttons)} Send buttons | saved as a draft, nothing sent"
        buttons[0].click()
        try:
            page.wait_for_selector(SENT_TOAST, timeout=10000)
        except Exception:
            return "UNKNOWN mail.google.com | clicked Send once, no 'Message sent' seen | check Sent"
        return SENT
    except Exception as exc:
        return f"ERR mail.google.com | send failed | {' '.join(str(exc).split())[:100]}"
