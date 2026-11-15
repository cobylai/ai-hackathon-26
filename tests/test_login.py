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

    code = login_mod.login("https://example.com/", tmp_path / "profile", verify=False)

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


def test_sign_in_reports_the_profile_check(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(login_mod, "chromium_path", lambda: "/fake/Chromium")
    monkeypatch.setattr(login_mod, "profile_locked", lambda profile: False)
    monkeypatch.setattr(login_mod.subprocess, "run", lambda cmd: type("R", (), {"returncode": 0})())
    monkeypatch.setattr(session_mod, "get_session", lambda: _StoppedSession())
    monkeypatch.setattr(
        login_mod, "_verify", lambda url, profile: "OK example.com | Example Domain | sign-in check"
    )

    assert login_mod.login("https://example.com/", tmp_path / "profile") == 0
    out = capsys.readouterr().out
    assert "checking the profile" in out
    assert "OK example.com | Example Domain | sign-in check" in out


def test_sign_in_returns_one_when_check_says_login(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(login_mod, "chromium_path", lambda: "/fake/Chromium")
    monkeypatch.setattr(login_mod, "profile_locked", lambda profile: False)
    monkeypatch.setattr(login_mod.subprocess, "run", lambda cmd: type("R", (), {"returncode": 0})())
    monkeypatch.setattr(session_mod, "get_session", lambda: _StoppedSession())
    monkeypatch.setattr(
        login_mod, "_verify", lambda url, profile: "LOGIN example.com | Sign in | sign-in check"
    )

    assert login_mod.login("https://example.com/", tmp_path / "profile") == 1
    assert "LOGIN example.com" in capsys.readouterr().out


def test_verify_retries_a_locked_profile(monkeypatch, tmp_path):
    starts = {"n": 0}

    class FakePage:
        url = "https://example.com/"

        def goto(self, *args, **kwargs):
            return type("R", (), {"status": 200})()

        def title(self):
            return "Example Domain"

    class FakeSession:
        def __init__(self, profile):
            self.profile = profile

        def start(self):
            starts["n"] += 1
            if starts["n"] == 1:
                raise RuntimeError("Failed to create a ProcessSingleton")
            return self

        @property
        def page(self):
            return FakePage()

        def stop(self):
            pass

    monkeypatch.setattr("harness.browser.session.Session", FakeSession)
    monkeypatch.setattr("harness.browser.state.classify", lambda page, status=None: "OK")
    monkeypatch.setattr(login_mod.time, "sleep", lambda seconds: None)

    result = login_mod._verify("https://example.com/", tmp_path)
    assert result == "OK example.com | Example Domain | sign-in check"
    assert starts["n"] == 2


def test_verify_gives_up_after_attempts(monkeypatch, tmp_path):
    class BadSession:
        def __init__(self, profile):
            self.profile = profile

        def start(self):
            raise RuntimeError("profile locked")

        def stop(self):
            pass

    monkeypatch.setattr("harness.browser.session.Session", BadSession)
    monkeypatch.setattr(login_mod.time, "sleep", lambda seconds: None)

    result = login_mod._verify("https://example.com/", tmp_path)
    assert result.startswith("ERR example.com")
    assert "could not start" in result
    assert "profile locked" in result
