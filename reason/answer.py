"""answer(question): bank first, browser only when the bank falls short.

Routes, picked in code (reason/route.py), in this order:
  due     -> bank.due over a date range, list written in code, no model call
  calendar-> Apple Calendar events over a date range (applecal), written in code, no model call
  person  -> bank.by_person, Bonsai answers from those entries only
  else    -> bank.search + sufficiency.judge; if not enough: gather on the web when
             online (and ingest the page), or the plain offline message
"""
from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import bank
from bank import store

from . import route

OFFLINE_TEXT = "I don't have that saved, and the Mac is offline, so I can't look it up."
PERSON_LIMIT = 8
SEARCH_LIMIT = 5
GATHER_SECONDS = 60

PERSON_SYSTEM = ("You answer a student's questions using only the email notes you are given. "
                 "You never use outside knowledge and never guess.")
PERSON_PROMPT = """Today is {today}.

QUESTION: {question}

EMAIL NOTES FROM {who}:
{notes}

Answer the question in one to three sentences using only these notes. If the notes do not answer it, say that the saved emails from {who} don't say. List the numbers of the notes you used."""
PERSON_HINT = '{"answer": "your answer", "used": [1]}'


@dataclass
class Answer:
    text: str
    route: str                      # due | calendar | person | bank | web | offline | not_found
    sources: list[str] = field(default_factory=list)  # bank entry paths, or one url
    seconds: float = 0.0


# ---- formatting -------------------------------------------------------------

def _short_date(iso: str | None) -> str:
    try:
        d = date.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return str(iso or "no date")
    return f"{d:%b} {d.day}"


def _time(hhmm: str | None) -> str:
    if not hhmm:
        return ""
    h, m = (int(x) for x in hhmm.split(":"))
    suffix = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}{':%02d' % m if m else ''}{suffix}" if (h, m) != (12, 0) else "noon"


def source_label(e: dict) -> str:
    if e.get("kind") == "page":
        return str(e.get("source") or "a saved page")
    who = e.get("sender_name") or e.get("sender_address") or "unknown sender"
    return f"{who}, {_short_date(e.get('sent_date'))}"


def _with_source(text: str, entries: list[dict]) -> str:
    labels = list(dict.fromkeys(source_label(e) for e in entries))
    return f"{text.strip()}\nSource: {'; '.join(labels)}" if labels else text.strip()


def note_block(i: int, e: dict) -> str:
    dl = "; ".join(f"{d.get('phrase')}" + (f" ({d['date']}{' ' + d['time'] if d.get('time') else ''})"
                                           if d.get("date") else "")
                   for d in e.get("deadlines") or [])
    who = e.get("sender_name") or ""
    if e.get("sender_address"):
        who = f"{who} <{e['sender_address']}>".strip()
    lines = [f"[{i}] From: {who or e.get('source') or 'unknown'}",
             (f"Saved on: {e.get('sent_date') or 'unknown'}" if e.get("kind") == "page"
              else f"Date: {e.get('sent_date') or 'unknown'}"),
             f"Subject: {e.get('subject') or ''}"]
    if e.get("ask"):
        lines.append(f"Ask: {e['ask']}")
    if dl:
        lines.append(f"Deadlines: {dl}")
    lines.append(f"Summary: {e.get('body') or ''}")
    return "\n".join(lines)


# ---- routes -----------------------------------------------------------------

def _due(question: str, today: date, root) -> Answer:
    start, end, label = route.due_range(question, today)
    rows = bank.due(start, end, root=root)
    head = f"Due {label}" if start == end else (
        f"Due {label} ({_short_date(start.isoformat())} to {_short_date(end.isoformat())})")
    if not rows:
        return Answer(f"Nothing due {label} in your saved mail.", "due")
    lines = [head + ":"]
    for r in rows:
        e = r["entry"]
        what = (e.get("ask") or e.get("body") or e.get("subject") or "").strip().rstrip(".")
        when = route._day(date.fromisoformat(r["date"])) if start != end else ""
        t = _time(r.get("time"))
        stamp = " ".join(x for x in (when, t) if x)
        lines.append(f"- {stamp + '  ' if stamp else ''}{what} ({source_label(e)})")
        summary = (e.get("body") or "").strip()
        if summary and summary.rstrip(".") != what:  # the summary carries amounts etc.
            lines.append(f"    {summary}")
    paths = list(dict.fromkeys(r["entry"]["path"] for r in rows))
    return Answer("\n".join(lines), "due", paths)


