"""Offline token counting and budget helpers.

Uses the model's own tokenizer.json (same file for 2B/4B/9B) via the
`tokenizers` package. If that package or file is missing, falls back to a
conservative estimate of 1 token per 2.5 characters, which overcounts.
"""
from __future__ import annotations

import functools
import re

from . import config

# Per-message chat-template overhead (<|im_start|>role\n ... <|im_end|>\n) and the
# assistant prefix plus the empty think block. Checked against server usage
# numbers; see docs/bonsai-client.md.
PER_MESSAGE_OVERHEAD = 6
REPLY_PRIMER = 8


class BudgetError(ValueError):
    """Prompt plus reserved output does not fit the 32k context."""


@functools.lru_cache(maxsize=1)
def _tokenizer():
    try:
        from tokenizers import Tokenizer
    except ImportError:
        return None
    path = config.model_dir() / "tokenizer.json"
    if not path.exists():
        # Any size will do: all three share one tokenizer.
        found = sorted(config.MODELS_DIR.glob("bonsai2-*-mlx/tokenizer.json"))
        if not found:
            return None
        path = found[0]
    return Tokenizer.from_file(str(path))


def method() -> str:
    return "tokenizer.json" if _tokenizer() is not None else "estimate (chars/2.5)"


def count(text: str) -> int:
    tok = _tokenizer()
    if tok is None:
        return int(len(text) / 2.5) + 1
    return len(tok.encode(text, add_special_tokens=False).ids)


def count_messages(messages: list[dict]) -> int:
    return sum(count(m["content"]) + PER_MESSAGE_OVERHEAD for m in messages) + REPLY_PRIMER


def check_budget(messages: list[dict], max_tokens: int,
                 limit: int = config.CONTEXT_TOKENS) -> int:
    """Return prompt token count, or raise BudgetError. Never truncates."""
    n = count_messages(messages)
    if n + max_tokens > limit:
        raise BudgetError(
            f"Prompt is {n} tokens + {max_tokens} reserved for output = "
            f"{n + max_tokens}, over the {limit}-token context. Shorten the input "
            f"(llm.tokens.split_to_budget / trim_to_budget) or lower max_tokens."
        )
    return n


def _hard_split(text: str, budget: int) -> list[str]:
    tok = _tokenizer()
    if tok is None:
        step = max(1, int(budget * 2.5))
        return [text[i:i + step] for i in range(0, len(text), step)]
    enc = tok.encode(text, add_special_tokens=False)
    out = []
    for i in range(0, len(enc.ids), budget):
        start = enc.offsets[i][0]
        end = enc.offsets[min(i + budget, len(enc.ids)) - 1][1]
        out.append(text[start:end])
    return out


def split_to_budget(text: str, budget: int) -> list[str]:
    """Split text into chunks of at most `budget` tokens each.

    Breaks on blank lines first, then lines, then sentences, then raw tokens.
    """
    if budget <= 0:
        raise ValueError("budget must be positive")
    if count(text) <= budget:
        return [text]
    for sep, joiner in ((r"\n\s*\n", "\n\n"), (r"\n", "\n"), (r"(?<=[.!?])\s+", " ")):
        pieces = [p for p in re.split(sep, text) if p.strip()]
        if len(pieces) > 1:
            break
    else:
        return _hard_split(text, budget)

    chunks, cur = [], ""
    for p in pieces:
        if count(p) > budget:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.extend(split_to_budget(p, budget))
            continue
        cand = f"{cur}{joiner}{p}" if cur else p
        if count(cand) <= budget:
            cur = cand
        else:
            chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


def trim_to_budget(text: str, budget: int) -> str:
    """The first `budget` tokens' worth of text, cut on a natural boundary."""
    return split_to_budget(text, budget)[0]
