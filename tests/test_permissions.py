"""Tests for the accessibility permission check (task C2)."""

from harness.computer import permissions, ui


def test_accessibility_ok_true(monkeypatch):
    monkeypatch.setattr(permissions, "AXIsProcessTrusted", lambda: True)
    assert permissions.accessibility_ok() is True


def test_accessibility_ok_false(monkeypatch):
    monkeypatch.setattr(permissions, "AXIsProcessTrusted", lambda: False)
    assert permissions.accessibility_ok() is False


def test_accessibility_ok_without_pyobjc(monkeypatch):
    monkeypatch.setattr(permissions, "AXIsProcessTrusted", None)
    assert permissions.accessibility_ok() is False


def test_ui_returns_err_when_not_trusted(monkeypatch, tmp_path):
    """The false path: the ui tool refuses before touching any app."""
    monkeypatch.setattr(permissions, "AXIsProcessTrusted", lambda: False)
    monkeypatch.setattr(ui, "_front_app", lambda: (_ for _ in ()).throw(AssertionError("must not reach")))
    result = ui.list_controls()
    assert result == permissions.NEEDED
    assert result.startswith("ERR accessibility permission needed")
    assert ui._last == []