NEXT_EVENT_DAYS = 60


def _event_line(e: dict, with_day: bool) -> str:
    day = route._day(e["start"].date()) if with_day else ""
    if e.get("all_day"):
        when = "all day"
    else:
        when = _time(f"{e['start']:%H:%M}")
        if e.get("end") and e["end"] > e["start"]:
            when += "\u2013" + _time(f"{e['end']:%H:%M}")
    where = f" ({e['location']})" if e.get("location") else ""
    return f"- {' '.join(x for x in (day, when) if x)}  {e.get('title') or '(no title)'}{where}"


def _calendar(question: str, today: date, now: datetime, events_fn) -> Answer:
    """Apple Calendar events, listed by code. No model call."""
    import applecal
    events_fn = events_fn or applecal.events
    src = f"Source: Apple Calendar ({applecal.calendar_name()})"
    try:
        if route.is_next_event(question):
            evs = [e for e in events_fn(today, today + timedelta(days=NEXT_EVENT_DAYS))
                   if (e["start"] >= now if not e.get("all_day") else e["start"].date() >= now.date())]
            if not evs:
                return Answer(f"Nothing coming up on your calendar in the next {NEXT_EVENT_DAYS} days.\n{src}",
                              "calendar")
            return Answer(f"Your next event:\n{_event_line(evs[0], True)}\n{src}", "calendar")
        start, end, label = route.due_range(question, today)
        evs = events_fn(start, end)
    except applecal.CalendarError as e:
        return Answer(f"I couldn't read Apple Calendar ({e}).", "calendar")
    if not evs:
        return Answer(f"Nothing on your calendar {label}.\n{src}", "calendar")
    head = (f"On your calendar {label}" if start == end else
            f"On your calendar {label} ({_short_date(start.isoformat())} to {_short_date(end.isoformat())})")
    lines = [head + ":"] + [_event_line(e, start != end) for e in evs]
    return Answer("\n".join(lines) + "\n" + src, "calendar")


def _senders(root) -> set[str]:
    names: set[str] = set()
    for e in store.all_entries(root):
        if e.get("kind") == "email":
            names |= route.name_words(e.get("sender_name"), e.get("sender_address"))
    return names


def _person_asks(question: str, who: str, root) -> Answer:
    """'What did <name> ask / want / need': each entry's ask, listed by code. No model call."""
    entries = bank.by_person(who, root=root)
    # "Nina Valdez": keep only senders that also match the question's other name words.
    words = {w.lower() for w in route._WORD.findall(question)} & _senders(root)
    narrowed = [e for e in entries
                if words <= route.name_words(e.get("sender_name"), e.get("sender_address"))]
    entries = (narrowed or entries)[:PERSON_LIMIT]
    many = len({e.get("sender_name") or e.get("sender_address") for e in entries}) > 1
    lines = []
    for e in entries:
        who_ = f"{e.get('sender_name') or e.get('sender_address')}, " if many else ""
        head = f"- {who_}{_short_date(e.get('sent_date'))}  {e.get('subject') or '(no subject)'}: "
        ask = (e.get("ask") or "").strip()
        if ask:
            lines.append(head + ask)
        else:
            lines.append(head + "no ask. " + (e.get("body") or "").strip())
    name = entries[0].get("sender_name") or who.title()
    top = "From " + (" / ".join(dict.fromkeys(e.get("sender_name") or "" for e in entries)) if many else name) + ":"
    return Answer(_with_source("\n".join([top] + lines), entries), "person", [e["path"] for e in entries])


def _person(question: str, who: str, today: date, root) -> Answer:
    if route.is_ask_question(question):
        return _person_asks(question, who, root)
    from llm import client
    entries = bank.by_person(who, root=root)[:PERSON_LIMIT]
    display = entries[0].get("sender_name") or who.title()
    notes = "\n\n".join(note_block(i + 1, e) for i, e in enumerate(entries))
    got = client.complete_json(
        PERSON_PROMPT.format(today=f"{today:%A} {today:%B} {today.day}, {today.year}",
                             question=question, who=display, notes=notes),
        system=PERSON_SYSTEM, max_tokens=300, json_schema_hint=PERSON_HINT,
        sampling={"temperature": 0.2})
    text = str((got or {}).get("answer") or "").strip() if isinstance(got, dict) else ""
    used = []
    if isinstance(got, dict) and isinstance(got.get("used"), list):
        for n in got["used"]:
            try:
                k = int(n)
            except (TypeError, ValueError):
                continue
            if 1 <= k <= len(entries) and entries[k - 1] not in used:
                used.append(entries[k - 1])
    used = used or entries
    if not text:
        text = f"The saved emails from {display} don't say."
    return Answer(_with_source(text, used), "person", [e["path"] for e in used])


