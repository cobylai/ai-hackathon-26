"""Tests for ui_click and ui_type with the AX layer mocked (task C6)."""

import pytest

from harness import config
from harness.computer import permissions, policy, ui


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def controls(monkeypatch):
    """A fake last-listing and a TextEdit-like front app; AX calls recorded."""
    calls = {"press": [], "set_value": [], "type_text": []}
    fake_elements = [object(), object(), object()]
    monkeypatch.setattr(ui, "_last", [
        {"kind": "checkbox", "label": "bold", "element": fake_elements[0]},
        {"kind": "menuitem", "label": "Delete", "element": fake_elements[1]},
        {"kind": "textarea", "label": "(empty text area)", "element": fake_elements[2]},
    ])
    monkeypatch.setattr(permissions, "AXIsProcessTrusted", lambda: True)
    monkeypatch.setattr(ui, "_front_app", lambda: (1234, "TextEdit"))
    monkeypatch.setattr(ui, "_press", lambda el: calls["press"].append(el) or (True, ""))
    monkeypatch.setattr(ui, "_set_value",
                        lambda el, text: calls["set_value"].append((el, text)) or True)
    monkeypatch.setattr(ui, "_type_text",
                        lambda pid, text: calls["type_text"].append((pid, text)) or (True, ""))
    monkeypatch.setattr(ui, "_element_window_title", lambda el: "Untitled 1")
    return calls


def test_click_presses_element(home, controls):
    result = ui.ui_click(1)
    assert result == 'OK clicked 1. checkbox "bold" | Untitled 1'
    assert len(controls["press"]) == 1


def test_click_bad_number(home, controls):
    assert ui.ui_click(0) == "ERR no control 0; call ui first"
    assert ui.ui_click(9) == "ERR no control 9; call ui first"
    assert controls["press"] == []


def test_click_no_listing_first(home, monkeypatch):
    monkeypatch.setattr(ui, "_last", [])
    monkeypatch.setattr(permissions, "AXIsProcessTrusted", lambda: True)
    assert ui.ui_click(1) == "ERR no control 1; call ui first"


def test_click_confirm_word_needs_confirmation(home, controls):
    result = ui.ui_click(2)
    assert result.startswith("CONFIRM click 'Delete' on 'TextEdit'")
    assert "call again with token=" in result
    assert controls["press"] == []


def test_click_denied_app(home, controls, monkeypatch):
    monkeypatch.setattr(ui, "_front_app", lambda: (1234, "Terminal"))
    assert ui.ui_click(1) == "ERR not allowed: click 'bold' on 'Terminal'"
    assert controls["press"] == []


def test_click_press_failure(home, controls, monkeypatch):
    monkeypatch.setattr(ui, "_press", lambda el: (False, "AXPress error -25204"))
    result = ui.ui_click(1)
    assert result.startswith("ERR click 1 failed")
    assert "AXPress error -25204" in result


def test_type_sets_value(home, controls):
    result = ui.ui_type(3, "hello world")
    assert result == 'OK typed into 3. textarea "(empty text area)" | Untitled 1'
    el, text = controls["set_value"][0]
    assert text == "hello world"
    assert controls["type_text"] == []


def test_type_falls_back_to_keystrokes(home, controls, monkeypatch):
    monkeypatch.setattr(ui, "_set_value", lambda el, text: False)
    focused = []
    monkeypatch.setattr(ui, "_focus", lambda el: focused.append(el))
    result = ui.ui_type(3, "abc")
    assert result.startswith("OK typed into 3.")
    assert controls["type_text"] == [(1234, "abc")]
    assert len(focused) == 1


def test_type_fallback_failure(home, controls, monkeypatch):
    monkeypatch.setattr(ui, "_set_value", lambda el, text: False)
    monkeypatch.setattr(ui, "_type_text", lambda pid, text: (False, "no event tap"))
    result = ui.ui_type(3, "abc")
    assert result.startswith("ERR type 3 failed")
    assert "no event tap" in result


def test_type_confirm_word_in_label(home, controls):
    result = ui.ui_type(2, "x")
    assert result.startswith("CONFIRM type 'Delete' on 'TextEdit'")
    assert "call again with token=" in result
    assert controls["set_value"] == [] and controls["type_text"] == []


def test_stop_file_blocks_actions(home, controls):
    (home / "STOP").touch()
    assert ui.ui_click(1) == "ERR stopped by user"
    assert ui.ui_type(3, "x") == "ERR stopped by user"
    assert controls["press"] == [] and controls["set_value"] == []


def test_no_permission_blocks_actions(home, controls, monkeypatch):
    monkeypatch.setattr(permissions, "AXIsProcessTrusted", lambda: False)
    assert ui.ui_click(1) == permissions.NEEDED
    assert ui.ui_type(3, "x") == permissions.NEEDED
    assert controls["press"] == []


def test_actions_are_logged(home, controls):
    ui.ui_click(1)
    ui.ui_type(3, "hello")
    ui.ui_click(2)  # CONFIRM, still logged
    lines = (home / "actions.log").read_text().splitlines()
    assert len(lines) == 3
    assert "ALLOW\tTextEdit\tclick\tbold" in lines[0]
    assert "ALLOW\tTextEdit\ttype\t(empty text area)" in lines[1]
    assert "CONFIRM\tTextEdit\tclick\tDelete" in lines[2]
