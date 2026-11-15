"""Drafts you edit and open in Mail; nothing is ever sent. playbooks/compose.md.

    handle(question, today, root, session, events_fn) -> Answer | None   # route "compose"
    reply_draft(entry, gist, events_fn) -> draft dict        (a Suggested "Draft" click)
    rewrite(draft_id, gist) -> draft dict                     (the box's "What should it say?")
    mailto(to, subject, body) -> "mailto:..."                 (Open in Mail)

A draft is {"id", "to", "to_name", "subject", "body", "used": [labels], "kind"}.
Meeting replies come from code templates; other bodies from Bonsai, only from bank entries
and what the user said. To stays empty when no address is stored; nothing is made up.
"""
from __future__ import annotations

import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import quote

import bank
from bank import store
from bank.query import STOPWORDS

from . import playbook, suggest
from .playbook import say

TTL = 180.0
MAX_QUESTIONS = 2
TOPIC_LIMIT = 4


def _say(key: str, **kw) -> str:
    return say("compose", key, **kw).replace("\\n", "\n")


def _t(key: str):
    return playbook.trigger("compose", key)


@dataclass
class Held:
    need: str                 # "who" | "which" | "more"
    name: str | None          # as typed
    topic: str | None
    reply: bool
    gist: str
    asked: int
    at: float = field(default_factory=time.monotonic)
    options: list[dict] = field(default_factory=list)


_held: Held | None = None
_drafts: dict[str, dict] = {}   # draft id -> {"draft", "entry"} for "What should it say?"


def waiting() -> bool:
    return _held is not None and time.monotonic() - _held.at <= TTL


def reset() -> None:
    global _held
    _held = None


# ---- parsing ----------------------------------------------------------------

def parse(q: str) -> dict | None:
    """{"reply": bool, "name": str | None, "gist": str} | None. Code only."""
    q = re.sub(r"[\s.!?]+$", "", (q or "").strip())
    if _t("gmail").search(q):
        return None
    for kind in ("reply", "compose"):
        m = _t(kind).search(q)
        if m and m.start() == 0:
            rest = (m.group(1) or "").strip()
            name, gist = None, rest
            if kind == "reply" or re.match(r"(?i)to\s+", rest):
                rest = re.sub(r"(?i)^to\s+", "", rest)
                g = re.search(r"(?i)[\s,]+(?:" + _gist() + r")\s+", " " + rest)
                if g:
                    name, gist = (" " + rest)[:g.start()].strip(), (" " + rest)[g.end():].strip()
                else:
                    name, gist = rest, ""
                name = re.sub(r"'s?(?:\s+(?:email|message|mail))?$", "", name).strip() or None
            else:
                gist = re.sub(r"(?i)^(?:" + _gist() + r")\s+", "", rest).strip()
            return {"reply": kind == "reply", "name": name, "gist": gist}
    return None


def _gist() -> str:
    return "|".join(playbook.load("compose").triggers["gist"])


# ---- who --------------------------------------------------------------------

def people_named(name: str, root) -> list[dict]:
    """One row per person called that: {"name", "address", "entries"} (address may be None)."""
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) > 1]
    if not words:
        return []
    found: dict[str, dict] = {}
    for e in bank.by_person(words[0], root=root):
        if e.get("kind") != "email":
            continue
        who = e.get("sender_name") or e.get("sender_address") or ""
        hay = f"{who} {e.get('sender_address') or ''}".lower()
        if not all(w in hay for w in words):
            continue
        row = found.setdefault(who.lower(), {"name": who, "address": None, "entries": []})
        row["entries"].append(e)
        row["address"] = row["address"] or e.get("sender_address")
    if not found:
        try:
            page = bank.people.get(name, root=root)
        except Exception:
            page = None
        if page:
            found[page["name"].lower()] = {"name": page["name"], "address": None, "entries": [], "page": page}
    return list(found.values())


def my_first_name(root) -> str | None:
    for e in bank.notes(root):
        m = _t("my_name").search(e.get("body") or e.get("subject") or "")
        if m:
            return next(g for g in m.groups() if g)
    return None


def _signed(body: str, root) -> str:
    me = my_first_name(root)
    body = body.rstrip()
    return body + _say("sign", name=me) if me else body


def _label(e: dict) -> str:
    from .answer import source_label
    return source_label(e)


# ---- drafts -----------------------------------------------------------------

def _keep(draft: dict, entry: dict | None) -> dict:
    draft["id"] = uuid.uuid4().hex[:10]
    _drafts[draft["id"]] = {"draft": draft, "entry": entry}
    return draft


def _subject(e: dict) -> str:
    s = (e.get("subject") or "").strip()
    return s if re.match(r"(?i)^re:", s) else f"Re: {s}" if s else "Re:"


