"""Discovery: explore, propose, confirm, review. Wording: playbooks/discover.md.

    handle(question, today, root, deps=None) -> Answer | None

"discover" starts a run: when online the mail sync runs first, then the bank and Apple
Calendar are read, propose.candidates() finds patterns, and at most MAX_QUESTIONS
unanswered ones are asked, one at a time, each with the entries it came from.
While a question is held: yes writes it (bank.remember, people.set_fact,
people.set_relation), no records it so it is never asked again, skip leaves it for the
next run, stop ends the run. Any other input ends the run too (the held question counts
as skipped). "what have you learned" lists confirmed facts; "unlearn N" removes one.
Nothing about the user is written without a yes (playbooks/RULES.md rule 7).
"""
from __future__ import annotations

import importlib.util
import re
from datetime import date, timedelta
from pathlib import Path

import bank
from bank import people, store
from reason import playbook
from reason.playbook import say

from . import propose, state

MAX_QUESTIONS = 10
CAL_BACK, CAL_AHEAD = 56, 28   # days of calendar read around today
SHOW_SOURCES = 5
RELATION_ENTRIES = 6
SYNC_DAYS = 7
SYNC_EVERY = 30 * 60  # seconds: discovery runs the mail sync at most this often

_run: dict | None = None      # {"queue": [candidate], "n": int, "yes": int, "no": int, "skip": int}


def waiting() -> bool:
    """True when a discovery question is held (the window shows Yes / No / Skip)."""
    return bool(_run and _run["queue"])


def reset() -> None:
    global _run
    _run = None


def _t(key: str):
    return playbook.trigger("discover", key)


