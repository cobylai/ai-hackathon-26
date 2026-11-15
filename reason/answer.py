"""answer(question): bank first, browser only when the bank falls short.

Routes, picked in code (reason/route.py), in this order:
  followup -> reason/session.py: "and tomorrow?", "and Hugo?", "the first one", "open it",
              only when a session is passed in; code only, no model call
  discover -> discover/: proposes facts from the bank and calendar, writes only on a yes
  remember, forget, about_me, people -> reason/me.py: notes about the user and person pages, no model call
  catchup -> reason/catchup.py: today's calendar, due soon, recent asks; no model call
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

from . import playbook, route
from .playbook import say

OFFLINE_TEXT = say("web", "offline")
PERSON_LIMIT = 8
EVERYONE_LIMIT = 12
SEARCH_LIMIT = 5
GATHER_SECONDS = 60

# Wording and prompts come from playbooks/<route>.md. STEPS is how many numbered steps
# each playbook lists; the code below runs them in that order (a test checks the count).
STEPS = {"about": 5, "followup": 5, "discover": 6, "act": 5, "remember": 4, "people": 4, "catchup": 5, "due": 5, "calendar": 4, "person": 6, "bank": 4, "web": 6, "chat": 3, "open": 4, "schedule": 5, "setup": 5, "suggest": 5, "compose": 5, "send": 5}
PERSON_SYSTEM = playbook.prompt("person", "person_system")
PERSON_PROMPT = playbook.prompt("person", "person_prompt")
PERSON_HINT = playbook.prompt("person", "person_hint")


@dataclass
class Answer:
    text: str
    route: str  # followup | discover | act | remember | forget | about_me | people | catchup | due | calendar | person | bank | web | offline | not_found
    sources: list[str] = field(default_factory=list)  # bank entry paths, or one url
    seconds: float = 0.0
    # What the answer listed, for follow-ups ("the first one", "who sent that?"):
    # {"kind": "entry", "entry": dict, "date", "time", "line"} or {"kind": "event", "event": dict, "line"}
    rows: list[dict] = field(default_factory=list)
    # Suggested next steps under the answer (reason/suggest.py, at most 2) and a draft box
    # (reason/compose.py): {"id", "to", "to_name", "subject", "body", "used", "kind"}.
    suggestions: list[dict] = field(default_factory=list)
    draft: dict | None = None
    # A send preview (reason/send.py, playbooks/send.md): {"token", "to", "subject", "body", ...}.
    # The window shows it with a Send button; nothing is sent without that click.
    send: dict | None = None
    # The agent loop's steps (reason/agent.py, FLUX_AGENT=1 only): [{"n", "action", "arg",
    # "note", "tokens", "seconds", "valid"}], shown as "How I got this" in the window.
    trace: list[dict] = field(default_factory=list)
    agent: dict | None = None
    choices: list | None = None  # buttons [[label, words]] (reason/tour.py: examples, Next / Back / Stop)


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
    if e.get("kind") == "me":
        return say("remember", "note_label", date=_short_date(e.get("sent_date")))
    if e.get("kind") == "page":
        return str(e.get("source") or "a saved page")
    who = e.get("sender_name") or e.get("sender_address") or "unknown sender"
    return f"{who}, {_short_date(e.get('sent_date'))}"


def _with_source(text: str, entries: list[dict]) -> str:
    labels = list(dict.fromkeys(source_label(e) for e in entries))
    return f"{text.strip()}\n{say('RULES', 'source', labels='; '.join(labels))}" if labels else text.strip()


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
    head = say("due", "head_day", label=label) if start == end else say(
        "due", "head_range", label=label, start=_short_date(start.isoformat()),
        end=_short_date(end.isoformat()))
    if not rows:
        return Answer(say("due", "nothing_due", label=label), "due")
    lines, items = [head], []
    for r in rows:
        e = r["entry"]
        what = (e.get("ask") or e.get("body") or e.get("subject") or "").strip().rstrip(".")
        when = route._day(date.fromisoformat(r["date"])) if start != end else ""
        t = _time(r.get("time"))
        stamp = " ".join(x for x in (when, t) if x)
        lines.append(say("due", "row", when=stamp + "  " if stamp else "", what=what,
                         source=source_label(e)))
        items.append({"kind": "entry", "entry": e, "date": r["date"], "time": r.get("time"),
                      "line": lines[-1]})
        summary = (e.get("body") or "").strip()
        if summary and summary.rstrip(".") != what:  # the summary carries amounts etc.
            lines.append(f"    {summary}")
    paths = list(dict.fromkeys(r["entry"]["path"] for r in rows))
    return Answer("\n".join(lines), "due", paths, rows=items)


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
    line = say("calendar", "row", when=" ".join(x for x in (day, when) if x),
               title=e.get("title") or "(no title)", where=where)
    return f"{line} {say('calendar', 'row_cal', calendar=e['calendar'])}" if e.get("calendar") else line


def _calendar(question: str, today: date, now: datetime, events_fn) -> Answer:
    """Apple Calendar events, listed by code. No model call."""
    import applecal
    events_fn = events_fn or applecal.events
    src = say("calendar", "source", calendar=applecal.source_label())
    try:
        if route.is_next_event(question):
            evs = [e for e in events_fn(today, today + timedelta(days=NEXT_EVENT_DAYS))
                   if (e["start"] >= now if not e.get("all_day") else e["start"].date() >= now.date())]
            if not evs:
                return Answer(f"{say('calendar', 'none_next', days=NEXT_EVENT_DAYS)}\n{src}", "calendar")
            src = say("calendar", "source", calendar=applecal.source_label(evs[:1]))
            line = _event_line(evs[0], True)
            return Answer(f"{say('calendar', 'next_head')}\n{line}\n{src}", "calendar",
                          rows=[{"kind": "event", "event": evs[0], "line": line}])
        start, end, label = route.due_range(question, today)
        evs = events_fn(start, end)
    except applecal.CalendarError as e:
        return Answer(say("calendar", "error", error=e), "calendar")
    if not evs:
        return Answer(f"{say('calendar', 'nothing', label=label)}\n{src}", "calendar")
    head = (say("calendar", "head_day", label=label) if start == end else
            say("calendar", "head_range", label=label, start=_short_date(start.isoformat()),
                end=_short_date(end.isoformat())))
    items = [{"kind": "event", "event": e, "line": _event_line(e, start != end)} for e in evs]
    src = say("calendar", "source", calendar=applecal.source_label(evs))
    lines = [head] + [r["line"] for r in items]
    return Answer("\n".join(lines) + "\n" + src, "calendar", rows=items)


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
    lines, items = [], []
    for e in entries:
        who_ = f"{e.get('sender_name') or e.get('sender_address')}, " if many else ""
        row = dict(who=who_, date=_short_date(e.get("sent_date")), subject=e.get("subject") or "(no subject)")
        ask = (e.get("ask") or "").strip()
        if ask:
            lines.append(say("person", "ask_row", ask=ask, **row))
        else:
            lines.append(say("person", "no_ask_row", summary=(e.get("body") or "").strip(), **row))
        items.append({"kind": "entry", "entry": e, "line": lines[-1]})
    name = entries[0].get("sender_name") or who.title()
    top = say("person", "ask_head",
              name=" / ".join(dict.fromkeys(e.get("sender_name") or "" for e in entries)) if many else name)
    return Answer(_with_source("\n".join([top] + lines), entries), "person", [e["path"] for e in entries],
                  rows=items)


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
        text = say("person", "model_empty", name=display)
    return Answer(_with_source(text, used), "person", [e["path"] for e in used],
                  rows=[{"kind": "entry", "entry": e, "line": e.get("subject") or ""} for e in used])


def _everyone(today: date, root) -> Answer:
    """Every sender's asks still open (deadline today or later, or none), newest first. No model call."""
    rows = []
    for e in sorted(store.all_entries(root), key=lambda e: e.get("sent_date") or "", reverse=True):
        if e.get("kind") != "email" or not (e.get("ask") or "").strip():
            continue
        dates = [d["date"] for d in e.get("deadlines") or [] if d.get("date")]
        if dates and max(dates) < today.isoformat():
            continue
        rows.append(e)
    if not rows:
        return Answer(say("person", "no_open_asks"), "person")
    shown = rows[:EVERYONE_LIMIT]
    lines = [say("person", "everyone_head", count=len(rows))]
    lines += [say("person", "everyone_row", who=e.get("sender_name") or e.get("sender_address"),
                  date=_short_date(e.get("sent_date")), subject=e.get("subject") or "(no subject)",
                  ask=e["ask"].strip()) for e in shown]
    return Answer(_with_source("\n".join(lines), shown), "person", [e["path"] for e in shown])


