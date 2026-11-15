"""Chit-chat: greetings, mic checks, thanks. A fixed reply, never the web (playbooks/chat.md)."""
from __future__ import annotations

import re

from . import route
from .playbook import say

_THANKS = re.compile(r"\b(thanks|thank you|cheers)\b", re.I)
_MIC = re.compile(r"\b(hear me|is this (?:on|working|thing on)|testing|mic check|are you (?:there|listening|working|on))\b", re.I)


_ABOUT = re.compile(r"\b(who are you|what are you|what(?:'s| is) flux|what can you do|what do you do|who (?:made|built|created) you|are you (?:a|an) (?:ai|bot|robot|assistant|chatbot))\b", re.I)


def handle(q: str):
    if not route.is_chat(q):
        return None
    from .answer import Answer
    key = "about_flux" if _ABOUT.search(q) else "hear_you" if _MIC.search(q) else "thanks" if _THANKS.search(q) else "hello"
    return Answer(say("chat", key), "chat")
