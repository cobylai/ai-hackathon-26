"""The "send it" route (playbooks/send.md): a preview with a Send button, never a send.

    handle(question) -> Answer | None      route "send"; a.send = preview for the window
    prepare(draft_id, to, subject, body)   the draft box's Send…: same preview

This module only ever calls ``harness.email.send.prepare_send`` (the pause). The send
itself (``send_draft``) is reachable only from the window server's POST /send/confirm,
built from a clicked Send button (reason/web.py). Off unless FLUX_ALLOW_SEND=1.
"""
from __future__ import annotations

import re

from . import compose, playbook
from .playbook import say


def _say(key: str, **kw) -> str:
    return say("send", key, **kw)


def matches(question: str) -> bool:
    q = re.sub(r"[\s.!?]+$", "", (question or "").strip())
    return bool(playbook.trigger("send", "send").fullmatch(q))


def prepare(draft_id: str, to: str, subject: str, body: str) -> dict:
    """{"send": preview, "text"} or {"text"} when a gate refuses. Never sends."""
    from harness.email import send as gate  # only once "send it" matched: other routes load no harness
    try:
        p = gate.prepare_send(to, subject, body, draft_id=draft_id, is_flux_draft=compose.is_flux_draft)
    except gate.SendRefused as e:
        return {"text": _say("off") if e.gate == "flag" else _say("refused", why=e.why)}
    return {"send": p, "text": _say("preview")}


def handle(question: str):
    from .answer import Answer
    if not matches(question):
        return None
    from harness.email import send as gate
    if not gate.enabled():
        return Answer(_say("off"), "send")
    d = compose.last_draft()
    if d is None:
        return Answer(_say("no_draft"), "send")
    got = prepare(d["id"], d.get("to") or "", d.get("subject") or "", d.get("body") or "")
    a = Answer(got["text"], "send")
    a.send = got.get("send")
    return a
