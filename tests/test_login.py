import os

from harness.browser import login as login_mod
from harness.browser import session as session_mod
from harness.browser.login import profile_locked


def test_no_lock_means_free(tmp_path):
    assert not profile_locked(tmp_path)


def test_stale_lock_is_free(tmp_path):
    os.symlink("host-99999999", tmp_path / "SingletonLock")
    assert not profile_locked(tmp_path)


def test_live_lock_is_locked(tmp_path):
    os.symlink(f"host-{os.getpid()}", tmp_path / "SingletonLock")
    assert profile_locked(tmp_path)


class _StoppedSession:
    def stop(self):
        self.stopped = True


def test_sign_in_command_has_no_automation_flags(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd):
        captured["cmd"] = cmd
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(login_mod, "chromium_path", lambda: "/fake/Chromium")
    monkeypatch.setattr(login_mod, "profile_locked", lambda profile: False)
    monkeypatch.setattr(login_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(session_mod, "get_session", lambda: _StoppedSession())

    code = login_mod.login("https://example.com/", tmp_path / "profile")

    cmd = captured["cmd"]
    assert code == 0
    assert cmd[0] == "/fake/Chromium"
    assert f"--user-data-dir={tmp_path / 'profile'}" in cmd
    assert cmd[-1] == "https://example.com/"
    assert "--use-mock-keychain" in cmd
    assert not [arg for arg in cmd if arg.startswith(("--remote-debugging", "--headless"))]
    assert "--enable-automation" not in cmd
    assert not [arg for arg in cmd if "AutomationControlled" in arg]


def test_sign_in_refuses_a_locked_profile(monkeypatch, tmp_path):
    launched = []
    monkeypatch.setattr(login_mod, "profile_locked", lambda profile: True)
    monkeypatch.setattr(login_mod.subprocess, "run", lambda *args, **kwargs: launched.append(args))
    monkeypatch.setattr(session_mod, "get_session", lambda: _StoppedSession())

    assert login_mod.login("https://example.com/", tmp_path / "profile") == 1
    assert launched == []
