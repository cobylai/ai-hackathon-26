"""Find patterns in the bank and the calendar; turn each into one candidate fact. Code only,
except relation guesses, which come from relation_fn (Bonsai in discover/session.py).

    candidates(entries, events, relation_fn=None) -> [candidate], most supported first

A candidate is a dict:
    id        stable hash of kind + what it would write, so a second run finds the same id
    kind      "event" | "course" | "person" | "relation" | "bill"
    question  one yes/no question
    fact      what is written on a yes, in the user's voice for notes
    write     {"to": "note"} | {"to": "fact", "name"} | {"to": "relation", "name", "relation"}
    sources   [{"label", "line", "path"}]: the entries or events it came from
    score     how many entries or events support it
Nothing is written here.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from datetime import date

from reason import route

MIN_EVENTS = 3      # same title, weekday and time
MIN_COURSE_MAIL = 2  # a course code in this many mail entries (one Canvas entry is enough)
MIN_PERSON = 3      # entries from one sender
MIN_BILLS = 2       # entries with an amount and a due date from one sender

COURSE_RE = re.compile(r"\b([A-Z]{2,5}) ?(\d{4})\b")
AMOUNT_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d\d)?")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
ORDER = {"person": 0, "relation": 1, "course": 2, "event": 3, "bill": 4}


def cid(kind: str, write: dict, fact: str) -> str:
    key = f"{kind}|{write.get('name', '')}|{fact}".lower()
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def _short(iso) -> str:
    try:
        d = date.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return str(iso or "no date")
    return f"{d:%b} {d.day}"


def _time(dt) -> str:
    h, m = dt.hour, dt.minute
    if (h, m) == (12, 0):
        return "noon"
    return f"{h % 12 or 12}{':%02d' % m if m else ''}{'am' if h < 12 else 'pm'}"


def entry_source(e: dict) -> dict:
    who = e.get("sender_name") or e.get("sender_address") or "unknown sender"
    return {"label": f"{who}, {_short(e.get('sent_date'))}",
            "line": f"{_short(e.get('sent_date'))}  {who}: {e.get('subject') or '(no subject)'}",
            "path": e.get("path")}


def _cand(kind, question, fact, write, sources, score=None) -> dict:
    return {"id": cid(kind, write, fact), "kind": kind, "question": question, "fact": fact,
            "write": write, "sources": sources, "score": len(sources) if score is None else score}


def courses_in(e: dict) -> list[str]:
    text = " ".join(str(e.get(k) or "") for k in ("course", "subject", "ask", "body"))
    if e.get("kind") == "canvas":
        text = f"{e.get('sender_name') or ''} {text}"
    return list(dict.fromkeys(f"{a} {b}" for a, b in COURSE_RE.findall(text)))


# ---- the four patterns ----------------------------------------------------

def event_candidates(events: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for ev in events or []:
        if ev.get("all_day") or not ev.get("start") or not (ev.get("title") or "").strip():
            continue
        s = ev["start"]
        groups[(ev["title"].strip().lower(), s.weekday(), s.hour, s.minute)].append(ev)
    out = []
    for (_, wd, _, _), evs in groups.items():
        if len(evs) < MIN_EVENTS:
            continue
        evs = sorted(evs, key=lambda e: e["start"])
        title, day, t = evs[-1]["title"].strip(), WEEKDAYS[wd], _time(evs[0]["start"])
        src = [{"label": "Apple Calendar", "line": f"{e['start']:%a %b} {e['start'].day} {t}  {title}",
                "path": None} for e in evs]
        out.append(_cand("event", f"Do you have {title} every {day} at {t}?",
                         f"I have {title} every {day} at {t}", {"to": "note"}, src))
    return out


def course_candidates(entries: list[dict]) -> list[dict]:
    seen = defaultdict(list)   # code -> entries
    names = {}                 # code -> Canvas course name ("HIST 2147 Maps and Empires")
    canvas = set()
    for e in entries:
        if e.get("kind") not in ("email", "canvas"):
            continue
        for code in courses_in(e):
            seen[code].append(e)
            if e.get("kind") == "canvas":
                canvas.add(code)
                n = (e.get("sender_name") or "").strip()
                if n.upper().startswith(code.replace(" ", "")) or n.startswith(code):
                    names.setdefault(code, n)
    out = []
    for code, es in seen.items():
        mail = [e for e in es if e.get("kind") == "email"]
        if code not in canvas and len(mail) < MIN_COURSE_MAIL:
            continue
        name = names.get(code, code)
        es = sorted(es, key=lambda e: e.get("sent_date") or "", reverse=True)
        out.append(_cand("course", f"Are you taking {name}?", f"I'm taking {name}",
                         {"to": "note"}, [entry_source(e) for e in es]))
    return out


def _senders(entries: list[dict]) -> dict[str, list[dict]]:
    """Email entries grouped by sender (address, else name), people only, newest first."""
    by = defaultdict(list)
    for e in entries:
        if e.get("kind") != "email":
            continue
        if not route.name_words(e.get("sender_name"), e.get("sender_address")):
            continue  # automated sender or no name
        key = (e.get("sender_address") or e.get("sender_name") or "").lower()
        if key:
            by[key].append(e)
    for es in by.values():
        es.sort(key=lambda e: e.get("sent_date") or "", reverse=True)
    return by


def person_candidates(entries: list[dict], relation_fn=None) -> list[dict]:
    out = []
    for es in _senders(entries).values():
        if len(es) < MIN_PERSON:
            continue
        name = es[0].get("sender_name") or es[0].get("sender_address")
        codes = Counter(c for e in es for c in courses_in(e))
        src = [entry_source(e) for e in es]
        if codes:
            course = codes.most_common(1)[0][0]
            out.append(_cand("person", f"Does {name} write to you about {course}?",
                             f"writes to you about {course}", {"to": "fact", "name": name}, src))
        else:
            out.append(_cand("person", f"Is {name} someone you hear from often?",
                             "writes to you often", {"to": "fact", "name": name}, src))
        rel = relation_fn(name, es) if relation_fn else None
        if rel:
            out.append(_cand("relation", f"Is {name} your {rel}?", rel,
                             {"to": "relation", "name": name, "relation": rel}, src,
                             score=len(src) - 0.5))
    return out


def bill_candidates(entries: list[dict]) -> list[dict]:
    out = []
    for es in _senders(entries).values():
        bills = []
        for e in es:
            amt = AMOUNT_RE.search(" ".join(str(e.get(k) or "") for k in ("subject", "ask", "body")))
            due = next((d for d in e.get("deadlines") or [] if d.get("date")), None)
            if amt and due:
                bills.append((e, amt.group(0).replace(" ", ""), due["date"]))
        if len(bills) < MIN_BILLS:
            continue
        name = es[0].get("sender_name") or es[0].get("sender_address")
        seen = "; ".join(f"{a} due {_short(d)}" for _, a, d in bills[:3])
        out.append(_cand("bill", f"Does {name} send you bills to pay ({seen})?",
                         "sends you bills to pay", {"to": "fact", "name": name},
                         [entry_source(e) for e, _, _ in bills]))
    return out


def candidates(entries: list[dict], events: list[dict] | None = None, relation_fn=None) -> list[dict]:
    out = (person_candidates(entries, relation_fn) + course_candidates(entries)
           + event_candidates(events or []) + bill_candidates(entries))
    return sorted(out, key=lambda c: (-c["score"], ORDER[c["kind"]], c["question"]))
