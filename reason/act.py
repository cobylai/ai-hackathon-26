"""Acting: draft a reply, open an app or a saved page, only after showing it and getting a yes.

    handle(question, today, root) -> Answer | None

None means "not an action request and not a yes/no to one": answer() goes on to the
other routes. Otherwise the Answer is either a preview ending in "Say or type yes ...",
with one action held for TTL seconds, or the result of running/cancelling the held one.

The partner's tools do the work: harness.computer.tools.app_open (allowlist, block list,
log), harness.email.search + harness.email.draft.reply (drafts only; there is no send
path anywhere). Drafts are saved only when the signed-in Gmail is TEST_ACCOUNT.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import bank

from . import playbook
from .playbook import say

TEST_ACCOUNT = "ilovelocalai@gmail.com"
TTL = 180.0  # seconds a held action waits for its yes

# Only these, and the harness policy (allow_apps / block_apps) still decides on the yes.
APPS = {"calendar": "Calendar", "notes": "Notes", "finder": "Finder", "files": "Finder",
        "textedit": "TextEdit", "text edit": "TextEdit", "preview": "Preview",
        "calculator": "Calculator"}
APP_LIST = "Calendar, Notes, Finder, TextEdit, Preview and Calculator"
URL_RE = re.compile(r"^(https?|file)://", re.I)



def _t(key: str):
    return playbook.trigger("act", key)


@dataclass
class Held:
    what: str                      # "open_app" | "open_page" | "draft"
    run: Callable[[], str]
    at: float


_held: Held | None = None
_choice: dict | None = None      # a "which one do you mean?" waiting for its title


def waiting() -> bool:
    """True when an action is held for a yes (the window shows Yes/Cancel buttons)."""
    return _held is not None and time.monotonic() - _held.at <= TTL


def reset() -> None:
    global _held, _choice
    _held = None
    _choice = None


def _words(q: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", (q or "").lower())).strip()


def is_yes(q: str) -> bool:
    return bool(_t("yes").search(_words(q)))


def is_no(q: str) -> bool:
    return bool(_t("no").search(_words(q)))


def parse(q: str) -> dict | None:
    """{"kind": "draft" | "calendar" | "remind" | "setup" | "open", ...} | None. Code only."""
    q = re.sub(r"\W+$", "", (q or "").strip())
    m = _t("draft").search(q)
    if m:
        return {"kind": "draft", "name": re.sub(r"'s?$", "", m.group(1)), "gist": (m.group(2) or "").strip()}
    m = playbook.trigger("schedule", "calendar").search(q)
    if m:
        return {"kind": "calendar", "target": m.group(1).strip()}
    m = playbook.trigger("schedule", "remind").search(q)
    if m:
        return {"kind": "remind", "target": (m.group(1) or "").strip(), "when": (m.group(2) or "").strip()}
    m = playbook.trigger("setup", "setup").search(q)
    if m:
        return {"kind": "setup", "target": m.group(1).strip()}
    m = _t("open").search(q)
    if m:
        return {"kind": "open", "target": m.group(1).strip()}
    return None


# ---- the actions (run only after a yes) -------------------------------------

def open_app(app: str) -> str:
    from harness.computer import tools
    out = tools.app_open(app)
    if out.startswith("OK"):
        return say("act", "opened_app", app=app)
    return say("act", "open_app_failed", app=app, why=out)


def open_page(url: str) -> str:
    from harness.computer import direct, policy
    if policy.stopped():
        return say("act", "page_stopped", why=policy.STOPPED_MESSAGE)
    if not URL_RE.match(url):
        return say("act", "page_only_links")
    policy.log_action("Browser", "open_url", url, policy.ALLOW)
    ok, msg = direct.open_path(url)
    return say("act", "opened_page", url=url) if ok else say("act", "open_page_failed", url=url, why=msg)


def _norm_subject(s: str) -> str:
    s = re.sub(r"^\s*((re|fwd?)\s*:\s*)+", "", s or "", flags=re.I)
    return " ".join(s.lower().split())


def gmail_account(page) -> str:
    """The address in the Gmail tab title ("Inbox (3) - a@b.com - Gmail"), or ""."""
    try:
        title = page.title() or ""
    except Exception:
        return ""
    m = re.search(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+", title)
    return m.group(0).lower() if m else ""


def save_draft(to: str, subject: str, body: str) -> str:
    """Reply draft in the newest thread from `to` with this subject. Never sends."""
    from harness.browser.session import get_session
    from harness.email import draft, search
    from harness.email.status import signed_in
    page = get_session().start().page
    if not signed_in(page):
        return say("act", "not_signed_in")
    account = gmail_account(page)
    if account != TEST_ACCOUNT:
        return say("act", "wrong_account", account=account or "an unknown account", test=TEST_ACCOUNT)
    search.search(sender=to)
    rows = search.last_rows()
    if not rows:
        return say("act", "no_thread", to=to)
    want = _norm_subject(subject)
    n = next((r.n for r in rows if _norm_subject(r.subject) == want), rows[0].n)
    out = draft.reply(n, body)
    if not out.startswith("OK"):
        return say("act", "draft_failed", why=out)
    got = out.split("| to", 1)[1].strip().lower() if "| to" in out else ""
    msg = say("act", "draft_saved", to=to, account=TEST_ACCOUNT)
    if got and to.lower() not in got:
        msg += "\n" + say("act", "draft_warning", got=got, to=to)
    return msg


def write_reply(gist: str, e: dict) -> str:
    from llm.client import complete
    who = e.get("sender_name") or e.get("sender_address") or "the sender"
    first = who.split()[0] if who and "@" not in who else "there"
    if first.lower().rstrip(".") in ("prof", "professor", "dr", "mr", "mrs", "ms"):
        first = who
    text = complete(playbook.prompt("act", "draft_prompt").format(
        who=who, subject=e.get("subject") or "(no subject)", summary=e.get("body") or "",
        ask_line=f"They asked: {e['ask']}" if e.get("ask") else "",
        gist=gist or "a short, friendly acknowledgement", first=first),
        system=playbook.prompt("act", "draft_system"), max_tokens=200)
    lines = [ln for ln in text.strip().strip('"').splitlines()
             if not re.match(r"^\s*(subject|to)\s*:", ln, re.I)]
    return "\n".join(lines).strip()


# ---- planning: build the preview and hold the action ------------------------

def _hold(what: str, run: Callable[[], str], preview: str):
    from .answer import Answer
    global _held
    _held = Held(what, run, time.monotonic())
    return Answer(f"{preview}\n{say('act', 'ask_yes')}", "act")


def hold_save(preview: str, run: Callable[[], str]) -> None:
    """Ask before filing a web answer in the notes (finding 17b): a yes runs it, anything else drops it."""
    global _held
    _held = Held("save_note", run, time.monotonic())


def _next_due(e: dict, today: date) -> str:
    """Soonest deadline on or after today ("9999" when none), for picking "the assignment"."""
    days = [str(d.get("date")) for d in e.get("deadlines") or [] if d.get("date")]
    return min((d for d in days if d >= today.isoformat()), default="9999")


def _pick_page(words: str, today: date, root):
    """The bank entry with a link to open. Named words: best match, newest first.
    "the assignment page" alone: the Canvas assignment due soonest (else the newest link)."""
    from bank import store
    if words:
        hits = [e for e in bank.search(words, limit=20, root=root)
                if URL_RE.match(str(e.get("source") or ""))]
        return hits[0] if hits else None
    links = [e for e in store.all_entries(root) if URL_RE.match(str(e.get("source") or ""))]
    if not links:
        return None
    canvas = [e for e in links if e.get("kind") == "canvas"]
    if canvas:
        return min(canvas, key=lambda e: (_next_due(e, today), e.get("sent_date") or ""))
    return max(links, key=lambda e: e.get("sent_date") or "")


def _plan_open(target: str, today: date, root, deps: dict):
    from .answer import Answer
    t = target.lower().strip()
    app = APPS.get(t) or APPS.get(re.sub(r"^(?:apple\s+|mac\s+)", "", t))
    if app:
        return _hold("open_app", lambda: deps["open_app"](app), say("act", "open_app_preview", app=app))
    if not _t("page").search(t):
        return Answer(say("act", "only_apps", apps=APP_LIST), "act")
    generic = ("page", "link", "site", "website", "url", "the", "my", "for", "on", "canvas",
               "assignment", "assignments", "homework", "next")
    words = " ".join(w for w in re.findall(r"[a-z0-9]+", t) if w not in generic)
    e = _pick_page(words, today, root)
    if e is None:
        return Answer(say("act", "no_link", target=target), "act")
    url = str(e["source"])
    return _hold("open_page", lambda: deps["open_page"](url),
                 say("act", "open_page_preview", title=e.get("subject") or url, url=url))


def _saved_copy(e: dict) -> str:
    """The saved bank entry, shown when the thing itself can't be opened."""
    from .answer import _short_date
    who = e.get("sender_name") or e.get("sender_address") or e.get("source") or "unknown"
    return say("open", "saved_copy", who=who, date=_short_date(e.get("sent_date")),
               subject=e.get("subject") or "(no subject)", summary=(e.get("body") or "").strip())


