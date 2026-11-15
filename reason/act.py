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

TEST_ACCOUNT = "ilovelocalai@gmail.com"
TTL = 180.0  # seconds a held action waits for its yes

# Only these, and the harness policy (allow_apps / block_apps) still decides on the yes.
APPS = {"calendar": "Calendar", "notes": "Notes", "finder": "Finder", "files": "Finder",
        "textedit": "TextEdit", "text edit": "TextEdit", "preview": "Preview",
        "calculator": "Calculator"}
APP_LIST = "Calendar, Notes, Finder, TextEdit, Preview and Calculator"
PAGE_WORDS = re.compile(r"\b(page|link|site|website|assignment|canvas|syllabus|url)\b", re.I)
URL_RE = re.compile(r"^(https?|file)://", re.I)

ASK_YES = "Say or type yes to go ahead, no to cancel."
CANCELLED = "Cancelled. Nothing was done."
NOTHING_HELD = "There's nothing waiting for a yes."
NEEDS_NET = "Drafting a reply needs a connection, and the Mac is offline. Nothing was drafted."

DRAFT_SYSTEM = ("You write short, plain email replies for a student. You write only the reply "
                "body. You never add facts that were not given.")
DRAFT_PROMPT = """Write the student's reply to this email.

EMAIL FROM {who}
Subject: {subject}
Summary: {summary}
{ask_line}
WHAT THE REPLY SHOULD SAY: {gist}

Write one to three short sentences. Start with "Hi {first}," on its own line. No subject line, no signature, no placeholders."""

_DRAFT = re.compile(
    r"^(?:please\s+|can you\s+|could you\s+)?(?:(?:draft|write)\s+(?:a\s+|an\s+)?(?:quick\s+|short\s+)?"
    r"(?:reply|response|answer|email)(?:\s+back)?|reply)\s+to\s+([A-Za-z][A-Za-z'\-]*)"
    r"(?:'s\s+(?:email|message|mail))?"
    r"(?:[\s,]+(?:saying|that says|to say|telling (?:him|her|them)|that)\s+(.+?))?[\s.!?]*$", re.I)
_OPEN = re.compile(
    r"^(?:please\s+|can you\s+|could you\s+|muse,?\s+)?(?:open|launch|pull up|bring up)\s+(?:up\s+)?"
    r"(?:my\s+|the\s+)?(.+?)(?:\s+app)?(?:\s+please)?[\s.!?]*$", re.I)

YES_WORDS = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "do it", "go ahead", "confirm",
             "yes please", "please do", "yes do it", "go for it"}
NO_WORDS = {"no", "nope", "cancel", "stop", "dont", "don't", "no thanks", "never mind", "nevermind",
            "cancel it", "no dont", "no don't"}


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
    return _words(q) in YES_WORDS


def is_no(q: str) -> bool:
    return _words(q) in NO_WORDS


def parse(q: str) -> dict | None:
    """{"kind": "draft", "name", "gist"} | {"kind": "open", "target"} | None. Code only."""
    q = (q or "").strip()
    m = _DRAFT.match(q)
    if m:
        return {"kind": "draft", "name": re.sub(r"'s?$", "", m.group(1)), "gist": (m.group(2) or "").strip()}
    m = _OPEN.match(q)
    if m:
        return {"kind": "open", "target": m.group(1).strip()}
    return None


# ---- the actions (run only after a yes) -------------------------------------

def open_app(app: str) -> str:
    from harness.computer import tools
    out = tools.app_open(app)
    if out.startswith("OK"):
        return f"Opened {app}."
    return f"I couldn't open {app}: {out}"


