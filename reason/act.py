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
from datetime import date
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


def waiting() -> bool:
    """True when an action is held for a yes (the window shows Yes/Cancel buttons)."""
    return _held is not None and time.monotonic() - _held.at <= TTL


def reset() -> None:
    global _held
    _held = None


def _words(q: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", (q or "").lower())).strip()


def is_yes(q: str) -> bool:
    return bool(_t("yes").search(_words(q)))


def is_no(q: str) -> bool:
    return bool(_t("no").search(_words(q)))


def parse(q: str) -> dict | None:
    """{"kind": "draft", "name", "gist"} | {"kind": "open", "target"} | None. Code only."""
    q = re.sub(r"\W+$", "", (q or "").strip())
    m = _t("draft").search(q)
    if m:
        return {"kind": "draft", "name": re.sub(r"'s?$", "", m.group(1)), "gist": (m.group(2) or "").strip()}
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


def plan_row(row: dict, deps: dict | None = None):
    """'Open it' after an answer that listed rows (reason/session.py): a row with a link opens
    that page, a calendar row opens Calendar, mail without a link says so. Held for a yes."""
    from .answer import Answer
    d = {"open_app": open_app, "open_page": open_page, **(deps or {})}
    if row.get("kind") == "event":
        return _hold("open_app", lambda: d["open_app"]("Calendar"), say("act", "open_app_preview", app="Calendar"))
    e = row.get("entry") or {}
    url = str(e.get("source") or "")
    if URL_RE.match(url):
        return _hold("open_page", lambda: d["open_page"](url),
                     say("act", "open_page_preview", title=e.get("subject") or url, url=url))
    who = e.get("sender_name") or e.get("sender_address") or "an unknown sender"
    return Answer(say("followup", "no_link", who=who), "act")


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
           deps: dict | None = None):
    """Answer for an action request or a yes/no to a held one; None for anything else."""
    from .answer import Answer
    global _held
    d = {"online": _default_online, "open_app": open_app, "open_page": open_page,
         "save_draft": save_draft, "write_reply": write_reply, **(deps or {})}
    held, _held = (_held if waiting() else None), None  # any new input ends the wait
    if is_yes(question) or is_no(question):
        if held is None:
            return Answer(say("act", "nothing_held"), "act")
        if is_no(question):
            return Answer(say("act", "cancelled"), "act")
        try:
            return Answer(held.run(), "act")
        except Exception as ex:  # report it; nothing is retried
            return Answer(say("act", "failed", why=f"{type(ex).__name__}: {ex}"), "act")
    req = parse(question)
    if req is None:
        return None
    if req["kind"] == "open":
        return _plan_open(req["target"], today or date.today(), root, d)
    return _plan_draft(req["name"], req["gist"], root, d)