def open_email(e: dict) -> str:
    """Apple Mail (test account) first, works offline; then the Gmail page when online;
    else the saved copy. Run only after a yes."""
    from . import computer
    who = e.get("sender_name") or e.get("sender_address") or "unknown sender"
    if e.get("sender_address") and computer.mail_app_open(e["sender_address"], e.get("subject") or ""):
        return say("open", "opened_mail", who=who, subject=e.get("subject") or "(no subject)")
    url = computer.gmail_url(e)
    if url and _default_online():
        return "\n".join([say("open", "not_in_mail"), open_page(url)])
    return "\n".join([say("open", "cannot_open_mail"), _saved_copy(e)])


def show_event(ev: dict) -> str:
    from . import computer
    if computer.show_event(ev):
        return say("open", "showed_event", title=ev.get("title") or "(no title)")
    return "\n".join([say("open", "event_not_found", title=ev.get("title") or "(no title)"),
                      open_app("Calendar")])


def plan_row(row: dict, deps: dict | None = None):
    """'Open it' after an answer that listed rows (reason/session.py), held for a yes:
    a calendar row shows that event in Calendar, a row with a link opens the page, an email
    opens in Mail (else its Gmail page, else the saved copy), anything else shows the saved copy."""
    from .answer import Answer
    from . import computer
    d = {"open_app": open_app, "open_page": open_page, "open_email": open_email,
         "show_event": show_event, **(deps or {})}
    if row.get("kind") == "event":
        ev = row.get("event") or {}
        start = ev.get("start")
        when = computer.when_text(start, ev.get("all_day")) if isinstance(start, datetime) else str(start or "")
        return _hold("show_event", lambda: d["show_event"](ev),
                     say("open", "show_event_preview", title=ev.get("title") or "(no title)", when=when))
    e = row.get("entry") or {}
    url = str(e.get("source") or "")
    if URL_RE.match(url):
        return _hold("open_page", lambda: d["open_page"](url),
                     say("act", "open_page_preview", title=e.get("subject") or url, url=url))
    if e.get("kind") == "email":
        who = e.get("sender_name") or e.get("sender_address") or "an unknown sender"
        return _hold("open_email", lambda: d["open_email"](e),
                     say("open", "open_mail_preview", who=who, subject=e.get("subject") or "(no subject)"))
    return Answer(_saved_copy(e), "act")


