"""What's Flux, and a guided tour. playbooks/about.md. Code only, no model call.

handle(question, today, root, session=, run=answer, events=) -> Answer | None
  - overview ("what's Flux", "help", ...): about.md's intro, one line per ## Overview row, buttons.
  - "show me" starts the tour; while it's on (session.tour), next / back / skip / stop move it.
    Any other question returns None and is answered as usual; the tour waits.
Each step runs real questions from about.md, with {name} and {item} filled from the bank
(a sender and a due item), through answer() on a scratch session, and shows the real answers.
A question marked (show) is shown, not run. Anything an example left waiting for a yes
(act) or for more words (compose) is cleared, so nothing is saved, opened or sent.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from . import playbook, route
from .playbook import say

BOOK = "about"
NAV = [["Next", "next"], ["Back", "back"], ["Stop", "stop"]]
FIXED = ("internet", "mail", "model", "send")  # about.md: one fixed answer each, no model call


def _items(section: str) -> list[tuple[str, str]]:
    out = []
    for line in playbook.load(BOOK).sections.get(section, "").splitlines():
        m = re.match(r"^- ([^:]+):\s*(.*)$", line.strip())
        if m:
            out.append((m.group(1).strip(), m.group(2).strip()))
    return out


def _refs(spec: str) -> list[tuple[str, str]]:
    """'What did {name} ask me? | Remember that … (show)' -> [(question, "" | "show"), ...]."""
    out = []
    for part in [p.strip() for p in spec.split("|") if p.strip()]:
        show = part.endswith("(show)")
        out.append((part[:-len("(show)")].strip() if show else part, "show" if show else ""))
    return out


def _whole(question: str, key: str) -> bool:
    q = route._lead(question).strip().rstrip("?.!").strip()
    return bool(q) and bool(re.fullmatch(playbook.trigger(BOOK, key).pattern, q, re.I))


# ---- what the bank has, to fill the examples ----------------------------------

def _sender(root: Path | None) -> str | None:
    """The first name of the newest email sender with an ask."""
    from bank import store
    mail = [e for e in store.all_entries(root) if e.get("kind") == "email" and e.get("ask")
            and (e.get("sender_name") or "").strip()]
    mail.sort(key=lambda e: e.get("sent_date") or "", reverse=True)
    return mail[0]["sender_name"].split()[0] if mail else None


def _item(today: date, root: Path | None) -> str | None:
    """The nearest coursework due item (its subject), in the next two weeks."""
    from bank import due
    for r in due(today, today + timedelta(days=14), root):
        e = r.get("entry") or {}
        if e.get("folder") == "course" and e.get("subject"):
            return e["subject"]
    return None


def _fill(question: str, name: str | None, item: str | None) -> str | None:
    """The question with {name} (newest sender with an ask) and {item} (nearest coursework due
    item) filled from the bank. None when the bank can't fill a placeholder it uses."""
    if ("{name}" in question and not name) or ("{item}" in question and not item):
        return None
    return question.replace("{name}", name or "").replace("{item}", item or "")


# ---- the overview ----------------------------------------------------------------

def overview(today: date, root: Path | None):
    from .answer import Answer
    name, item = _sender(root), _item(today, root)
    lines, choices = [say(BOOK, "intro"), say(BOOK, "intro2"), say(BOOK, "can_head")], []
    for _label, spec in _items("Overview"):
        q = _fill(_refs(spec)[0][0], name, item)
        if q is None:  # the bank has no sender or due item to put in
            continue
        q = q.rstrip(".")
        lines.append(say(BOOK, "can_row", question=q))
        choices.append([q, q])
    lines += ["", say(BOOK, "source")]
    return Answer("\n".join(lines), "about", choices=choices)


# ---- the tour ----------------------------------------------------------------------

def _steps() -> list[tuple[str, str]]:
    return _items("Tour")


def _clear_held() -> None:
    from . import act, compose
    act.reset()
    compose.reset()