def open_page(url: str) -> str:
    from harness.computer import direct, policy
    if policy.stopped():
        return f"I couldn't open the page: {policy.STOPPED_MESSAGE}"
    if not URL_RE.match(url):
        return "I only open web or file links."
    policy.log_action("Browser", "open_url", url, policy.ALLOW)
    ok, msg = direct.open_path(url)
    return f"Opened {url}." if ok else f"I couldn't open {url}: {msg}"


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
        return "Gmail isn't signed in, so nothing was drafted (run: harness login https://mail.google.com)."
    account = gmail_account(page)
    if account != TEST_ACCOUNT:
        return (f"Gmail is signed in as {account or 'an unknown account'}, not {TEST_ACCOUNT}. "
                "I only save drafts in the test account, so nothing was drafted.")
    search.search(sender=to)
    rows = search.last_rows()
    if not rows:
        return f"I couldn't find an email from {to} in Gmail, so nothing was drafted."
    want = _norm_subject(subject)
    n = next((r.n for r in rows if _norm_subject(r.subject) == want), rows[0].n)
    out = draft.reply(n, body)
    if not out.startswith("OK"):
        return f"The draft wasn't saved: {out}"
    got = out.split("| to", 1)[1].strip().lower() if "| to" in out else ""
    msg = f"Saved a reply draft to {to} in {TEST_ACCOUNT}'s Drafts. It was not sent."
    if got and to.lower() not in got:
        msg += f"\nWARNING: Gmail addressed the draft to {got}, not {to}. Check it in Drafts."
    return msg


def write_reply(gist: str, e: dict) -> str:
    from llm.client import complete
    who = e.get("sender_name") or e.get("sender_address") or "the sender"
    first = who.split()[0] if who and "@" not in who else "there"
    if first.lower().rstrip(".") in ("prof", "professor", "dr", "mr", "mrs", "ms"):
        first = who
    text = complete(DRAFT_PROMPT.format(
        who=who, subject=e.get("subject") or "(no subject)", summary=e.get("body") or "",
        ask_line=f"They asked: {e['ask']}" if e.get("ask") else "",
        gist=gist or "a short, friendly acknowledgement", first=first),
        system=DRAFT_SYSTEM, max_tokens=200)
    lines = [ln for ln in text.strip().strip('"').splitlines()
             if not re.match(r"^\s*(subject|to)\s*:", ln, re.I)]
    return "\n".join(lines).strip()


# ---- planning: build the preview and hold the action ------------------------

def _hold(what: str, run: Callable[[], str], preview: str):
    from .answer import Answer
    global _held
    _held = Held(what, run, time.monotonic())
    return Answer(f"{preview}\n{ASK_YES}", "act")


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
        return _hold("open_app", lambda: deps["open_app"](app), f"I'll open {app}.")
    if not PAGE_WORDS.search(t):
        return Answer(f"I can only open {APP_LIST}, or a page saved in the bank.", "act")
    generic = ("page", "link", "site", "website", "url", "the", "my", "for", "on", "canvas",
               "assignment", "assignments", "homework", "next")
    words = " ".join(w for w in re.findall(r"[a-z0-9]+", t) if w not in generic)
    e = _pick_page(words, today, root)
    if e is None:
        return Answer(f"I don't have a saved link for {target}.", "act")
    url = str(e["source"])
    return _hold("open_page", lambda: deps["open_page"](url),
                 f"I'll open this page in your browser:\n{e.get('subject') or url}\n{url}")


def _plan_draft(name: str, gist: str, root, deps: dict):
    from .answer import Answer
    who_cap = name[:1].upper() + name[1:]
    if not deps["online"]():
        return Answer(NEEDS_NET, "act")
    mails = [e for e in bank.by_person(name, root=root)
             if e.get("kind") == "email" and e.get("sender_address")]
    if not mails:
        return Answer(f"I have nothing from {who_cap}, so I can't find an email to reply to.", "act")
    e = mails[0]
    to, subject = e["sender_address"], e.get("subject") or ""
    try:
        body = deps["write_reply"](gist, e)
    except Exception as ex:  # model server down, budget, ...
        return Answer(f"I couldn't write that reply ({type(ex).__name__}: {ex}). Nothing was drafted.", "act")
    if not body:
        return Answer("I couldn't write that reply. Nothing was drafted.", "act")
    who = e.get("sender_name") or to
    preview = (f"I'll save this reply as a draft in {TEST_ACCOUNT}. It won't be sent.\n"
               f"To: {who} <{to}>\nSubject: Re: {subject}\n\n{body}\n")
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
            return Answer(NOTHING_HELD, "act")
        if is_no(question):
            return Answer(CANCELLED, "act")
        try:
            return Answer(held.run(), "act")
        except Exception as ex:  # report it; nothing is retried
            return Answer(f"That didn't work: {type(ex).__name__}: {ex}", "act")
    req = parse(question)
    if req is None:
        return None
    if req["kind"] == "open":
        return _plan_open(req["target"], today or date.today(), root, d)
    return _plan_draft(req["name"], req["gist"], root, d)