# ---- add to calendar, remind me, set me up (playbooks/schedule.md, setup.md) ---------

GENERIC = set("""the a an my this that it one thing meeting event invite invitation email mail message
about for on to of with from""".split())


def _session_row(target: str, session):
    """(row, None) for "this / that / it / the first one", else (None, None); (None, Answer) when
    it needs a conversation or a choice."""
    from .answer import Answer
    t = target.lower().strip()
    m = re.fullmatch(r"(?:(?:this|that|it)(?:\s+one)?|the\s+(\w+)(?:\s+one)?)", t)
    if not m:
        return None, None
    from .session import ORDINALS, _row
    if m.group(1) is not None and m.group(1) not in ORDINALS:
        return None, None
    if session is None or not session.rows:
        return None, Answer(say("schedule", "which_this"), "act")
    idx = ORDINALS.get(m.group(1)) if m.group(1) else None
    row, why = _row(session, idx)
    if why is not None:
        why.route = "act"
        return None, why
    return row, None


def _find_entry(target: str, root, today: date, dated: bool):
    """A bank entry for "Felix's meeting", "the lab report", "band practice". Code only."""
    from . import computer
    t = target.strip()
    pool = []
    m = re.match(r"^([A-Za-z][A-Za-z\-]+)'s?\s+(.+)$", t)
    if m:
        mine = bank.by_person(m.group(1), root=root)
        words = [w for w in re.findall(r"[a-z0-9]+", m.group(2).lower()) if w not in GENERIC]
        pool = [e for e in mine if all(w in (str(e.get("subject")) + " " + str(e.get("body")) + " "
                                             + str(e.get("ask"))).lower() for w in words)] or mine
    else:
        words = " ".join(w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in GENERIC)
        pool = bank.search(words, limit=20, root=root) if words else []
    pool = [e for e in pool if e.get("kind") != "me"]
    if re.search(r"\b(meeting|meet|appointment|event)\b", t.lower()):
        # "Greta's meeting" means her meeting, not whatever she wrote last (playbooks/schedule.md)
        from . import suggest
        meetings = [e for e in pool if suggest.is_meeting(e)]
        pool = meetings or pool
    if dated:
        with_date = [e for e in pool if computer._dated(e)]
        if with_date:
            pool = with_date
    return pool[0] if pool else None