def online(timeout: float = 2.0) -> bool:
    try:
        socket.create_connection(("www.bing.com", 443), timeout=timeout).close()
        return True
    except OSError:
        return False


def _bank(question: str, today: date, root):
    """(Answer, None) when the bank answers, else (None, entries looked at)."""
    from sufficiency import judge, quote_in_page
    entries = bank.search(question, limit=SEARCH_LIMIT, root=root)
    if not entries:
        return None
    blocks = [note_block(i + 1, e) for i, e in enumerate(entries)]
    v = judge(question, "\n\n".join(blocks), today=today)
    if not v.enough:
        return None
    hit = next((e for e, b in zip(entries, blocks) if quote_in_page(v.evidence or "", b)), entries[0])
    return Answer(_with_source(v.answer, [hit]), "bank", [hit["path"]])


def _web(question: str, today: date, root, search_fn=None, open_fn=None, ingest_fn=None) -> Answer:
    from sufficiency import gather
    if search_fn is None or open_fn is None:
        from harness.search import tools  # loads Playwright; web route only
        from sufficiency import websearch  # partner's engine.search, then Bing
        search_fn = search_fn or websearch.search
        open_fn = open_fn or tools.open_page
    ingest_fn = ingest_fn or bank.ingest
    r = gather(question, search_fn, open_fn, today=today, max_seconds=GATHER_SECONDS)
    if not r.found or not r.source:
        return Answer(r.message or "I couldn't find that on the web.", "not_found",
                      list(r.opened))
    url = r.source.url
    ans = (r.answer or "").strip()
    quote = (r.evidence or "").strip().strip('"“” ')
    text = ans + (f'\n"{quote}"' if quote and quote.lower() not in ans.lower() else "")
    try:
        got = ingest_fn(saved_page(question, ans, quote, url), source=url, kind="page",
                        subject=f"{question} {ans}"[:200], root=root)
        note = "Saved to your notes." if got.get("status") == "added" else "Already in your notes."
    except Exception as ex:  # the answer still stands
        note = f"(Could not save the page: {type(ex).__name__}.)"
    return Answer(f"{text}\nSource: {url}\n{note}", "web", [url])


def saved_page(question: str, ans: str, quote: str, url: str) -> str:
    """What the web route files in the bank for this url.

    The bank keeps a one or two sentence summary, not the page. A whole page's summary
    is about the page (cornell.edu's was a news item), so the answer was lost offline.
    Filing the question, answer and quoted line, with "question answer" as the subject
    (ingest's subject= wins over the model), keeps the answer findable and readable offline.
    """
    return (f"Title: {question}\nURL: {url}\n\nQuestion: {question}\nAnswer: {ans}\n"
            f'The page says: "{quote}"\n')


# ---- entry point ------------------------------------------------------------

def answer(question: str, today: date | str | None = None, *, root: Path | None = None,
           _online=None, _web_fns: dict | None = None, _events=None,
           _now: datetime | None = None) -> Answer:
    """Answer one question. today defaults to date.today(); root defaults to the bank dir."""
    t0 = time.monotonic()
    if isinstance(today, str):
        today = date.fromisoformat(today)
    today = today or date.today()
    q = (question or "").strip()
    if not q:
        return Answer("Ask me something.", "none", [], 0.0)

    if route.is_due(q):
        a = _due(q, today, root)
    elif route.is_calendar(q):
        now = _now or (datetime.now() if today == date.today() else datetime.combine(today, datetime.min.time()))
        a = _calendar(q, today, now, _events)
    elif (who := route.person_in(q, _senders(root))):
        a = _person(q, who, today, root)
    elif (name := route.asked_name(q)):
        # Shaped like a person question but nobody by that name is a sender: stop here.
        # A wrong answer about a person is worse than none (thinker ruling).
        a = Answer(f"I have nothing from {name[:1].upper() + name[1:]}.", "person")
    else:
        a = _bank(q, today, root)
        if a is None:
            is_up = _online() if _online else online()
            if is_up:
                a = _web(q, today, root, **(_web_fns or {}))
            else:
                a = Answer(OFFLINE_TEXT, "offline")
    a.seconds = round(time.monotonic() - t0, 2)
    return a
