"""E7, updated for confirmed send: harness/email/send.py is the ONLY send path.

Before confirmed send this file asserted there was no send path at all. Now it asserts
the one path is fenced in: only send.py names Gmail's Send control or defines a send
function, the model has no send tool, only the window's click handler calls
``send_draft``, only the "send it" route calls ``prepare_send``, and nothing else in
the repo imports the send module. The gates themselves are in tests/test_send_gates.py.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import harness

PACKAGE = Path(harness.__file__).parent
REPO = PACKAGE.parent
SEND_FILE = PACKAGE / "email" / "send.py"
# Gmail's send control, as a label or as a selector, in either quote style.
SEND_MARKERS = (
    "Send",
    "aria-label='Send",
    'aria-label="Send',
    "aria-label*='Send",
    'aria-label*="Send',
    "aria-label^='Send",
    "data-tooltip^='Send",
    "name='send'",
    'name="send"',
)
SEND_NAME = re.compile(r"^(?:.*_)?send(?:_[a-z_]+)?$", re.I)
SEND_FUNCTIONS = {"prepare_send", "send_draft", "gmail_send"}
# Who may import harness.email.send, and who may call each step.
IMPORTERS = {"reason/send.py", "reason/web.py"}
CALLERS = {"send_draft": {"reason/web.py"}, "prepare_send": {"reason/send.py"}, "gmail_send": set()}


def _python_files() -> list[Path]:
    return [path for path in PACKAGE.rglob("*.py") if "__pycache__" not in path.parts]


def _repo_code() -> list[Path]:
    """Every first-party .py file outside tests and samples."""
    skip = {".venv", "samples", "tests", "__pycache__", "third_party"}
    return [p for p in REPO.rglob("*.py") if not skip & set(p.relative_to(REPO).parts)]


def test_send_markers_only_in_send_py():
    hits = []
    for path in _python_files():
        if path == SEND_FILE:
            continue
        text = path.read_text(encoding="utf-8")
        for marker in SEND_MARKERS:
            if marker in text:
                hits.append(f"{path.relative_to(PACKAGE)}: {marker}")
    assert not hits


def test_send_functions_only_in_send_py():
    offenders, found = [], set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and SEND_NAME.match(node.name):
                if path == SEND_FILE and node.name in SEND_FUNCTIONS:
                    found.add(node.name)
                else:
                    offenders.append(f"{path.relative_to(PACKAGE)}: {node.name}")
    assert not offenders
    assert found == SEND_FUNCTIONS


def test_no_tool_named_send():
    from harness import registry

    assert not [name for name in registry.TOOLS if "send" in name.lower()]


def test_no_email_tool_description_offers_sending():
    from harness import registry

    assert all(
        not re.search(r"\bsend\b", registry.TOOLS[name].desc.lower())
        for name in registry.GROUPS["email"]
    )


def test_registry_does_not_import_send():
    text = (PACKAGE / "registry.py").read_text(encoding="utf-8")
    assert "email.send" not in text and "import send" not in text


def _imports_send(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "harness.email.send" or (mod == "harness.email" and any(a.name == "send" for a in node.names)):
                return True
        if isinstance(node, ast.Import) and any(a.name == "harness.email.send" for a in node.names):
            return True
    return False


def test_only_the_route_and_window_import_send():
    importers = set()
    for path in _repo_code():
        rel = path.relative_to(REPO).as_posix()
        if rel == "harness/email/send.py":
            continue
        if _imports_send(ast.parse(path.read_text(encoding="utf-8"))):
            importers.add(rel)
    assert importers == IMPORTERS


def test_send_steps_are_called_only_where_allowed():
    calls: dict[str, set[str]] = {name: set() for name in CALLERS}
    for path in _repo_code():
        rel = path.relative_to(REPO).as_posix()
        if rel == "harness/email/send.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name in calls:
                    calls[name].add(rel)
    assert calls == CALLERS


def test_send_draft_is_called_once_and_only_in_the_click_handler():
    src = (REPO / "reason" / "web.py").read_text(encoding="utf-8")
    assert src.count("send_draft(") == 1
    body = src[src.index("def _send_post"):src.index("def _chats_post")]
    assert "send_draft(" in body
    assert body.index("UserApproval.from_click") < body.index("send_draft(")


def test_route_and_model_paths_never_reach_send_draft():
    """The route module may only pause (prepare); it never resumes (send)."""
    src = (REPO / "reason" / "send.py").read_text(encoding="utf-8")
    assert "send_draft" not in src.split('"""', 2)[2]
    for rel in ("reason/answer.py", "reason/act.py", "reason/compose.py", "reason/suggest.py",
                "reason/session.py", "llm/client.py", "harness/llm.py", "harness/registry.py"):
        assert "send_draft" not in (REPO / rel).read_text(encoding="utf-8"), rel
