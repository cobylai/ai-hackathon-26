"""The two thinking routes, for questions no code route takes (brief Y).

  reason   about the user: code fetches the facts (bank, and for planning the coming week's
           due list and calendar), Bonsai reasons over them with thinking on, and code checks
           that every date, time, amount and name in the answer is in those facts.
           playbooks/reason-over-data.md
  general  everything else: bank first, the web for a factual lookup when online, else
           Bonsai's own knowledge with thinking on, labelled as general knowledge.
           playbooks/general.md

Facts about the user never come from the model (playbooks/RULES.md rule 1).
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

import bank
from bank import store

from . import playbook, route
from .playbook import say

GB, RB = "general", "reason-over-data"   # playbook names
THINK_TOKENS = 1500      # the time cap: ~25-30 s at 55-70 tokens/s with a 1-2k token prompt
SHORT_TOKENS = 300       # the no-thinking fallback and small talk
NOTES_TOKENS = 900       # how much of a cut-off thinking the fallback sees
CONTEXT_TOKENS = 600     # the last turns of the chat, for the general route
CONTEXT_TURNS = 3
FACTS_LIMIT = 8
DUE_LIMIT = 12           # the earliest 12 due rows, so the prompt stays short
CAL_SECONDS = 6          # a cold Calendar read can take 30 s; past this, go on without it
PLAN_DAYS = 6            # planning questions see today .. today + 6


# ---- which kind -------------------------------------------------------------------------

def _me(q: str) -> bool:
    """'my', 'mine', 'myself', or 'me' outside 'tell me / show me / help me ...'."""
    if playbook.trigger(RB, "personal").search(q):
        return True
    rest = playbook.trigger(RB, "not_me").sub(" ", q)
    return bool(re.search(r"\bme\b", rest, re.I))


def about_user(q: str, senders: set[str], root) -> bool:
    """Kind (b): the question is about the user's own things (playbooks/reason-over-data.md)."""
    if _me(q) or playbook.trigger(RB, "domain").search(q) or playbook.trigger(RB, "planning").search(q):
        return True
    words = {w.lower() for w in route._WORD.findall(q)}
    if words & senders and not words & route.COMMON:
        return True
    if re.search(r"\b[A-Z]{2,5} ?\d{4}\b", q):  # a course code
        return True
    return bool(bank.query.subject_hits(q, root=root))


# ---- model calls ------------------------------------------------------------------------

def _think(messages: list[dict], thinking: bool = True, max_tokens: int | None = None):
    """(text, cut_short). With thinking, a reply that ran out of tokens before its answer gets
    one quick call without thinking for a short answer."""
    from llm import client
    r = client.chat(messages, max_tokens=max_tokens or THINK_TOKENS, thinking=thinking)
    text = (r.text or "").strip()
    if r.finish_reason != "length":
        return text, False
    if thinking and (r.reasoning is None or not text):  # cut off inside the thinking
        notes = (r.reasoning or text or "").replace("<think>", "").strip()
        from llm.tokens import count
        while notes and count(notes) > NOTES_TOKENS:  # keep the end of the thinking
            notes = notes[len(notes) // 4:]
        short = messages + ([{"role": "assistant", "content": "My notes so far:\n" + notes}] if notes else []) + \
            [{"role": "user", "content": playbook.prompt(GB, "short_instruction")}]
        r2 = client.chat(short, max_tokens=SHORT_TOKENS, thinking=False)
        return (r2.text or "").strip(), True
    return text, True


def _json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        got = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return got if isinstance(got, dict) else None


# ---- the fact check ---------------------------------------------------------------------

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE = re.compile(rf"\b{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?\b|\b\d{{1,2}}/\d{{1,2}}(?:/\d{{2,4}})?\b|\b\d{{4}}-\d{{2}}-\d{{2}}\b", re.I)
_TIME = re.compile(r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm|a\.m\.|p\.m\.)|\b\d{1,2}:\d{2}\b|\bnoon\b|\bmidnight\b", re.I)
_MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s?(?:dollars|usd)\b", re.I)
_WEEKDAY = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b", re.I)
_CAP = re.compile(r"\b[A-Z][a-zA-Z'\-]+\b")
_CODE = re.compile(r"\b[A-Z]{2,5} ?\d{4}\b")
_ALWAYS = set("""i i'm i'd i'll i've flux ok okay am pm monday tuesday wednesday thursday friday saturday
sunday january february march april may june july august september october november december
today tomorrow tonight source canvas email mail fact facts note notes""".split())
_FACT_REF = re.compile(r"\s*\((?:facts?|notes?)\s*[\d,&\s and]+\)", re.I)


def _dates(text: str, today: date) -> set[str]:
    from bank.dates import resolve_date
    out = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text))
    for m in _DATE.finditer(text):
        d = resolve_date(m.group(0), today)
        if d:
            out.add(d.isoformat())
    return out


def _times(text: str) -> set[str]:
    from bank.dates import resolve_time
    out = set(re.findall(r"\b\d{2}:\d{2}\b", text))
    for m in _TIME.finditer(text):
        t = resolve_time(m.group(0))
        if t:
            out.add(t)
    return out


