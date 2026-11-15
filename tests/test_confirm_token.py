"""Tests for one-time confirmation tokens (the C3 CONFIRM seam)."""

import re
import subprocess
from unittest.mock import MagicMock

import pytest

from harness import config
from harness.computer import direct, permissions, policy, tools, ui


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME_DIR", tmp_path)
    return tmp_path


def _token_from(line: str) -> str:
    return re.search(r"token=([0-9a-f]+)", line).group(1)


def test_issue_and_consume_roundtrip(home):
    token = policy.issue_token("TextEdit", "click", "Delete", home)
    assert re.fullmatch(r"[0-9a-f]{6}", token)
    assert policy.consume_token("TextEdit", "click", "Delete", token, home) is True


def test_token_is_one_time(home):
    token = policy.issue_token("TextEdit", "click", "Delete", home)
    assert policy.consume_token("TextEdit", "click", "Delete", token, home) is True
    assert policy.consume_token("TextEdit", "click", "Delete", token, home) is False


def test_token_must_match_the_action(home):
    token = policy.issue_token("TextEdit", "click", "Delete", home)
    # same token, different label: no match, and the token is spent anyway
    assert policy.consume_token("TextEdit", "click", "Duplicate", token, home) is False
    assert policy.consume_token("TextEdit", "click", "Delete", token, home) is False


def test_unknown_and_empty_tokens_rejected(home):
    assert policy.consume_token("TextEdit", "click", "Delete", "ffffff", home) is False
    assert policy.consume_token("TextEdit", "click", "Delete", "", home) is False


def test_tokens_survive_across_calls(home):
    """confirms.json persists, so a replay works from another process."""
    token = policy.issue_token("Finder", "file_open", "/x/delete.txt", home)
    assert (home / "confirms.json").exists()
    assert policy.consume_token("Finder", "file_open", "/x/delete.txt", token, home) is True


# --- tool-level flow ---------------------------------------------------------


@pytest.fixture
def mock_run(monkeypatch):
    run = MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(direct.subprocess, "run", run)
    return run


def test_file_open_confirm_then_token_replay(home, mock_run):
    mock_run.return_value = subprocess.CompletedProcess(
        [], 0, "/Users/u/delete-me.txt\n", ""
    )
    tools.file_find("delete")
    mock_run.reset_mock()

    first = tools.file_open(1)
    assert first.startswith("CONFIRM")
    mock_run.assert_not_called()

    token = _token_from(first)
    second = tools.file_open(1, token=token)
    assert second == "OK opened 1. /Users/u/delete-me.txt"
    mock_run.assert_called_once()

    # the same token cannot authorize a third call
    mock_run.reset_mock()
    third = tools.file_open(1, token=token)
    assert third.startswith("CONFIRM")
    mock_run.assert_not_called()

    lines = (home / "actions.log").read_text().splitlines()
    verdicts = [line.split("\t")[1] for line in lines]
    assert verdicts[-3:] == ["CONFIRM", "CONFIRMED", "CONFIRM"]


def test_token_does_not_override_deny(home, mock_run):
    token = policy.issue_token("Terminal", "open", "")
    result = tools.app_open("Terminal", token=token)
    assert result.startswith("ERR not allowed")
    mock_run.assert_not_called()


def test_wrong_token_leaves_confirm(home, mock_run):
    mock_run.return_value = subprocess.CompletedProcess(
        [], 0, "/Users/u/delete-me.txt\n", ""
    )
    tools.file_find("delete")
    mock_run.reset_mock()
    result = tools.file_open(1, token="000000")
    assert result.startswith("CONFIRM")
    mock_run.assert_not_called()


@pytest.fixture
def ui_controls(monkeypatch):
    calls = {"press": []}
    monkeypatch.setattr(ui, "_last", [
        {"kind": "menuitem", "label": "Delete", "element": object()},
    ])
    monkeypatch.setattr(permissions, "AXIsProcessTrusted", lambda: True)
    monkeypatch.setattr(ui, "_front_app", lambda: (1234, "TextEdit"))
    monkeypatch.setattr(ui, "_press", lambda el: calls["press"].append(el) or (True, ""))
    monkeypatch.setattr(ui, "_element_window_title", lambda el: "Doc")
    return calls


def test_ui_click_confirm_then_token_replay(home, ui_controls):
    first = ui.ui_click(1)
    assert first.startswith("CONFIRM")
    assert ui_controls["press"] == []
    second = ui.ui_click(1, token=_token_from(first))
    assert second == 'OK clicked 1. menuitem "Delete" | Doc'
    assert len(ui_controls["press"]) == 1


def test_stop_file_beats_token(home, mock_run):
    mock_run.return_value = subprocess.CompletedProcess(
        [], 0, "/Users/u/delete-me.txt\n", ""
    )
    tools.file_find("delete")
    token = _token_from(tools.file_open(1))
    (home / "STOP").touch()
    assert tools.file_open(1, token=token) == "ERR stopped by user"
