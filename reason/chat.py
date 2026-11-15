"""Chit-chat: greetings, mic checks, thanks. A fixed reply, never the web (playbooks/chat.md)."""
from __future__ import annotations

import re

from . import route
from .playbook import say

_THANKS = re.compile(r"\b(thanks|thank you|cheers)\b", re.I)
_MIC = re.compile(r"\b(hear me|is this (?:on|working|thing on)|testing|mic check|are you (?:there|listening|working|on))\b", re.I)


def handle(q: str):
    if not route.is_chat(q):
        return None
    from .answer import Answer
    key = "hear_you" if _MIC.search(q) else "thanks" if _THANKS.search(q) else "hello"
    return Answer(say("chat", key), "chat")
