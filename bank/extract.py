"""Bonsai 4B pulls out text fields; code does headers, dates, course and folder."""
from __future__ import annotations

import re
from datetime import date, datetime
from email.utils import getaddresses, parsedate_to_datetime

from . import classify, dates

CHUNK_TOKENS = 6000

SYSTEM = ("You extract facts from emails and web pages for a student's notes. "
          "You copy words exactly and never invent information.")

PROMPT = """Read the {kind} below and fill in the JSON.

Rules:
- sender_address: the email address in the From line. Never a name.
- ask: the main thing the reader should do, as a short instruction. Any request or instruction to the reader counts, even polite or automated ones: pay, submit, send, book, register, fill out, push, reply. A bill or statement that says payments are due asks the reader to pay, even if it also says some people need no action. Pick the task given to the reader ("could you take X?") over closing lines like "let me know". Use null only when the text asks nothing of the reader, as in a newsletter or a thank-you note; a generic line like "visit the website" or "questions? contact us" alone is not an ask.
- deadlines: every time by which the reader must do something, copied exactly as written, including relative words like "tomorrow morning", "Friday at 5pm", "before Tuesday", "the 25th". Do not turn them into dates. Event days, menus and opening hours are not deadlines. Empty list if none.
- course: a course code like "CS 3110" if the text names one, else null.

{KIND}:
{text}"""

HINT = ('{"sender_name": "name in the From line, or null", '
        '"sender_address": "email address in the From line, or null", '
        '"sender_is_person": true, "subject": "subject line or page title", '
        '"summary": "one or two sentences", "ask": "one sentence, or null", '
        '"deadlines": ["each phrase exactly as written"], '
        '"course": "course code or null", "topic": "a few words"}')

_NULLS = {"", "null", "none", "n/a", "na", "nothing", "no", "-"}


def parse_headers(text: str) -> dict:
    """From/Date/Subject from the header block at the top, if there is one."""
    out: dict = {}
    for line in text.lstrip().splitlines():
        if not line.strip():
            break
        k, sep, v = line.partition(":")
        if not sep or " " in k.strip():
            break
        k, v = k.strip().lower(), v.strip()
        if k == "from" and "from" not in out:
            (name, addr), = getaddresses([v])[:1] or [("", "")]
            out["sender_name"] = name.strip().strip('"') or None
            out["sender_address"] = addr.lower() if "@" in addr else None
            if not out["sender_name"] and not out["sender_address"]:
                out["sender_name"] = v or None
        elif k == "date" and "sent_date" not in out:
            try:
                out["sent_date"] = parsedate_to_datetime(v).date()
            except (TypeError, ValueError):
                m = re.search(r"\d{4}-\d{2}-\d{2}", v)
                if m:
                    out["sent_date"] = date.fromisoformat(m.group(0))
        elif k == "subject" and "subject" not in out:
            out["subject"] = v or None
    return out


def _clean(v):
    if v is None:
        return None
    if isinstance(v, str):
        return None if v.strip().strip(".").lower() in _NULLS else v.strip()
    if isinstance(v, (list, dict)) and not v:
        return None
    return v


def _phrases(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        v = [v]
    out = []
    for x in v:
        if isinstance(x, dict):
            x = x.get("phrase") or x.get("deadline") or x.get("text") or " ".join(
                str(y) for y in x.values() if y)
        x = _clean(str(x)) if x is not None else None
        if x:
            out.append(x)
    return out


def _bool(v) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return {"true": True, "yes": True, "false": False, "no": False}.get(v.strip().lower())
    return None


def ask_model(text: str, kind: str) -> dict:
    from llm import client
    prompt = PROMPT.format(kind=kind, KIND=kind.upper(), text=text)
    got = client.complete_json(prompt, system=SYSTEM, json_schema_hint=HINT, max_tokens=400)
    return got if isinstance(got, dict) else {}


ASK_FOLLOWUP = ("{KIND}:\n{text}\n\nThis {kind} gives the deadline \"{phrase}\". What does the reader "
                "have to do by then? Reply with one short instruction to the reader, nothing else.")


def ask_for_deadline(text: str, kind: str, phrase: str) -> str | None:
    """Second call, only when the model listed a deadline but no ask."""
    from llm import client
    got = client.complete(ASK_FOLLOWUP.format(KIND=kind.upper(), kind=kind, text=text, phrase=phrase),
                          system=SYSTEM, max_tokens=60)
    got = got.strip().strip('"').strip()
    return _clean(got)


def chunks(text: str) -> list[str]:
    from llm import tokens
    if tokens.count(text) <= CHUNK_TOKENS:
        return [text]
    return tokens.split_to_budget(text, CHUNK_TOKENS)


def build_fields(text: str, kind: str, today: date, raws: list[dict]) -> dict:
    """Merge model replies (one per chunk) with header parsing and code-side rules."""
    first = raws[0] if raws else {}
    hdr = parse_headers(text)

    def pick(key):
        if hdr.get(key):
            return hdr[key]
        for r in raws:
            v = _clean(r.get(key))
            if v:
                return v
        return None

    sender_name = pick("sender_name") if kind == "email" else None
    sender_address = pick("sender_address") if kind == "email" else None
    if sender_address and "@" not in str(sender_address):
        sender_address = None
    sent = hdr.get("sent_date") or today
    subject = pick("subject")
    summary = next((str(_clean(r.get("summary"))) for r in raws if _clean(r.get("summary"))), "")
    ask = next((str(_clean(r.get("ask"))) for r in raws if _clean(r.get("ask"))), None)

    deadlines, seen, prev = [], set(), None
    for r in raws:
        for ph in _phrases(r.get("deadlines")):
            d, t = dates.resolve(ph, sent, prev)
            key = (d.isoformat() if d else None, ph.lower())
            if key in seen:
                continue
            seen.add(key)
            deadlines.append({"phrase": ph, "date": d.isoformat() if d else None, "time": t})
            prev = d or prev
    if not deadlines and ask:
        # The model sometimes leaves a deadline inside the ask ("send it tomorrow").
        for ph in dates.find_phrases(ask):
            d, t = dates.resolve(ph, sent, prev)
            if d:
                deadlines.append({"phrase": ph, "date": d.isoformat(), "time": t})
                prev = d

    model_course = next((str(_clean(r.get("course"))) for r in raws if _clean(r.get("course"))), None)
    course = classify.find_course(subject, text, model_course)
    person = classify.is_person(sender_name, sender_address, _bool(first.get("sender_is_person")))
    topic = next((str(_clean(r.get("topic"))) for r in raws if _clean(r.get("topic"))), None)
    return {
        "kind": kind,
        "folder": classify.folder_for(kind, course, person),
        "sender_name": sender_name,
        "sender_address": sender_address,
        "sent_date": sent.isoformat(),
        "subject": subject,
        "ask": ask,
        "deadlines": deadlines,
        "course": course,
        "topic": topic,
        "body": summary,
        "ingested_at": datetime.now().replace(microsecond=0).isoformat(),
    }