def _entry_from_row(row: dict) -> dict:
    if row.get("kind") == "event":
        ev = row.get("event") or {}
        start = ev.get("start")
        d = start.date().isoformat() if hasattr(start, "date") else str(start)[:10]
        t = f"{start:%H:%M}" if hasattr(start, "hour") and not ev.get("all_day") else None
        return {"subject": ev.get("title"), "deadlines": [{"phrase": "", "date": d, "time": t}],
                "kind": "event", "sender_name": "your calendar"}
    return row.get("entry") or {}


def _plan_calendar(target: str, today: date, root, session, deps: dict):
    from .answer import Answer
    from . import computer
    row, why = _session_row(target, session)
    if why is not None:
        return why
    if row is not None and row.get("kind") == "event":
        return Answer(say("schedule", "already_on_calendar",
                          title=(row.get("event") or {}).get("title") or "(no title)"), "act")
    e = (row or {}).get("entry") if row else _find_entry(target, root, today, dated=True)
    if not e:
        return Answer(say("schedule", "nothing_found", target=target), "act")
    ev = computer.event_for(e, today)
    if ev is None:
        return Answer(say("schedule", "no_time", subject=e.get("subject") or target), "act")
    import applecal
    where = say("schedule", "at_place", place=ev["location"]) if ev["location"] else ""
    when = computer.when_text(ev["start"], ev["all_day"])
    if not ev["all_day"]:
        when += "–" + computer.when_text(ev["end"]).split(" ")[-1]
    return _hold("add_event", lambda: deps["add_event"](ev),
                 say("schedule", "event_preview", title=ev["title"], when=when, where=where,
                     calendar=applecal.calendar_name()))


def _plan_reminder(target: str, when: str, today: date, root, session, deps: dict):
    from .answer import Answer
    from . import computer
    row, why = _session_row(target or "this", session)
    if why is not None:
        return why
    e = _entry_from_row(row) if row else _find_entry(target, root, today, dated=True)
    if not e:
        return Answer(say("schedule", "nothing_due", target=target), "act")
    r = computer.reminder_for(e, when, today)
    if r is None:
        return Answer(say("schedule", "no_date", subject=e.get("subject") or target), "act")
    return _hold("add_reminder", lambda: deps["add_reminder"](r),
                 say("schedule", "reminder_preview", name=r["name"],
                     when=computer.when_text(r["remind_at"]), due=computer.when_text(r["due"])))


def do_add_event(ev: dict) -> str:
    from . import computer
    import applecal
    computer.add_event(ev)
    return say("schedule", "event_added", title=ev["title"], calendar=applecal.calendar_name())


def do_add_reminder(r: dict) -> str:
    from . import computer
    from applecal import write
    try:
        computer.add_reminder(r)
    except Exception as e:  # Reminders not running is the usual one: "Connection is invalid. (-609)"
        if "-609" in str(e) or "Connection is invalid" in str(e):
            return say("schedule", "reminders_closed")
        raise
    return say("schedule", "reminder_added", name=r["name"], list=write.REMINDER_LIST)