def _near_person(question: str, near: tuple[str, list[str]], today: date, root) -> Answer:
    """A misheard name close to exactly one sender: that sender's asks, saying what was heard."""
    heard, names = near
    people_ = list(dict.fromkeys(e.get("sender_name") or e.get("sender_address")
                                 for n in names for e in bank.by_person(n, root=root)
                                 if e.get("kind") == "email"))
    if len(people_) != 1:
        return Answer(say("person", "did_you_mean", heard=heard, names=" or ".join(people_ or names)), "person")
    a = _person_asks(question, names[0], root)
    a.text = say("person", "heard", heard=heard, name=people_[0]) + "\n" + a.text
    return a


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
    from sufficiency.junk import looks_blocked
    if search_fn is None or open_fn is None:
        from harness.search import tools  # loads Playwright; web route only
        from sufficiency import websearch  # partner's engine.search, then Bing
        search_fn = search_fn or websearch.search
        open_fn = open_fn or tools.open_page
    ingest_fn = ingest_fn or bank.ingest
    r = gather(question, search_fn, open_fn, today=today, max_seconds=GATHER_SECONDS)
    if not r.found or not r.source:
        return Answer(r.message or say("web", "not_found"), "not_found",
                      list(r.opened))
    url = r.source.url
    ans = (r.answer or "").strip()
    quote = (r.evidence or "").strip().strip('"“” ')
    if looks_blocked(f"{ans}\n{quote}"):  # bot-check or error page: no answer, nothing filed
        return Answer("I couldn't find that on the web.", "not_found", list(r.opened))
    text = ans + (f'\n"{quote}"' if quote and quote.lower() not in ans.lower() else "")

    def save() -> str:
        # A web answer is a reference note, not one of the reader's commitments: file it with
        # today's date and no deadlines, so a page's dates (1797-08-30 for Mary Shelley) never
        # become due items (finding 17b).
        try:
            got = ingest_fn(saved_page(question, ans, quote, url), source=url, kind="page",
                            subject=f"{question} {ans}"[:200], today=today, sent_date=today,
                            deadlines=[], root=root)
            return say("web", "saved") if got.get("status") == "added" else say("web", "already_saved")
        except Exception as ex:  # the answer still stands
            return say("web", "save_failed", error=type(ex).__name__)

    from . import act
    act.hold_save(say("web", "save_ask"), save)  # filed only after a yes (finding 17b)
    return Answer(f"{text}\n{say('RULES', 'source', labels=url)}\n{say('web', 'save_ask')}", "web", [url])


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
           _now: datetime | None = None, session=None) -> Answer:
    """Answer one question. today defaults to date.today(); root defaults to the bank dir.
    session (reason/session.py) keeps the last answer for follow-ups; None means no follow-ups."""
    t0 = time.monotonic()
    if isinstance(today, str):
        today = date.fromisoformat(today)
    today = today or date.today()
    q = (question or "").strip()
    if not q:
        return Answer(say("RULES", "empty_question"), "none", [], 0.0)

    import discover  # a held discovery question takes its yes / no / skip first
    from . import act, catchup, chat, compose, me, suggest  # drafts and actions first: they name senders
    from . import send  # playbooks/send.md: "send it" only ever shows a preview
    follow, asked = None, q  # asked: as the user said it, for the saved turn
    from . import tour  # playbooks/about.md: "what's Flux" and the guided tour, before follow-ups
    sending = send.handle(q)  # playbooks/send.md: "send it" only ever shows a preview
    held = discover.waiting() or act.waiting() or compose.waiting()
    tour_a = None if (held or sending is not None) else tour.handle(
        q, today, root, session=session, run=answer, events=_events)
    if sending is not None:
        follow = ("answer", sending)
    elif session is not None and tour_a is None and not held:
        from .session import resolve  # playbooks/followup.md: code only, no model call
        follow = resolve(q, session, today, root)
        if follow and follow[0] == "question":
            q = follow[1]  # "and Hugo?" -> the last person question, with Hugo
    if tour_a is not None:
        a = tour_a
    elif follow and follow[0] == "answer":
        a = follow[1]
    elif follow and follow[0] == "due":
        a = _due(follow[1], today, root)
    elif follow and follow[0] == "calendar":
        now = _now or (datetime.now() if today == date.today() else datetime.combine(today, datetime.min.time()))
        a = _calendar(follow[1], today, now, _events)
    elif (got := discover.handle(q, today, root)) is not None:
        a = got
    elif (got := compose.handle(q, today, root, session=session, events_fn=_events)) is not None:
        a = got  # playbooks/compose.md: a draft box, never sent ("... in Gmail" goes to act)
    elif (got := act.handle(q, today, root, session=session)) is not None:
        a = got
    elif (got := me.handle(q, today, root)) is not None:  # remember / forget / about_me / people
        a = got
    elif (got := catchup.handle(q, today, root, _events)) is not None:  # reason/catchup.py
        a = got
    elif route.is_due(q):
        a = _due(q, today, root)
    elif route.is_calendar(q):
        now = _now or (datetime.now() if today == date.today() else datetime.combine(today, datetime.min.time()))
        a = _calendar(q, today, now, _events)
    elif (who := route.person_in(q, senders := _senders(root))):
        a = _person(q, who, today, root)
    elif route.is_everyone(q):  # "what did everyone ask me": asks across senders, code only
        a = _everyone(today, root)
    elif route.is_person_shaped(q) and (near := route.near_person(q, senders)):
        a = _near_person(q, near, today, root)  # "Elena asked me" -> Lena (misheard by voice)
    elif (name := route.asked_name(q)):
        # Shaped like a person question but nobody by that name is a sender: stop here.
        # A wrong answer about a person is worse than none (thinker ruling).
        a = Answer(say("person", "no_sender", name=name[:1].upper() + name[1:]), "person")
    elif (got := chat.handle(q)) is not None:  # greetings and mic checks never reach the web
        a = got
    else:
        a = _bank(q, today, root)
        if a is None:
            from . import agent  # FLUX_AGENT=1 only: a bounded plan for what no route covers
            if agent.wants(q):
                a = agent.answer(q, today, root, session=session, events_fn=_events,
                                 online_fn=_online or online, web_fns=_web_fns)
        if a is None and not route.web_ok(q):  # web only for clear factual questions (RULES 9)
            a = Answer(say("web", "personal" if playbook.trigger("web", "personal").search(q)
                           else "unclear"), "not_found")
        if a is None:
            is_up = _online() if _online else online()
            if is_up:
                a = _web(q, today, root, **(_web_fns or {}))
            else:
                a = Answer(OFFLINE_TEXT, "offline")
    try:
        a.suggestions = suggest.for_answer(a, session, today, root, _events)  # playbooks/suggest.md
    except Exception:  # a suggestion never breaks the answer
        a.suggestions = []
    a.seconds = round(time.monotonic() - t0, 2)
    if session is not None:
        session.record(q, a, root, asked=asked)
    return a
