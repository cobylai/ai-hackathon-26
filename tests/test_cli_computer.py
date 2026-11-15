"""The CLI exposes the computer tools and maps argv to tool kwargs."""

import pytest

import harness.__main__ as cli
from harness import registry
from harness.registry import Tool


@pytest.fixture
def fake_tool(monkeypatch):
    """Replace a registry tool with a recorder; returns the calls list."""

    def install(name: str, reply: str = "OK fake"):
        calls = []

        def run(**kwargs):
            calls.append(kwargs)
            return reply

        monkeypatch.setitem(
            registry.TOOLS, name, Tool(name, "fake", {}, run)
        )
        return calls

    return install


def test_app_open(fake_tool, capsys):
    calls = fake_tool("app_open")
    assert cli.main(["app_open", "TextEdit"]) == 0
    assert calls == [{"name": "TextEdit", "token": ""}]
    assert capsys.readouterr().out.startswith("OK fake")


def test_app_open_with_token(fake_tool):
    calls = fake_tool("app_open")
    assert cli.main(["app_open", "TextEdit", "--token", "a1b2c3"]) == 0
    assert calls == [{"name": "TextEdit", "token": "a1b2c3"}]


def test_file_find(fake_tool):
    calls = fake_tool("file_find")
    assert cli.main(["file_find", "report"]) == 0
    assert calls == [{"query": "report"}]


def test_file_open(fake_tool):
    calls = fake_tool("file_open")
    assert cli.main(["file_open", "2"]) == 0
    assert calls == [{"n": 2, "token": ""}]


def test_ui_default_filter(fake_tool):
    calls = fake_tool("ui")
    assert cli.main(["ui"]) == 0
    assert calls == [{"filter": ""}]


def test_ui_with_filter(fake_tool):
    calls = fake_tool("ui")
    assert cli.main(["ui", "save"]) == 0
    assert calls == [{"filter": "save"}]


def test_ui_click(fake_tool):
    calls = fake_tool("ui_click")
    assert cli.main(["ui_click", "3"]) == 0
    assert calls == [{"n": 3, "token": ""}]


def test_ui_type(fake_tool):
    calls = fake_tool("ui_type")
    assert cli.main(["ui_type", "1", "hello world"]) == 0
    assert calls == [{"n": 1, "text": "hello world", "token": ""}]


def test_confirm_and_err_exit_nonzero(fake_tool, capsys):
    fake_tool("ui_click", reply="CONFIRM click 'Delete' | call again with token=abc123")
    assert cli.main(["ui_click", "2"]) == 1
    assert "CONFIRM" in capsys.readouterr().out
    fake_tool("app_open", reply="ERR not allowed: open app 'Terminal'")
    assert cli.main(["app_open", "Terminal"]) == 1


def test_every_registry_command_is_parseable():
    """All six computer commands plus the browser ones parse."""
    for argv in (
        ["app_open", "x"], ["file_find", "x"], ["file_open", "1"],
        ["ui"], ["ui_click", "1"], ["ui_type", "1", "x"],
        ["goto", "x"], ["read"], ["elements"], ["click", "1"],
        ["type", "1", "x"], ["back"], ["login", "x"],
    ):
        cli._parser().parse_args(argv)  # must not raise SystemExit