def write_reply(gist: str, e: dict) -> str:
    from llm.client import complete
    who = e.get("sender_name") or e.get("sender_address") or "the sender"
    text = complete(playbook.prompt("compose", "reply_prompt").format(
        who=who, subject=e.get("subject") or "(no subject)", summary=e.get("body") or "",
        ask_line=f"They asked: {e['ask']}" if e.get("ask") else "",
        gist=gist or "a short, friendly reply", first=suggest.first_name(e)),
        system=playbook.prompt("compose", "reply_system"), max_tokens=300,
        sampling={"temperature": 0.2})
    lines = [ln for ln in text.strip().strip('"').splitlines()
             if not re.match(r"^\s*(subject|to)\s*:", ln, re.I)]
    return "\n".join(lines).strip()


def reply_draft(e: dict, gist: str = "", root=None, events_fn=None, writer=None) -> dict:
    """A reply to one email. Meeting asks with a read time and calendar use code templates."""
    first = suggest.first_name(e)
    m = suggest.meeting(e, events_fn) if not gist else None
    if m:
        kind = "yes" if m["free"] else ("no_slot" if m["slot"] else "no_reason")
        body = _say(kind, first=first, when=m["when"], clash=m["clash"], slot=m["slot"])
    else:
        kind = "model"
        body = (writer or write_reply)(gist, e)
        if not body:
            raise RuntimeError("the model wrote nothing")
    return _keep({"kind": kind, "to": e.get("sender_address") or "",
                  "to_name": e.get("sender_name") or e.get("sender_address") or "",
                  "subject": _subject(e), "body": _signed(body, root), "used": [_label(e)]}, e)


def _topic_entries(topic: str, person: dict | None, root) -> list[dict]:
    words = {w for w in re.findall(r"[a-z0-9]+", topic.lower()) if len(w) > 2 and w not in STOPWORDS}
    if not words:
        return []
    hits = [e for e in bank.search(topic, limit=12, root=root) if e.get("kind") != "me"]
    hits = [e for e in hits if words & set(re.findall(r"[a-z0-9]+", " ".join(
        str(e.get(k) or "") for k in ("subject", "ask", "body", "topic")).lower()))]
    if person:
        mine = {e.get("path") for e in person.get("entries") or []}
        hits.sort(key=lambda e: e.get("path") not in mine)
    return hits[:TOPIC_LIMIT]


def write_new(topic: str, to_name: str | None, notes: str, greeting: str) -> dict:
    from llm.client import complete_json
    got = complete_json(playbook.prompt("compose", "compose_prompt").format(
        to_line=f" to {to_name}" if to_name else "", topic=topic, notes=notes, greeting=greeting),
        system=playbook.prompt("compose", "compose_system"), max_tokens=300,
        json_schema_hint=playbook.prompt("compose", "compose_hint"), sampling={"temperature": 0.2})
    if not isinstance(got, dict):
        return {}
    return {"subject": str(got.get("subject") or "").strip(), "body": str(got.get("body") or "").strip()}


def new_draft(person: dict | None, typed_name: str | None, topic: str, entries: list[dict],
              said: str | None, root, writer=None) -> dict:
    from .answer import note_block
    blocks = [note_block(i + 1, e) for i, e in enumerate(entries)]
    page = (person or {}).get("page") or (bank.people.get(person["name"], root=root) if person else None)
    if page and (page.get("relation") or page.get("facts")):
        facts = "; ".join(f["fact"] for f in page.get("facts") or [])
        blocks.append(f"About {page['name']}: {page.get('relation') or ''} {facts}".strip())
    me = [n.get("body") or "" for n in bank.notes(root)[:5]]
    if me:
        blocks.append("About the student: " + "; ".join(me))
    if said:
        blocks.append(f"The student said: {said}")
    to_name = (person or {}).get("name") or typed_name
    first = to_name.split()[0] if to_name else None
    got = (writer or write_new)(topic, to_name, "\n\n".join(blocks), f"Hi {first}," if first else "Hi,")
    if not got.get("body"):
        raise RuntimeError("the model wrote nothing")
    return _keep({"kind": "new", "to": (person or {}).get("address") or "", "to_name": to_name or "",
                  "subject": got.get("subject") or topic[:60], "body": _signed(got["body"], root),
                  "used": [_label(e) for e in entries] + (["what you said"] if said else [])}, None)


def rewrite(draft_id: str, gist: str, root=None, writer=None) -> dict | None:
    """The box's "What should it say?": a new body for the same reply, from Bonsai."""
    got = _drafts.get(draft_id)
    if not got or not got["entry"]:
        return None
    d = reply_draft(got["entry"], gist or "a short, friendly reply", root=root, writer=writer)
    d["to"], d["subject"] = got["draft"]["to"], got["draft"]["subject"]
    return d


def mailto(to: str, subject: str, body: str) -> str:
    return (f"mailto:{quote((to or '').strip(), safe='@,+')}"
            f"?subject={quote(subject or '', safe='')}&body={quote(body or '', safe='')}")


