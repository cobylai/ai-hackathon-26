"""Tests for direct computer commands with subprocess mocked (task C4)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from harness import config
from harness.computer import direct, policy, tools


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Policy state in a tmp dir, never the real ~/.harness."""
    monkeypatch.setattr(config, "HOME_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def mock_run(monkeypatch):
    run = MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(direct.subprocess, "run", run)
    return run


def test_app_open_allowed(home, mock_run):
    assert tools.app_open("TextEdit") == "OK opened TextEdit"
    mock_run.assert_called_once()
    args = mock_run.call_args.args[0]
    assert args == ["open", "-a", "TextEdit"]
    assert isinstance(args, list)


def test_app_open_denied_never_runs(home, mock_run):
    result = tools.app_open("Terminal")
    assert result.startswith("ERR not allowed")
    mock_run.assert_not_called()


def test_app_open_failure(home, mock_run):
    mock_run.return_value = subprocess.CompletedProcess([], 1, "", "Unable to find application")
    result = tools.app_open("TextEdit")
    assert result.startswith("ERR app_open 'TextEdit' failed")
    assert "Unable to find application" in result


def test_app_open_timeout(home, mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(["open"], 15)
    assert tools.app_open("TextEdit").startswith("ERR app_open 'TextEdit' failed")


def _mdfind_result(*paths):
    return subprocess.CompletedProcess([], 0, "".join(p + "\n" for p in paths), "")


def test_file_find_numbers_results(home, mock_run):
    mock_run.return_value = _mdfind_result("/Users/u/notes.txt", "/Users/u/report.pdf")
    result = tools.file_find("notes")
    assert result.startswith("OK file_find 'notes' | 2 results")
    assert "1. /Users/u/notes.txt" in result
    assert "2. /Users/u/report.pdf" in result
    args = mock_run.call_args.args[0]
    assert args[0:2] == ["mdfind", "-name"]
    assert "notes" in args
    assert "-onlyin" in args and str(Path.home()) in args
    assert isinstance(args, list)


def test_file_find_drops_hidden_and_library(home, mock_run):
    mock_run.return_value = _mdfind_result(
        "/Users/u/.cache/notes.txt",
        "/Users/u/Library/Preferences/notes.plist",
        "/Users/u/Documents/notes.txt",
    )
    result = tools.file_find("notes")
    assert "1. /Users/u/Documents/notes.txt" in result
    assert "2." not in result
    assert "Library" not in result and ".cache" not in result


def test_file_find_caps_at_10(home, mock_run):
    mock_run.return_value = _mdfind_result(*[f"/Users/u/f{i}.txt" for i in range(15)])
    result = tools.file_find("f")
    assert "| 10 results" in result
    assert "10. /Users/u/f9.txt" in result
    assert "f10" not in result


def test_file_find_no_results(home, mock_run):
    assert tools.file_find("zzz") == "OK file_find 'zzz' | 0 results"


def test_file_open_by_number(home, mock_run):
    mock_run.return_value = _mdfind_result("/Users/u/a.txt", "/Users/u/b.txt")
    tools.file_find("txt")
    assert tools.file_open(2) == "OK opened 2. /Users/u/b.txt"
    assert mock_run.call_args.args[0] == ["open", "/Users/u/b.txt"]


def test_file_open_bad_number(home, mock_run):
    mock_run.return_value = _mdfind_result("/Users/u/a.txt")
    tools.file_find("a")
    mock_run.reset_mock()
    assert tools.file_open(0) == "ERR no file 0; call file_find first"
    assert tools.file_open(5) == "ERR no file 5; call file_find first"
    mock_run.assert_not_called()


def test_file_open_without_find_first(home, mock_run, monkeypatch):
    monkeypatch.setattr(tools, "_last_files", [])
    assert tools.file_open(1) == "ERR no file 1; call file_find first"
    mock_run.assert_not_called()


def test_file_open_confirm_word_in_name(home, mock_run):
    mock_run.return_value = _mdfind_result("/Users/u/delete-me.txt")
    tools.file_find("delete")
    mock_run.reset_mock()
    assert tools.file_open(1) == "CONFIRM open file '/Users/u/delete-me.txt'"
    mock_run.assert_not_called()


def test_stop_file_blocks_every_tool(home, mock_run):
    (home / "STOP").touch()
    assert tools.app_open("TextEdit") == "ERR stopped by user"
    assert tools.file_find("notes") == "ERR stopped by user"
    assert tools.file_open(1) == "ERR stopped by user"
    mock_run.assert_not_called()


def test_actions_are_logged(home, mock_run):
    mock_run.return_value = _mdfind_result("/Users/u/a.txt")
    tools.app_open("TextEdit")
    tools.file_find("a")
    tools.file_open(1)
    lines = (home / "actions.log").read_text().splitlines()
    assert len(lines) == 3
    assert "ALLOW\tTextEdit\topen" in lines[0]
    assert "file_find\ta" in lines[1]
    assert "file_open\t/Users/u/a.txt" in lines[2]


def test_output_capped(home, mock_run):
    mock_run.return_value = _mdfind_result(*[f"/Users/u/{'x' * 140}{i}.txt" for i in range(10)])
    result = tools.file_find("x")
    assert len(result) <= config.MAX_CHARS
    assert result.endswith("[end]")
