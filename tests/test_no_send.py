"""E7: the package must not contain a Send button or a send function."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import harness

PACKAGE = Path(harness.__file__).parent
# Gmail's send control, as a label or as a selector, in either quote style.
SEND_MARKERS = (
    "Send",
    "aria-label='Send",
    'aria-label="Send',
    "aria-label*='Send",
    'aria-label*="Send',
    "name='send'",
    'name="send"',
)
SEND_NAME = re.compile(r"^(?:.*_)?send(?:_[a-z_]+)?$", re.I)


def _python_files() -> list[Path]:
    return [path for path in PACKAGE.rglob("*.py") if "__pycache__" not in path.parts]


def test_no_send_label_or_selector():
    hits = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        for marker in SEND_MARKERS:
            if marker in text:
                hits.append(f"{path.relative_to(PACKAGE)}: {marker}")
    assert not hits


def test_no_function_named_send():
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and SEND_NAME.match(node.name):
                offenders.append(f"{path.relative_to(PACKAGE)}: {node.name}")
    assert not offenders


def test_no_tool_named_send():
    from harness import registry

    assert not [name for name in registry.TOOLS if "send" in name.lower()]


def test_no_email_tool_description_offers_sending():
    from harness import registry

    assert all(
        not re.search(r"\bsend\b", registry.TOOLS[name].desc.lower())
        for name in registry.GROUPS["email"]
    )