def _words(q: str) -> str:
    from reason import route
    t = route._lead(q or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", t)).strip()


# ---- explore ----------------------------------------------------------------

def _default_online() -> bool:
    from reason.answer import online
    return online()


def _default_sync(root) -> int:
    """The existing mail sync (scripts/sync_email.py), into this bank. Returns entries added."""
    p = Path(__file__).resolve().parent.parent / "scripts" / "sync_email.py"
    spec = importlib.util.spec_from_file_location("muse_sync_email", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rs = mod.sync(SYNC_DAYS, lambda *a, **k: bank.ingest(*a, root=root, **k))
    return sum(r.get("status") == "added" for r in rs)


def _default_events(start: date, end: date):
    import applecal
    return applecal.events(start, end)


def _default_relation(name: str, entries: list[dict]) -> str | None:
    """Bonsai's guess at how name relates to the user, checked in code. Never written
    without a yes; None when the model is down or the reply isn't a short relation."""
    from llm import client
    from reason.answer import note_block
    notes = "\n\n".join(note_block(i + 1, e) for i, e in enumerate(entries[:RELATION_ENTRIES]))
    try:
        got = client.complete_json(playbook.prompt("discover", "relation_prompt").format(name=name, notes=notes),
                                   system=playbook.prompt("discover", "relation_system"), max_tokens=60,
                                   json_schema_hint=playbook.prompt("discover", "relation_hint"),
                                   sampling={"temperature": 0.0})
    except Exception:
        return None
    return clean_relation(got.get("relation") if isinstance(got, dict) else None, name)


_BAD_REL = {"unknown", "none", "n/a", "sender", "recipient", "person", "someone", "contact", "user"}


def clean_relation(rel, name: str = "") -> str | None:
    rel = re.sub(r"\s+", " ", str(rel or "")).strip().strip(".\"'").lower()
    rel = re.sub(r"^(?:my|your|the|a|an|his|her|their)\s+", "", rel)
    if not re.fullmatch(r"[a-z][a-z0-9 \-]{1,40}", rel) or len(rel.split()) > 5:
        return None
    if rel in _BAD_REL or any(w in _BAD_REL for w in rel.split()):
        return None
    if any(w.lower() in rel.split() for w in re.findall(r"[A-Za-z]+", name or "")):
        return None
    return rel


def _known(c: dict, root) -> bool:
    """Already true in the bank: the same note, the same page fact, or any relation."""
    w = c["write"]
    if w["to"] == "note":
        return any((e.get("body") or "").lower() == c["fact"].lower() for e in bank.notes(root=root))
    page = people.get(w["name"], root=root)
    if not page or not page.get("path"):
        return False
    if w["to"] == "relation":
        return bool(page.get("relation"))
    return any(f["fact"].lower() == c["fact"].lower() for f in page.get("facts") or [])


def _start(today: date, root, deps: dict):
    global _run
    from reason import act
    from reason.answer import Answer
    act.reset()
    notes = []
    if deps["online"]() and state.since_sync(root) >= SYNC_EVERY:
        try:
            n = deps["sync"](root)
            state.stamp_sync(root)
            notes.append(say("discover", "synced", count=n))
        except BaseException as ex:  # SystemExit when Gmail isn't signed in
            if isinstance(ex, KeyboardInterrupt):
                raise
            notes.append(say("discover", "sync_failed", why=f"{type(ex).__name__}: {ex}"[:160]))
    try:
        events = deps["events"](today - timedelta(days=CAL_BACK), today + timedelta(days=CAL_AHEAD))
    except Exception as ex:
        events = []
        notes.append(say("discover", "no_calendar", why=str(ex)[:160]))
    done = state.load(root)
    answered = {r["id"] for r in done}
    asked_relation = {r["write"].get("name", "").lower() for r in done if r["kind"] == "relation"}

    def worth_asking(name, entries):  # no Bonsai call here: the guess is made when asked
        if name.lower() in asked_relation:
            return False
        page = people.get(name, root=root)
        return not (page and page.get("relation"))

    cands = propose.candidates(store.all_entries(root), events, relation_fn=worth_asking,
                               lazy_relation=True)
    queue = [c for c in cands if c["id"] not in answered and not _known(c, root)][:MAX_QUESTIONS]
    head = "\n".join(notes)
    _run = {"queue": queue, "n": len(queue), "yes": 0, "no": 0, "skip": 0, "relation": deps["relation"]}
    _resolve()
    if not _run["queue"]:
        _run = None
        return Answer("\n".join(x for x in (head, say("discover", "nothing_new")) if x), "discover")
    intro = say("discover", "found", count=_run["n"])
    return _ask(("\n".join(x for x in (head, intro) if x)))


def _resolve() -> None:
    """Turn a relation placeholder at the head of the queue into a real question (one
    Bonsai call), or drop it when the guess is unusable."""
    q = _run["queue"]
    while q and q[0].get("lazy"):
        c = q.pop(0)
        rel = _run["relation"](c["name"], c["entries"])
        if rel:
            q.insert(0, propose.relation_candidate(c["name"], rel, c["sources"]))
        else:
            _run["n"] -= 1


# ---- confirm ----------------------------------------------------------------

def _ask(before: str = ""):
    from reason.answer import Answer
    c = _run["queue"][0]
    k = _run["n"] - len(_run["queue"]) + 1
    lines = [before] if before else []
    lines.append(say("discover", "question", k=k, n=_run["n"], question=c["question"]))
    lines.append(say("discover", "from_head"))
    lines += [say("discover", "from_row", line=s["line"]) for s in c["sources"][:SHOW_SOURCES]]
    if len(c["sources"]) > SHOW_SOURCES:
        lines.append(say("discover", "from_more", count=len(c["sources"]) - SHOW_SOURCES))
    lines.append(say("discover", "ask_yes"))
    labels = list(dict.fromkeys(s["label"] for s in c["sources"]))
    lines.append(say("RULES", "source", labels="; ".join(labels)))
    return Answer("\n".join(lines), "discover", [s["path"] for s in c["sources"] if s.get("path")])


def shown(c: dict) -> str:
    """How a confirmed fact reads in replies and in the learned list."""
    w = c["write"]
    if w["to"] == "relation":
        return say("discover", "shown_relation", name=w["name"], relation=w["relation"])
    if w["to"] == "fact":
        return f"{w['name']} {c['fact']}"
    return c["fact"]


def _write(c: dict, today: date, root) -> str | None:
    w = c["write"]
    if w["to"] == "note":
        return bank.remember(c["fact"], today=today, root=root)["path"]
    if w["to"] == "relation":
        return people.set_relation(w["name"], w["relation"], root=root)["path"]
    src = "; ".join(s["path"] or s["label"] for s in c["sources"])
    return people.set_fact(w["name"], c["fact"], source=src, root=root)["path"]


def _reply(kind: str, today: date, root):
    global _run
    from reason.answer import Answer
    c = _run["queue"][0]
    if kind == "stop":
        r = _run
        _run = None
        return Answer(say("discover", "stopped", yes=r["yes"], no=r["no"], skip=r["skip"] + 1), "discover")
    if kind == "yes":
        wrote = _write(c, today, root)
        state.record(c, "yes", root, wrote=wrote)
        _run["yes"] += 1
        said = say("discover", "saved", fact=shown(c))
    elif kind == "no":
        state.record(c, "no", root)
        _run["no"] += 1
        said = say("discover", "declined")
    else:
        _run["skip"] += 1
        said = say("discover", "skipped")
    _run["queue"].pop(0)
    _resolve()
    if _run["queue"]:
        return _ask(said)
    r = _run
    _run = None
    return Answer(said + "\n" + say("discover", "done", yes=r["yes"], no=r["no"], skip=r["skip"]), "discover")


# ---- review -----------------------------------------------------------------

def _learned(root):
    from reason.answer import Answer
    recs = state.learned(root)
    if not recs:
        return Answer(say("discover", "nothing_learned"), "discover")
    lines = [say("discover", "learned_head")]
    for i, r in enumerate(recs, 1):
        labels = list(dict.fromkeys(s["label"] for s in r["sources"]))
        frm = "; ".join(labels[:3]) + (f" +{len(labels) - 3} more" if len(labels) > 3 else "")
        lines.append(say("discover", "learned_row", n=i, fact=shown(r), sources=frm))
    lines.append(say("discover", "unlearn_hint", n=len(recs)))
    lines.append(say("discover", "learned_source"))
    return Answer("\n".join(lines), "discover", [r["wrote"] for r in recs if r.get("wrote")])


def _unlearn(n: int, root):
    from reason.answer import Answer
    recs = state.learned(root)
    if not 1 <= n <= len(recs):
        return Answer(say("discover", "unlearn_none", n=n, count=len(recs)), "discover")
    r = recs[n - 1]
    w = r["write"]
    ok = True
    if w["to"] == "note":
        # Only when the exact note is still there (the user may have forgotten it already):
        # then it shares every word and bank.forget picks it, or on a tie removes nothing.
        if any((e.get("body") or "").lower() == r["fact"].lower() for e in bank.notes(root=root)):
            ok = bank.forget(r["fact"], root=root)["status"] == "removed"
    elif w["to"] == "relation":
        page = people.get(w["name"], root=root)
        if page and (page.get("relation") or "").lower() == w["relation"].lower():
            people.set_relation(w["name"], None, root=root)
    else:
        people.remove_fact(w["name"], r["fact"], root=root)
    if not ok:
        return Answer(say("discover", "unlearn_failed", fact=shown(r)), "discover")
    state.mark(r["id"], "removed", root)
    return Answer(say("discover", "unlearned", fact=shown(r)), "discover")


# ---- entry ------------------------------------------------------------------

def handle(question: str, today: date | None = None, root: Path | None = None, *,
           deps: dict | None = None):
    """Answer for a discovery command or a reply to a held question; None for anything else."""
    global _run
    today = today or date.today()
    d = {"online": _default_online, "sync": _default_sync, "events": _default_events,
         "relation": _default_relation, **(deps or {})}
    t = _words(question)
    if waiting():
        for kind in ("yes", "no", "skip", "stop"):
            if _t(kind).fullmatch(t):
                return _reply(kind, today, root)
    if _t("start").fullmatch(t):
        return _start(today, root, d)
    if _t("learned").search(t):
        _run = None
        return _learned(root)
    m = _t("unlearn").fullmatch(t)
    if m:
        _run = None
        return _unlearn(int(m.group(1)), root)
    _run = None  # anything else ends the run; the held question counts as skipped
    return None
