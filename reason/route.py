"""Routing in code: which route a question takes, and the date range for due questions.

Pure functions, no model, no network, no bank reads (the sender list is passed in).
Trigger words come from playbooks/<route>.md (reason/playbook.py).
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from bank.dates import resolve_date

from . import playbook

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_WD = {d: i for i, d in enumerate(WEEKDAYS)}
_WD_RE = r"(" + "|".join(WEEKDAYS) + r")"


# Title words and automated-sender words never count as a person's name.
TITLES = set("prof professor dr mr mrs ms mx sir dean".split())
AUTOMATED = set("""office club clubs library department dept team university univ services service
center centre school college admin admissions registrar bursar dining news newsletter noreply
no-reply reply support info notifications notification alerts student students staff faculty
course courses class group hall housing career careers health system mail""".split())
# Common English words that are also first names; skipped unless the question uses capitals.
COMMON = set("""will may mark grant bill rose june art august frank ray sue pat joy hope faith
dawn rob jack bob summer april earl sky gene van iris lily chase drew lane miles bob jean
the and you your what who when where how did does was are for from with about ask asked
said say says tell told send sent email emails mail message messages today tomorrow week
lab class""".split())

_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def is_due(question: str) -> bool:
    return bool(playbook.trigger("due", "due").search(question or ""))


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def due_range(question: str, today: date) -> tuple[date, date, str]:
    """(start, end, label) for a due question. label is how the answer names the range."""
    q = " " + re.sub(r"\s+", " ", (question or "").lower()) + " "
    if re.search(r"\bnext week\b", q):
        s = _monday(today) + timedelta(days=7)
        return s, s + timedelta(days=6), "next week"
    if re.search(r"\bthis week\b|\bthe week\b|\bend of (the )?week\b", q):
        # On Sat/Sun "this week" means today through the coming Sunday (thinker ruling).
        extra = 7 if today.weekday() >= 5 else 0
        return today, _monday(today) + timedelta(days=6 + extra), "this week"
    if re.search(r"\b(this )?weekend\b", q):
        sat = _monday(today) + timedelta(days=5)
        s = max(sat, today)
        return s, sat + timedelta(days=1), "this weekend"
    if re.search(r"\bday after tomorrow\b", q):
        d = today + timedelta(days=2)
        return d, d, _day(d)
    if re.search(r"\b(tomorrow|tmrw|tmr)\b", q):
        d = today + timedelta(days=1)
        return d, d, _day(d)
    if re.search(r"\b(today|tonight)\b", q):
        return today, today, _day(today)
    m = re.search(r"\bnext " + _WD_RE + r"\b", q)
    if m:
        d = _monday(today) + timedelta(days=7 + _WD[m.group(1)])
        return d, d, _day(d)
    m = re.search(r"\b" + _WD_RE + r"\b", q)
    if m:
        d = today + timedelta(days=(_WD[m.group(1)] - today.weekday()) % 7)
        return d, d, _day(d)
    if re.search(r"\d|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.? \d", q):
        d = resolve_date(q, today)
        if d:
            return d, d, _day(d)
    return today, today + timedelta(days=6), "in the next 7 days"




def is_calendar(question: str) -> bool:
    """Calendar questions: 'what's on my calendar tomorrow', 'when is my next meeting',
    'what do I have this week'. Checked after due and before person. 'What did <name>
    say about the meeting' stays a person question."""
    q = question or ""
    return bool(playbook.trigger("calendar", "calendar").search(q)
                or playbook.trigger("calendar", "next_event").search(q)) and not asked_name(q)


def is_next_event(question: str) -> bool:
    """'When is my next meeting' / 'next event': the first upcoming event."""
    return bool(playbook.trigger("calendar", "next_event").search(question or ""))


def _day(d: date) -> str:
    return f"{d:%a} {d:%b} {d.day}"


def name_words(sender_name: str | None, sender_address: str | None) -> set[str]:
    """Lowercase name words for one sender: 3+ letters, no titles, nothing automated."""
    words = _WORD.findall(sender_name or "")
    local = (sender_address or "").split("@")[0]
    words += re.split(r"[._\-+0-9]+", local)
    if any(w.lower() in AUTOMATED for w in words):
        return set()
    return {w.lower() for w in words if len(w) >= 3 and w.lower() not in TITLES}


_PRONOUNS = set("i you he she they we it someone anyone everyone people that this".split())


def is_ask_question(question: str) -> bool:
    """'What did Emily ask / want / need': answered as a code-written list of asks."""
    return bool(playbook.trigger("person", "ask").search(question or ""))


def asked_name(question: str) -> str | None:
    """The name in "what did <name> ask/say/send/want", or None (pronouns don't count)."""
    m = playbook.trigger("person", "asked_name").search(question or "")
    if not m:
        return None
    name = re.sub(r"'s$|'$", "", m.group(1))
    return None if name.lower() in _PRONOUNS else name


def person_in(question: str, names: set[str]) -> str | None:
    """The first question word that is a sender's name word, or None.

    If the question has a capitalized word other than its first, only capitalized
    words are tried and the COMMON stoplist does not apply ("what did Will say"); the
    first word is capitalized by habit, so it still goes through COMMON.
    Otherwise every word is tried except COMMON ("will it rain" does not match Will,
    "what did emily ask" matches Emily).
    """
    toks = [re.sub(r"'s$|'$", "", t) for t in _WORD.findall(question or "")]
    caps_mode = any(t[:1].isupper() for t in toks[1:])
    for i, t in enumerate(toks):
        w = t.lower()
        if len(w) < 3 or w not in names:
            continue
        if caps_mode and i > 0:
            if t[:1].isupper():
                return w
        elif w not in COMMON:  # lowercase mode, or the sentence-case first word
            return w
    return None


