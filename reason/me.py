"""Routes for notes about the user and for person pages. Code only, no model call.

  remember  "remember that my lab is Tuesdays at 2"  -> bank.remember, in the user's words
  forget    "forget that my lab ..." / "forget that"  -> bank.forget
  about_me  "what do you know about me"              -> bank.notes, listed
  people    "who is Felix" / "what do you know about Felix" -> bank.people.get, listed

Wording: playbooks/remember.md and playbooks/people.md. handle() returns None when the
question is none of these, and answer() goes on to its other routes.
"""
from __future__ import annotations

import re
from datetime import date

import bank
from bank import people

from . import route
from .playbook import say

PEOPLE_EMAILS = 5


def handle(q: str, today: date, root):
    from .answer import Answer, _senders, _short_date, _with_source
    fact = route.remember_text(q)
    if fact is not None:
        if not fact.strip(" .!"):
            return Answer(say("remember", "empty"), "remember")
        got = bank.remember(fact, today=today, root=root)
        key = "saved" if got["status"] == "added" else "already"
        return Answer(say("remember", key, fact=got["entry"]["body"]), "remember", [got["path"]])

    text = route.forget_text(q)
    if text is not None:
        got = bank.forget(text, root=root)
        if got["status"] == "removed":
            return Answer(say("remember", "forgotten", fact=got["removed"]["body"]), "forget")
        if got["status"] == "ambiguous":
            rows = [say("remember", "note_row", date=_short_date(e.get("sent_date")), fact=e["body"])
                    for e in got["candidates"]]
            return Answer("\n".join([say("remember", "which_one")] + rows), "forget",
                          [e["path"] for e in got["candidates"]])
        return Answer(say("remember", "forget_none"), "forget")

    if route.is_about_me(q):
        notes = bank.notes(root=root)
        if not notes:
            return Answer(say("remember", "no_notes"), "about_me")
        rows = [say("remember", "note_row", date=_short_date(e.get("sent_date")), fact=e["body"])
                for e in notes]
        return Answer("\n".join([say("remember", "notes_head")] + rows + [say("remember", "notes_source")]),
                      "about_me", [e["path"] for e in notes])

    name = route.who_text(q)
    if name and _known(name, _senders(root), root):
        page = people.get(name, root=root)
        if page:
            return _page(page)
    return None


def _known(name: str, senders: set[str], root) -> bool:
    """Every word of name is a sender's name word or a word of a person page's name."""
    known = set(senders)
    for n in people.names(root=root):
        known |= set(re.findall(r"[a-z0-9']+", n.lower()))
    words = re.findall(r"[a-z0-9']+", name.lower())
    return bool(words) and all(w in known for w in words)


def _page(page: dict):
    from .answer import Answer, _short_date, source_label
    lines = [say("people", "head", name=page["name"])]
    lines.append(say("people", "relation", relation=page["relation"]) if page.get("relation")
                 else say("people", "relation_unknown"))
    if page.get("facts"):
        lines.append(say("people", "facts_head"))
        lines += [say("people", "fact_row", fact=f["fact"]) for f in page["facts"]]
    entries = page.get("entries") or []
    if entries:
        lines.append(say("people", "emails_head", count=min(len(entries), PEOPLE_EMAILS), total=len(entries)))
        lines += [say("people", "email_row", date=_short_date(e.get("sent_date")),
                      subject=e.get("subject") or "(no subject)") for e in entries[:PEOPLE_EMAILS]]
    labels = ([say("people", "page_label", name=page["name"])] if page.get("path") else []) + \
        list(dict.fromkeys(source_label(e) for e in entries[:PEOPLE_EMAILS]))
    lines.append(say("RULES", "source", labels="; ".join(labels)))
    return Answer("\n".join(lines), "people",
                  ([page["path"]] if page.get("path") else []) + [e["path"] for e in entries[:PEOPLE_EMAILS]])