def open_in_mail(to: str, subject: str, body: str, runner=None) -> str:
    """Hand a plain-text mailto: link to macOS (the default mail app). Never sends."""
    url = mailto(to, subject, body)
    try:
        p = (runner or (lambda u: subprocess.run(["open", u], capture_output=True, text=True, timeout=15)))(url)
    except (OSError, subprocess.TimeoutExpired) as e:
        return _say("open_failed", why=e)
    if getattr(p, "returncode", 0):
        return _say("open_failed", why=(getattr(p, "stderr", "") or "open failed").strip())
    return _say("opened")


# ---- the route --------------------------------------------------------------

def _answer(draft: dict, who_hint: str | None = None):
    from .answer import Answer
    if draft["to"]:
        head = _say("draft_head", who=f"{draft['to_name']} <{draft['to']}>" if draft["to_name"] else draft["to"])
    elif draft["to_name"] or who_hint:
        head = _say("draft_head_noto", who=draft["to_name"] or who_hint)
    else:
        head = _say("draft_head_nobody")
    lines = [head, "", f"To: {draft['to']}", f"Subject: {draft['subject']}", "", draft["body"]]
    if draft["used"]:
        lines += ["", _say("used", labels="; ".join(draft["used"]))]
    a = Answer("\n".join(lines), "compose")
    a.draft = draft
    return a


def _ask(h: Held, text: str):
    from .answer import Answer
    global _held
    h.at, h.asked = time.monotonic(), h.asked + 1
    _held = h
    return Answer(text, "compose")


def _go(h: Held, root, session, events_fn, writer):
    """Carry a request on as far as it can go: a question, or the draft."""
    from .answer import Answer
    person = None
    if h.name:
        found = h.options or people_named(h.name, root)
        if len(found) > 1 and h.asked < MAX_QUESTIONS and h.need != "which":
            h.need, h.options = "which", found
            return _ask(h, _say("which", name=h.name[:1].upper() + h.name[1:],
                                options=" or ".join(p["name"] for p in found) + "?"))
        person = found[0] if len(found) == 1 else None
        if not found and h.asked < MAX_QUESTIONS and h.need != "who":
            if h.reply:
                return Answer(_say("no_sender", name=h.name[:1].upper() + h.name[1:]), "compose")
            h.need = "who"
            return _ask(h, _say("who_unknown", name=h.name[:1].upper() + h.name[1:]))
    elif h.asked < MAX_QUESTIONS and h.need != "who":
        h.need = "who"
        return _ask(h, _say("who"))
    try:
        if h.reply:
            mails = [e for e in (person or {}).get("entries") or [] if e.get("sender_address")]
            if not mails:
                return Answer(_say("no_sender", name=(h.name or "them").title()), "compose")
            e = mails[0]
            d = reply_draft(e, h.gist, root=root, events_fn=events_fn, writer=writer)
            suggest.mark_drafted(session, e)
            return _answer(d)
        topic = (h.topic or "").strip()
        entries = _topic_entries(topic, person, root) if topic else []
        if not entries and h.need != "more" and h.asked < MAX_QUESTIONS:
            h.need = "more"
            return _ask(h, _say("more", topic=topic) if topic else _say("more_blank"))
        said = h.gist if h.need == "more" else None
        d = new_draft(person, h.name, topic or (said or ""), entries, said, root, writer=writer)
        return _answer(d, h.name)
    except Exception as ex:  # model server down, budget, ...
        return Answer(_say("cannot_write", why=f"{type(ex).__name__}: {ex}"), "compose")


def _is_new_question(q: str) -> bool:
    """A yes/no (act's), a question, or a command: not an answer to "Who is this to?"."""
    from . import act
    q = q.strip()
    return (act.is_yes(q) or act.is_no(q) or q.endswith("?") or bool(playbook.trigger("compose", "new").match(q)))


def handle(question: str, today: date | None = None, root: Path | None = None, *, session=None,
           events_fn=None, writer=None):
    """An Answer for a draft request or a reply to a held compose question; None otherwise."""
    global _held
    held, _held = (_held if waiting() else None), None
    q = (question or "").strip()
    if held is not None and not parse(q) and not _is_new_question(q):
        ans = re.sub(r"[\s.!?]+$", "", q)
        if held.need == "who":
            held.name = re.sub(r"(?i)^(?:to\s+|it'?s\s+(?:to|for)\s+|for\s+)", "", ans).strip() or None
            held.options = []
        elif held.need == "which":
            pick = [p for p in held.options if all(w in p["name"].lower() for w in ans.lower().split())]
            held.options = pick[:1] or held.options[:1]
        else:
            ans = re.sub(r"(?i)^(?:about|it'?s about|say|that)\s+", "", ans).strip()
            if not held.topic:  # "What should it say?" with no topic: look again with these words
                held.topic, held.need = ans, ""
                if _topic_entries(ans, None, root):
                    return _go(held, root, session, events_fn, writer)
                held.need = "more"
            held.gist = ans
        return _go(held, root, session, events_fn, writer)
    req = parse(q)
    if req is None:
        return None
    h = Held(need="", name=req["name"], topic=None if req["reply"] else req["gist"], reply=req["reply"],
             gist=req["gist"] if req["reply"] else "", asked=0)
    return _go(h, root, session, events_fn, writer)