# ---- notes about the user, and person pages (playbooks/remember.md, people.md) ----

_LEAD = re.compile(r"^[\s\-–•*]*(?:(?:hey|ok|okay)[\s,]+)?(?:(?:muse|hearth)[\s,!.:]+)?(?:please[\s,]+)?", re.I)


def _lead(question: str) -> str:
    """Drop what comes before the command: a list dash from voice, "Muse,", "please"."""
    return _LEAD.sub("", question or "", count=1).strip()


def _after(book: str, key: str, question: str) -> str | None:
    t = _lead(question)
    m = playbook.trigger(book, key).match(t)
    return None if not m else t[m.end():].strip(" ,:")


def remember_text(question: str) -> str | None:
    """'Remember that my lab is Tuesdays at 2' -> 'my lab is Tuesdays at 2'. A question
    ("remember that thing Felix said?") or "do you remember …" is not a command: None."""
    if (question or "").strip().endswith("?"):
        return None
    rest = _after("remember", "remember", question)
    return None if rest is None else rest.rstrip(" .!")


def forget_text(question: str) -> str | None:
    """'Forget that my lab is Tuesdays at 2' -> 'my lab is Tuesdays at 2'; 'forget that' -> ''."""
    rest = _after("remember", "forget", question)
    if rest is None:
        return None
    return "" if rest.lower().strip(" .!") in ("", "it", "this", "that") else rest


def is_about_me(question: str) -> bool:
    return bool(playbook.trigger("remember", "about_me").search(question or ""))


def who_text(question: str) -> str | None:
    """'Who is Felix?' / 'What do you know about Felix Ambrose?' -> 'Felix' / 'Felix Ambrose'."""
    rest = _after("people", "who", question)
    if rest is None:
        return None
    rest = re.sub(r"'s$|'$", "", rest.strip(" ?.!"))
    return rest or None


# ---- misheard names, "everyone", chit-chat, and the web gate (test report problem 8) ----

_PERSON_VERB = re.compile(r"\b(ask|asks|asked|asking|want|wants|wanted|need|needs|needed|say|said|send|sent)\b", re.I)


def is_person_shaped(question: str) -> bool:
    """An ask/say/send/want verb, or "what did <name> ask/say/send/want"."""
    return bool(_PERSON_VERB.search(question or "")) or asked_name(question) is not None


def is_everyone(question: str) -> bool:
    """'What did everyone ask me?': asks across all senders (playbooks/person.md, everyone)."""
    q = question or ""
    return bool(playbook.trigger("person", "everyone").search(q)) and bool(_PERSON_VERB.search(q))


def _edit1(a: str, b: str) -> bool:
    """True if a and b differ by exactly one letter changed, added or dropped."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    s, t = (a, b) if len(a) < len(b) else (b, a)
    return any(t[:i] + t[i + 1:] == s for i in range(len(t)))


def near_name(word: str, name: str) -> bool:
    """A misheard name: one is the other with up to 2 letters more at the start or end
    ("elena" ~ "lena", shorter at least 4 letters), or one letter off when both have 5+."""
    if word == name:
        return False
    s, t = sorted((word, name), key=len)
    if len(s) >= 4 and len(t) - len(s) <= 2 and (t.startswith(s) or t.endswith(s)):
        return True
    return len(s) >= 5 and _edit1(word, name)


def near_person(question: str, names: set[str]) -> tuple[str, list[str]] | None:
    """(heard word, [sender name words it is near]) for the first question word that is no
    sender but near one, or None. Only words of 4+ letters outside the COMMON list are tried."""
    for t in _WORD.findall(question or ""):
        w = re.sub(r"'s$|'$", "", t).lower()
        if len(w) < 4 or w in COMMON or w in names or w in _PRONOUNS or _PERSON_VERB.fullmatch(w):
            continue
        hits = sorted(n for n in names if near_name(w, n))
        if hits:
            return t, hits
    return None


_CHAT_WORD = re.compile(r"[a-z']+")


def is_chat(question: str) -> bool:
    """Greetings, mic checks, thanks (playbooks/chat.md): a chat trigger matches and, with every
    chat and filler phrase taken out, at most 2 other words are left."""
    q = (question or "").lower()
    chat = playbook.trigger("chat", "chat")
    if not chat.search(q):
        return False
    rest = playbook.trigger("chat", "filler").sub(" ", chat.sub(" ", q))
    if re.search(r"\b(what|when|where|who|whose|which|why|how)\b", rest):
        return False  # "hey, what's due" or "hi, how much is my share" is a real question
    return len(_CHAT_WORD.findall(rest)) <= 2


def web_ok(question: str) -> bool:
    """The web is only for clear factual questions (playbooks/RULES.md rule 9): starts with a
    question word or ends with '?', and is not about the user's own things ("my")."""
    q = (question or "").strip()
    if playbook.trigger("web", "personal").search(q):
        return False
    return q.endswith("?") or bool(playbook.trigger("web", "question").match(_lead(q)))