def _plan_setup(target: str, today: date, root, deps: dict):
    """The coursework or page for <thing>, its related mail and any note, opened together."""
    from .answer import Answer
    from bank import me
    words = [w for w in re.findall(r"[a-z0-9]+", target.lower()) if w not in GENERIC]
    if not words:
        return Answer(say("setup", "what_thing", target=target), "act")
    hits = bank.search(" ".join(words), limit=20, root=root)
    hay = lambda e: " ".join(str(e.get(k) or "") for k in ("subject", "body", "ask", "course")).lower()
    full = [e for e in hits if all(w in hay(e) for w in words)]
    pages = [e for e in (full or hits) if URL_RE.match(str(e.get("source") or ""))]
    named = [p for p in pages if all(w in str(p.get("subject") or "").lower() for w in words)]
    choices = named if len(named) > 1 else (pages if not named and len(pages) > 1 else [])
    if choices:
        names = list(dict.fromkeys(p.get("subject") or "?" for p in choices))[:3]
        global _choice
        _choice = {"target": target, "names": names}  # the next message may be one of these
        return Answer(say("setup", "which_one", options="; ".join(names)), "act")
    page = named[0] if named else (pages[0] if pages else None)
    mails = [e for e in (full or hits) if e.get("kind") == "email"][:2]
    notes = [n for n in me.notes(root) if any(w in hay(n) for w in words)][:2]
    if not page and not mails and not notes:
        return Answer(say("setup", "nothing_found", target=target), "act")
    lines = [say("setup", "preview_head", target=target)]
    if page:
        lines.append(say("setup", "item_page", title=page.get("subject") or page["source"]))
    for m in mails:
        lines.append(say("setup", "item_mail", who=m.get("sender_name") or m.get("sender_address") or "?",
                         subject=m.get("subject") or "(no subject)"))
    for n in notes:
        lines.append(say("setup", "item_note", note=n.get("body") or n.get("subject") or ""))

    def run():
        out = []
        if page:
            out.append(deps["open_page"](str(page["source"])))
        for m in mails:
            out.append(deps["open_email"](m))
        for n in notes:
            out.append(say("setup", "note_line", note=n.get("body") or n.get("subject") or ""))
        return "\n".join(out)
    return _hold("setup", run, "\n".join(lines))


def _plan_draft(name: str, gist: str, root, deps: dict):
    from .answer import Answer
    who_cap = name[:1].upper() + name[1:]
    if not deps["online"]():
        return Answer(say("act", "needs_net"), "act")
    mails = [e for e in bank.by_person(name, root=root)
             if e.get("kind") == "email" and e.get("sender_address")]
    if not mails:
        return Answer(say("act", "no_sender", name=who_cap), "act")
    e = mails[0]
    to, subject = e["sender_address"], e.get("subject") or ""
    try:
        body = deps["write_reply"](gist, e)
    except Exception as ex:  # model server down, budget, ...
        return Answer(say("act", "cannot_write", why=f"{type(ex).__name__}: {ex}"), "act")
    if not body:
        return Answer(say("act", "cannot_write", why="the model wrote nothing"), "act")
    who = e.get("sender_name") or to
    preview = "\n".join([say("act", "draft_preview_head", account=TEST_ACCOUNT),
                         say("act", "draft_preview_to", who=who, to=to),
                         say("act", "draft_preview_subject", subject=subject), "", body, ""])
    return _hold("draft", lambda: deps["save_draft"](to, subject, body), preview)


def _default_online() -> bool:
    from .answer import online
    return online()


def handle(question: str, today: date | None = None, root: Path | None = None, *,
           deps: dict | None = None, session=None):
    """Answer for an action request or a yes/no to a held one; None for anything else."""
    from .answer import Answer
    global _held, _choice
    d = {"online": _default_online, "open_app": open_app, "open_page": open_page,
         "save_draft": save_draft, "write_reply": write_reply, "open_email": open_email,
         "add_event": do_add_event, "add_reminder": do_add_reminder, **(deps or {})}
    held, _held = (_held if waiting() else None), None  # any new input ends the wait
    choice, _choice = _choice, None  # a "which one" lasts for the next message only
    if is_yes(question) or is_no(question):
        if held is None:
            if choice is not None and is_no(question):
                return Answer(say("act", "cancelled"), "act")
            return Answer(say("act", "nothing_held"), "act")
        if is_no(question):
            return Answer(say("act", "cancelled"), "act")
        try:
            return Answer(held.run(), "act")
        except Exception as ex:  # report it; nothing is retried
            return Answer(say("act", "failed", why=f"{type(ex).__name__}: {ex}"), "act")
    today = today or date.today()
    if choice is not None:  # the answer to "Which one do you mean: A; B?" is one of the titles
        said = _words(question).split()
        names = [n for n in choice["names"] if said and all(w in _words(n) for w in said)]
        if len(names) == 1:
            return _plan_setup(names[0], today, root, d)
        if len(names) > 1:  # still ambiguous: ask again rather than guess (playbooks/setup.md step 3)
            _choice = {"target": choice["target"], "names": names}
            return Answer(say("setup", "which_one", options="; ".join(names)), "act")
    req = parse(question)
    if req is None:
        return None
    if req["kind"] == "open":
        return _plan_open(req["target"], today, root, d)
    if req["kind"] == "calendar":
        return _plan_calendar(req["target"], today, root, session, d)
    if req["kind"] == "remind":
        return _plan_reminder(req["target"], req["when"], today, root, session, d)
    if req["kind"] == "setup":
        return _plan_setup(req["target"], today, root, d)
    return _plan_draft(req["name"], req["gist"], root, d)
