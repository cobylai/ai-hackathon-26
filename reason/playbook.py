"""Playbooks: the wording of each route, read from playbooks/<name>.md.

Each playbook file has the same sections (see playbooks/RULES.md). Code reads four of them:

  ## Triggers   lines "- key: `pattern`"; lines with the same key are OR'ed, whole words
  ## Wording    lines "- key: text with {placeholders}"
  ## Not found  same as Wording (the not-found replies)
  ## Prompt     "### key" headings, each followed by one fenced block of prompt text
  ## Examples   a table: | question | route | answer contains |

The order of steps stays in code; STEPS in reason/answer.py must match the number of
numbered lines under "## Steps" (a unit test checks it). Files are read once per process,
so an edit applies on the next start.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "playbooks"
SECTIONS = ("For", "Triggers", "Steps", "May look", "May not look", "Wording", "Not found",
            "Never", "Prompt", "Examples")


class PlaybookError(Exception):
    pass


@dataclass
class Playbook:
    name: str
    sections: dict[str, str]
    triggers: dict[str, list[str]] = field(default_factory=dict)
    wording: dict[str, str] = field(default_factory=dict)
    prompts: dict[str, str] = field(default_factory=dict)
    steps: list[str] = field(default_factory=list)
    examples: list[dict] = field(default_factory=list)


_ITEM = re.compile(r"^- ([a-z0-9_]+): (.*)$")


def _items(text: str) -> list[tuple[str, str]]:
    out = []
    for line in text.splitlines():
        m = _ITEM.match(line.strip())
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out


def parse(name: str, text: str) -> Playbook:
    sections: dict[str, str] = {}
    cur = None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            sections[cur] = ""
        elif cur is not None:
            sections[cur] += line + "\n"
    pb = Playbook(name, sections)
    for k, v in _items(sections.get("Triggers", "")):
        pat = v.strip()
        if not (pat.startswith("`") and pat.endswith("`")):
            raise PlaybookError(f"{name}.md Triggers: {k} must be in backticks")
        pb.triggers.setdefault(k, []).append(pat[1:-1])
    for sec in ("Wording", "Not found"):
        for k, v in _items(sections.get(sec, "")):
            if k in pb.wording:
                raise PlaybookError(f"{name}.md: wording key {k} appears twice")
            pb.wording[k] = v
    for m in re.finditer(r"^### ([a-z0-9_]+)\s*\n```[a-z]*\n(.*?)\n```", sections.get("Prompt", ""),
                         re.S | re.M):
        pb.prompts[m.group(1)] = m.group(2)
    pb.steps = [ln.strip() for ln in sections.get("Steps", "").splitlines()
                if re.match(r"^\d+\.\s", ln.strip())]
    for line in sections.get("Examples", "").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or not line.strip().startswith("|"):
            continue
        if cells[0].lower() == "question" or set(cells[0]) <= set("-: "):
            continue
        contains = [c.strip().strip("`") for c in cells[2].split(";") if c.strip()]
        pb.examples.append({"question": cells[0].strip("`"), "route": cells[1].strip("`"),
                            "contains": contains})
    return pb


@lru_cache(maxsize=None)
def load(name: str) -> Playbook:
    path = DIR / f"{name}.md"
    if not path.exists():
        raise PlaybookError(f"no playbook {path}")
    return parse(name, path.read_text())


def reload() -> None:
    load.cache_clear()
    _pattern.cache_clear()


def names() -> list[str]:
    return sorted(p.stem for p in DIR.glob("*.md") if p.stem != "RULES")


def say(book: str, key: str, /, **values) -> str:
    """The wording line `key` from playbooks/<book>.md, filled in."""
    pb = load(book)
    if key not in pb.wording:
        raise PlaybookError(f"playbooks/{book}.md has no wording line '{key}'")
    try:
        return pb.wording[key].format(**values)
    except (KeyError, IndexError, ValueError) as e:
        raise PlaybookError(f"playbooks/{book}.md '{key}': bad placeholder ({e})") from None


def prompt(name: str, key: str) -> str:
    pb = load(name)
    if key not in pb.prompts:
        raise PlaybookError(f"playbooks/{name}.md has no prompt '{key}'")
    return pb.prompts[key]


@lru_cache(maxsize=None)
def _pattern(name: str, key: str) -> re.Pattern:
    pats = load(name).triggers.get(key)
    if not pats:
        raise PlaybookError(f"playbooks/{name}.md has no trigger '{key}'")
    return re.compile(r"\b(?:" + "|".join(f"(?:{p})" for p in pats) + r")\b", re.I)


def trigger(name: str, key: str) -> re.Pattern:
    """Lines '- key: `pattern`' under ## Triggers, OR'ed, matched as whole words, any case."""
    return _pattern(name, key)
