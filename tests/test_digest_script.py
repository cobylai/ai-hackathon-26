"""The digest entry point is safe to run unattended."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location(
        "daily_digest", ROOT / "scripts" / "daily_digest.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_busy_profile_is_one_clean_line(monkeypatch, capsys):
    script = _script()

    def boom(**kwargs):
        raise RuntimeError("Failed to create a ProcessSingleton for your profile directory")

    monkeypatch.setattr(script.digest, "build", boom)
    assert script.main(["--days", "1"]) == 2
    out = capsys.readouterr().out
    assert out.startswith("ERR gmail | digest failed |")
    assert "ProcessSingleton" in out


def test_output_file_is_written(monkeypatch, tmp_path, capsys):
    script = _script()
    text = "OK 1 threads, 1 asks | newer_than:1d\n1. Subject (1)\n   - Is this due Friday?"
    monkeypatch.setattr(script.digest, "build", lambda **kwargs: text)
    target = tmp_path / "digest.txt"
    assert script.main(["--output", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == text + "\n"


def test_login_result_exits_one(monkeypatch, capsys):
    script = _script()
    monkeypatch.setattr(
        script.digest, "build", lambda **kwargs: "LOGIN mail.google.com | sign-in needed"
    )
    assert script.main([]) == 1
    assert "LOGIN" in capsys.readouterr().out