def _num(s: str) -> str:
    n = re.sub(r"[^\d.]", "", s).rstrip(".")
    return n[:-3] if n.endswith(".00") else n


def unsupported(answer: str, facts: str, question: str, today: date) -> list[str]:
    """Dates, weekdays, times, amounts and names in answer that the facts (or question) don't hold."""
    text = re.sub(r"[*_`#]", "", answer or "")
    known = facts + "\n" + question
    low = known.lower()
    bad: list[str] = []
    fact_dates = _dates(known, today)
    for m in _DATE.finditer(text):
        from bank.dates import resolve_date
        d = resolve_date(m.group(0), today)
        if d and d.isoformat() not in fact_dates:
            bad.append(m.group(0))
    weekdays = {date.fromisoformat(d).strftime("%A").lower() for d in fact_dates}
    weekdays |= {w.lower() for w in _WEEKDAY.findall(known)}
    for m in _WEEKDAY.finditer(text):
        if m.group(1).lower() not in weekdays:
            bad.append(m.group(0))
    fact_times = _times(known)
    for m in _TIME.finditer(text):
        from bank.dates import resolve_time
        t = resolve_time(m.group(0))
        if t and t not in fact_times:
            bad.append(m.group(0))
    fact_nums = {_num(x) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", known)}
    for m in _MONEY.finditer(text):
        if _num(m.group(0)) not in fact_nums:
            bad.append(m.group(0))
    codes = []
    for m in _CODE.finditer(text):
        codes.append(m.span())
        if m.group(0).replace(" ", "").lower() not in low.replace(" ", ""):
            bad.append(m.group(0))
    for m in _CAP.finditer(text):
        w = m.group(0)
        if any(a <= m.start() < b for a, b in codes):
            continue  # part of a course code, checked above
        before = text[:m.start()].rstrip(" \t\"'(")
        if not before or before[-1] in ".!?:\n-•>":
            continue  # a sentence or list item starts here; capitals there are habit
        if w.lower() in _ALWAYS or w.lower() in low:
            continue
        bad.append(w)
    return list(dict.fromkeys(bad))


# ---- (b) reasoning over the user's data -------------------------------------------------

def _events(start: date, end: date, events_fn=None) -> list[dict]:
    """Calendar events, or [] if Calendar can't be read within CAL_SECONDS (the read goes on
    in the background and warms applecal's cache for the next question)."""
    import threading
    out: list = []

    def read():
        try:
            import applecal
            out.extend((events_fn or applecal.events)(start, end))
        except Exception:
            pass
    t = threading.Thread(target=read, daemon=True)
    t.start()
    t.join(CAL_SECONDS)
    return list(out) if not t.is_alive() else []


def _facts(q: str, today: date, root, events_fn=None) -> tuple[list[str], list[dict]]:
    """(numbered fact blocks, the entry for each block or {} for a calendar event)."""
    from .answer import _short_date, _time, note_block, source_label
    blocks: list[str] = []
    owners: list[dict] = []
    seen = set()
    found = bank.search(q, limit=FACTS_LIMIT, root=root)
    if playbook.trigger(RB, "money").search(q):  # money questions: every entry naming an amount
        found += [e for e in sorted(store.all_entries(root), key=lambda e: e.get("sent_date") or "", reverse=True)
                  if re.search(r"\$\s?\d", " ".join(str(e.get(k) or "") for k in ("subject", "ask", "body")))]
    for e in found:
        if e["path"] in seen:
            continue
        seen.add(e["path"])
        blocks.append(note_block(len(blocks) + 1, e))
        owners.append(e)
    if playbook.trigger(RB, "planning").search(q) or playbook.trigger(RB, "domain").search(q):
        end = today + timedelta(days=PLAN_DAYS)
        for r in bank.due(today, end, root=root)[:DUE_LIMIT]:
            e = r["entry"]
            d = date.fromisoformat(r["date"])
            when = f"{d:%A} {_short_date(r['date'])} ({r['date']})" + (
                f" {_time(r['time'])} ({r['time']})" if r.get("time") else "")
            what = (e.get("ask") or e.get("body") or e.get("subject") or "").strip()
            blocks.append(f"[{len(blocks) + 1}] Due {when}: {what} (from {source_label(e)})")
            owners.append(e)
        evs = _events(today, end, events_fn) if playbook.trigger(RB, "planning").search(q) else []
        for ev in evs:
            s = ev["start"]
            when = f"{s:%A} {_short_date(s.date().isoformat())} ({s.date().isoformat()})"
            if not ev.get("all_day"):
                when += f" {_time(f'{s:%H:%M}')} ({s:%H:%M})"
                if ev.get("end"):
                    when += f" to {_time(f'{ev['end']:%H:%M}')} ({ev['end']:%H:%M})"
            where = f" at {ev['location']}" if ev.get("location") else ""
            blocks.append(f"[{len(blocks) + 1}] Calendar {when}: {ev.get('title') or '(no title)'}{where}")
            owners.append({})
    return blocks, owners


def reason(q: str, today: date, root, events_fn=None):
    """Kind (b). Bank route first; else facts + thinking + the fact check."""
    from .answer import Answer, _bank, _with_source
    a = _bank(q, today, root)
    if a is not None:
        return a
    blocks, owners = _facts(q, today, root, events_fn)
    if not blocks:  # "When is my chemistry exam?" -> "I have nothing saved about a chemistry exam, ..."
        from .answer import _not_saved
        return Answer(_not_saved(q), "reason")
    facts = "\n\n".join(blocks)
    prompt = playbook.prompt(RB, "reason_prompt").format(
        today=f"{today:%A} {today:%B} {today.day}, {today.year} ({today.isoformat()})",
        question=q, facts=facts)
    msgs = [{"role": "system", "content": playbook.prompt(RB, "reason_system")},
            {"role": "user", "content": prompt}]
    text, cut, got = "", False, None
    for attempt in range(2):
        raw, cut = _think(msgs, thinking=(attempt == 0), max_tokens=None if attempt == 0 else 2 * SHORT_TOKENS)
        got = _json(raw) or {"answer": raw, "used": []}
        text = _FACT_REF.sub("", str(got.get("answer") or "")).strip()  # "(Fact 6)" -> ""
        bad = unsupported(text, facts, q, today) if text else ["(empty)"]
        if not bad:
            break
        msgs = msgs + [{"role": "assistant", "content": raw},
                       {"role": "user", "content": playbook.prompt(RB, "retry").format(bad=", ".join(bad))}]
    else:
        lines = [say(RB, "unchecked")] + [_one_line(b, e) if "\n" in b else "- " + re.sub(r"^\[\d+\] ", "", b)
                                          for b, e in zip(blocks, owners)]
        ents = [e for e in owners if e]
        return Answer(_with_source("\n".join(lines), ents), "reason", list(dict.fromkeys(e["path"] for e in ents)))
    used = []
    for n in got.get("used") or []:
        try:
            k = int(n)
        except (TypeError, ValueError):
            continue
        if 1 <= k <= len(owners) and owners[k - 1] and owners[k - 1] not in used:
            used.append(owners[k - 1])
    used = used or [e for e in owners if e]
    if cut:
        text += "\n" + say(GB, "cut_short")
    out = _with_source(text, used)
    if not used:  # calendar only
        out += "\n" + say(RB, "calendar_source")
    return Answer(out, "reason", list(dict.fromkeys(e["path"] for e in used)))


def _one_line(block: str, e: dict) -> str:
    """A note block as one line: '- Subject (sender, Nov 15): ask or summary'."""
    from .answer import source_label
    what = (e.get("ask") or e.get("body") or "").strip()
    return f"- {e.get('subject') or '(no subject)'} ({source_label(e)}): {what}"


# ---- (c) general ------------------------------------------------------------------------

def _context(session) -> list[dict]:
    if session is None or not getattr(session, "turns", None):
        return []
    from llm.tokens import count
    out, used = [], 0
    for t in reversed(session.turns[-CONTEXT_TURNS:]):
        pair = [{"role": "user", "content": str(t.get("question") or "")},
                {"role": "assistant", "content": str(t.get("text") or "")[:1200]}]
        n = sum(count(m["content"]) for m in pair)
        if used + n > CONTEXT_TOKENS:
            break
        out = pair + out
        used += n
    return out


def general(q: str, today: date, root, *, small_talk: bool = False, session=None,
            online_fn=None, web_fn=None):
    """Kind (c). Small talk and explanations go straight to the model; a factual lookup tries
    the bank, then (online) the web, then the model."""
    from .answer import Answer, _bank
    up = None
    if not small_talk and not playbook.trigger(GB, "straight").search(q):
        a = _bank(q, today, root)
        if a is not None:
            return a
        if route.web_ok(q):
            up = online_fn() if online_fn else None
            if up:
                a = web_fn(q)
                if a.route != "not_found":
                    return a
    volatile = bool(playbook.trigger(GB, "volatile").search(q))
    if volatile and up is None:
        up = online_fn() if online_fn else None
    system = playbook.prompt(GB, "general_system").format(
        today=f"{today:%A} {today:%B} {today.day}, {today.year}")
    user = q + ("\n\n" + playbook.prompt(GB, "small_talk_instruction") if small_talk else "")
    msgs = [{"role": "system", "content": system}] + _context(session) + [{"role": "user", "content": user}]
    if small_talk:
        text, cut = _think(msgs, thinking=False, max_tokens=SHORT_TOKENS)
    else:
        text, cut = _think(msgs)
    if not text:
        text = say(GB, "no_answer")
    parts = []
    if volatile and not up:
        parts.append(say(GB, "cannot_check"))
    parts.append(text)
    if cut:
        parts.append(say(GB, "cut_short"))
    parts.append(say(GB, "label"))
    return Answer("\n".join(parts), "general")
