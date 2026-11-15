"""Flux reasoning layer: one question in, one answer out, bank first.

    from reason import answer
    a = answer("what is due Tuesday")   # Answer(text, route, sources, seconds)

Typed chat loop: python -m reason
"""
from .answer import OFFLINE_TEXT, Answer, answer  # noqa: F401
