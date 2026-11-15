"""The shell runner coerces arguments and follows the registry contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from harness import registry

ROOT = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location("run_tool", ROOT / "scripts" / "run_tool.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_list_shows_the_email_group(capsys):
    script = _script()
    assert script.run(["--list"]) == 0
    out = capsys.readouterr().out
    assert "email_search" in out
    assert "email:" in out


def test_arguments_are_coerced_to_the_declared_types(monkeypatch, capsys):
    script = _script()
    seen = {}

    def echo(n: int, text: str = "") -> str:
        seen["n"], seen["text"] = n, text
        return f"OK n={n!r} text={text!r}"

    monkeypatch.setitem(
        registry.TOOLS, "echo", registry.Tool("echo", "Echo back.", {"n": int, "text": str}, echo)
    )
    assert script.run(["echo", "n=3", "text=hi"]) == 0
    assert seen == {"n": 3, "text": "hi"}
    assert capsys.readouterr().out.strip() == "OK n=3 text='hi'"


def test_unknown_argument_is_a_usage_error(capsys):
    script = _script()
    assert script.run(["goto", "nope=1"]) == 2
    assert "takes:" in capsys.readouterr().out


def test_unknown_tool_lists_options(capsys):
    script = _script()
    assert script.run(["nope"]) == 2
    out = capsys.readouterr().out
    assert "unknown tool" in out and "email_search" in out


def test_non_ok_output_exits_one(monkeypatch):
    script = _script()
    monkeypatch.setitem(registry.TOOLS, "fail", registry.Tool("fail", "Always ERR.", {}, lambda: "ERR nope"))
    assert script.run(["fail"]) == 1
