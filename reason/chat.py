"""Small talk detection (playbooks/chat.md). "Who are you / what can you do" gets a fixed reply;
other small talk is answered by the general route (reason/think.py), never the web."""
from __future__ import annotations

import re

from . import route
from .playbook import say

_THANKS = re.compile(r"\b(thanks|thank you|cheers)\b", re.I)
_MIC = re.compile(r"\b(hear me|is this (?:on|working|thing on)|testing|mic check|are you (?:there|listening|working|on))\b", re.I)


_ABOUT = re.compile(r"\b(who are you|what are you|what(?:'s| is) flux|what can you do|what do you do|who (?:made|built|created) you|are you (?:a|an) (?:ai|bot|robot|assistant|chatbot))\b", re.I)


def handle(q: str):
    """A question about Flux itself gets the fixed about_flux reply. Other small talk returns
    None and goes to the general route with a "keep it short" instruction (brief Y)."""
    if not route.is_chat(q) or not _ABOUT.search(q):
        return None
    from .answer import Answer
    return Answer(say("chat", "about_flux"), "chat")