def step(i: int, today: date, root: Path | None, run, events, *, skipped: list[str] | None = None):
    """Write step i (skipping steps whose data is missing). Returns (Answer, the step shown)."""
    from .answer import Answer
    from .session import Session
    steps = _steps()
    notes = list(skipped or [])
    name, item = _sender(root), _item(today, root)
    while i < len(steps):
        key, spec = steps[i]
        refs = _refs(spec)
        filled = [(_fill(q, name, item), how) for q, how in refs]
        missing = any(q is None for q, _ in filled) or (key == "catchup" and not _bank_has(root)) \
            or (key == "due" and not _due_tomorrow(today, root))
        if missing:
            notes.append(say(BOOK, f"{key}_skip"))
            i += 1
            continue
        out, sources = list(notes), []
        if notes:
            out.append("")
        out += [say(BOOK, "step_head", n=i + 1, total=len(steps), title=say(BOOK, f"{key}_title")),
                say(BOOK, f"{key}_what")]
        scratch = Session()
        for q, how in filled:
            out += ["", say(BOOK, "example", question=q)]
            if how == "show":
                out.append(say(BOOK, "shown"))
                continue
            try:
                a = run(q, today=today, root=root, session=scratch, _events=events)
            finally:
                _clear_held()
            out.append(_shown(a.text))
            for s in a.suggestions or []:
                out.append(say(BOOK, "suggested", line=s["line"]))
            sources += [s for s in a.sources or [] if s not in sources]
        last = i == len(steps) - 1
        out += ["", say(BOOK, f"{key}_try")] + ([] if last else [say(BOOK, "nav")]) + ["", say(BOOK, "source")]
        choices = [["Done", "stop"]] if last else ([c for c in NAV if c[1] != "back"] if i == 0 else NAV)
        return Answer("\n".join(out), "about", sources, choices=choices), i
    # Ran off the end: everything left was skipped.
    return Answer("\n".join(notes + ["", say(BOOK, "nav_last"), "", say(BOOK, "source")]), "about",
                  choices=[["Done", "stop"]]), len(steps) - 1


def _shown(text: str) -> str:
    """The example's answer as the route wrote it (with its source line). A "say yes to go ahead"
    line is swapped for `no_yes`: the tour cleared that action, so a yes would do nothing."""
    asks = {say("act", "ask_yes").lower(), say("web", "save_ask").lower()}
    lines = [say(BOOK, "no_yes") if ln.strip().lower() in asks else ln for ln in (text or "").strip().splitlines()]
    return "\n".join(lines)


def _bank_has(root: Path | None) -> bool:
    from bank import store
    return bool(store.all_entries(root))


def _due_tomorrow(today: date, root: Path | None) -> bool:
    from bank import due
    t = today + timedelta(days=1)
    return bool(due(t, t, root))


def handle(question: str, today: date, root: Path | None = None, *, session=None, run=None, events=None,
           held: bool = False):
    """An Answer for the overview or a tour move, else None (answer the question as usual)."""
    from .answer import Answer
    for key in FIXED:  # fixed answers: never touch a held action or draft
        if _whole(question, key):
            text = say(BOOK, f"{key}_answer")
            if key == "internet":
                from .answer import online
                text += " " + say(BOOK, "internet_online" if online() else "internet_offline")
            return Answer(text + "\n\n" + say(BOOK, "source"), "about")
    if held:
        return None
    if _whole(question, "overview"):
        return overview(today, root)
    if session is None or run is None:
        return None
    on = getattr(session, "tour", None) is not None
    if _whole(question, "start"):
        a, session.tour = step(0, today, root, run, events)
        return a
    if not on:
        if any(_whole(question, k) for k in ("next", "back", "skip")):
            return Answer(say(BOOK, "not_on") + "\n\n" + say(BOOK, "source"), "about")
        return None
    if _whole(question, "stop"):
        session.tour = None
        return Answer(say(BOOK, "ended") + "\n\n" + say(BOOK, "source"), "about")
    if _whole(question, "next") or _whole(question, "skip"):
        i = session.tour + 1
        if i >= len(_steps()):
            session.tour = None
            return Answer(say(BOOK, "ended") + "\n\n" + say(BOOK, "source"), "about")
        a, session.tour = step(i, today, root, run, events)
        return a
    if _whole(question, "back"):  # the nearest earlier step that isn't skipped
        for j in range(session.tour - 1, -1, -1):
            a, shown = step(j, today, root, run, events)
            if shown == j:
                session.tour = j
                return a
        a, session.tour = step(0, today, root, run, events)
        return a
    return None
