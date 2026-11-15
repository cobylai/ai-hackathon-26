"""One conversation: the last question, its route and its rows, for follow-ups. playbooks/followup.md.

    s = Session()
    answer("What's due tomorrow?", session=s)
    answer("and Friday?", session=s)          # due again, for Friday
    answer("who sent the first one?", session=s)

resolve(question, session, today) is code only, no model call. It returns:
  None                       not a follow-up: answer the question as usual
  ("question", text)         answer this question instead ("and Hugo?" -> "What did Hugo ask me?")
  ("due" | "calendar", text) run that route again with this date phrase
  ("answer", Answer)         answered from the last rows (route "followup", or "act" for "open it")
The session lives in memory only (one per chat loop, one in the window server) and is
gone on restart. Nothing is written to the bank.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from . import playbook, route
from .playbook import say

ORDINALS = {w: i for i, w in enumerate(
    "first second third fourth fifth sixth seventh eighth ninth tenth".split())}
ORDINALS.update({f"{n}{s}": n - 1 for n, s in zip(range(1, 11),
                                                  "st nd rd th th th th th th th".split())})
ORDINALS["last"] = -1
DATE_ROUTES = ("due", "calendar")
NAME_ROUTES = ("person", "people")
NOT_NAMES = set("""the a an my me your you it that this them him her his their what when where why
how who today tonight tomorrow week weekend next last this one ones all everyone else more about
also too then so is are was do did does""".split())
_DEFAULT_LABEL = "in the next 7 days"


@dataclass
class Session:
    question: str | None = None
    route: str | None = None
    rows: list[dict] = field(default_factory=list)
    who: str | None = None      # the name in the last person question, as it was written
    pick: int | None = None     # the row a follow-up picked last

    def clear(self) -> None:
        self.question, self.route, self.rows, self.who, self.pick = None, None, [], None, None

    def record(self, question: str, a, root=None) -> None:
        """Keep what a follow-up may lean on. Follow-up and act answers keep the rows they used."""
        if a.route in ("followup", "act"):
            return
        self.question, self.route, self.rows, self.pick = question, a.route, list(a.rows or []), None
        self.who = None
        if a.route == "person":
            from .answer import _senders
            w = route.person_in(question, _senders(root)) or route.asked_name(question)
            if w:
                m = re.search(rf"\b{re.escape(w)}\b", question, re.I)
                self.who = m.group(0) if m else w
        elif a.route == "people":
            self.who = route.who_text(question)


def _norm(q: str) -> str:
    t = route._lead(q or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[?.!,;:]+$", "", t.strip())).strip()


def _t(key: str):
    return playbook.trigger("followup", key)


def _ordinal(m) -> tuple[bool, int | None]:
    """(matched, index). An ordinal group that is not an ordinal means no match."""
    groups = [g for g in m.groups() if g is not None]
    if not groups:
        return True, None
    g = groups[0]
    if g.isdigit():
        return True, int(g) - 1
    if g in ORDINALS:
        return True, ORDINALS[g]
    return False, None


def _row(s: Session, idx: int | None):
    """(row, None) or (None, Answer saying which one / out of range)."""
    from .answer import Answer
    n = len(s.rows)
    if idx is None:
        idx = s.pick if s.pick is not None else (0 if n == 1 else None)
        if idx is None:
            return None, Answer(say("followup", "which_one", n=n), "followup")
    if idx == -1:
        idx = n - 1
    if not 0 <= idx < n:
        return None, Answer(say("followup", "out_of_range", n=n), "followup")
    s.pick = idx
    return s.rows[idx], None


def _source(row) -> str:
    from .answer import source_label
    if row["kind"] == "event":
        import applecal
        return say("calendar", "source", calendar=applecal.calendar_name())
    return say("RULES", "source", labels=source_label(row["entry"]))


def _show(row) -> str:
    line = re.sub(r"^- ", "", row.get("line") or "").strip()
    lines = [say("followup", "show_entry", line=line)]
    if row["kind"] == "entry":
        summary = (row["entry"].get("body") or "").strip()
        if summary and summary.rstrip(".") not in line:
            lines.append("    " + say("followup", "show_summary", summary=summary))
    return "\n".join(lines + [_source(row)])


def _who(row) -> str:
    from .answer import _short_date
    if row["kind"] == "event":
        return say("followup", "who_event", title=row["event"].get("title") or "(no title)")
    e = row["entry"]
    who = e.get("sender_name") or e.get("sender_address") or e.get("source") or "an unknown sender"
    key = "who_course" if e.get("kind") == "canvas" else "who_sent"
    text = say("followup", key, who=who, date=_short_date(e.get("sent_date")),
               subject=e.get("subject") or "(no subject)")
    return f"{text}\n{_source(row)}"


def _when(row) -> str:
    from .answer import _event_line, _time
    if row["kind"] == "event":
        when = re.sub(r"^- ", "", _event_line(row["event"], True)).strip()
        return f"{say('followup', 'when_event', when=when)}\n{_source(row)}"
    e = row["entry"]
    days = [(row["date"], row.get("time"))] if row.get("date") else [
        (str(d["date"]), d.get("time")) for d in e.get("deadlines") or [] if d.get("date")]
    if not days:
        return f"{say('followup', 'when_none')}\n{_source(row)}"
    whens = []
    for d, t in days:
        try:
            day = route._day(date.fromisoformat(d[:10]))
        except ValueError:
            day = d
        whens.append(" ".join(x for x in (day, _time(t)) if x))
    return f"{say('followup', 'when_due', when='; '.join(dict.fromkeys(whens)))}\n{_source(row)}"


def _date_phrase(rest: str, today: date) -> bool:
    return route.due_range(rest, today)[2] != _DEFAULT_LABEL


def _name(rest: str) -> str | None:
    words = re.sub(r"'s$", "", rest).split()
    if not 1 <= len(words) <= 3 or not all(re.fullmatch(r"[a-z][a-z'\-]*", w) for w in words):
        return None
    if any(w in NOT_NAMES for w in words):
        return None
    return " ".join(w[:1].upper() + w[1:] for w in words)


def resolve(question: str, s: Session, today: date, root=None, act_deps: dict | None = None):
    from .answer import Answer
    t = _norm(question)
    if not t or s.route is None:
        return None
    m = _t("more").match(t)
    if m:
        rest = m.group(1).strip()
        if s.route in DATE_ROUTES and _date_phrase(rest, today):
            return (s.route, rest)
        if s.route in NAME_ROUTES and s.who and (name := _name(rest)):
            q = re.sub(rf"\b{re.escape(s.who)}\b", name, s.question or "", count=1, flags=re.I)
            if q != s.question:
                return ("question", q)
    if not s.rows:
        return None
    for key in ("pick", "who", "when", "open"):
        m = _t(key).match(t)
        if not m:
            continue
        ok, idx = _ordinal(m)
        if not ok:
            return None
        row, why = _row(s, idx)
        if why is not None:
            return ("answer", why)
        if key == "open":
            from . import act
            return ("answer", act.plan_row(row, deps=act_deps))
        text = {"pick": _show, "who": _who, "when": _when}[key](row)
        return ("answer", Answer(text, "followup", rows=[row]))
    return None
