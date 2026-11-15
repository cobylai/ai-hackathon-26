"""B7: every tool returns a short, status-led string; registry and CLI work."""

import inspect
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harness import registry

ROOT = Path(__file__).resolve().parents[1]
STATUS_WORDS = {"OK", "BLOCKED", "LOGIN", "ERR"}


def check(result: str) -> str:
    assert isinstance(result, str)
    assert len(result) <= 1500, f"{len(result)} chars"
    assert result.split()[0] in STATUS_WORDS, result[:80]
    return result


@pytest.fixture()
def btools(session, monkeypatch):
    from harness.browser import tools

    monkeypatch.setattr(tools, "get_session", lambda: session)
    return tools


def number_of(listing: str, needle: str) -> int:
    for line in listing.splitlines():
        if needle in line:
            return int(line.split(".")[0])
    raise AssertionError(f"{needle!r} not in listing:\n{listing}")


def test_goto_and_read(btools, site):
    out = check(btools.goto(site.url("article.html")))
    assert out.startswith("OK 127.0.0.1:")
    assert "The Lighthouse Keeper" in out
    assert "page 1/" in out
    assert "lighthouse stood at the end" in out

    second = check(btools.read(2))
    assert "page 2/" in second
    assert "NAVLINK" not in second


def test_read_past_the_end(btools, site):
    btools.goto(site.url("article.html"))
    out = check(btools.read(99))
    assert "no text on that page" in out


def test_elements_lists_controls(btools, site):
    btools.goto(site.url("form.html"))
    out = check(btools.elements())
    assert out.startswith("OK")
    assert 'button "Submit"' in out
    assert out.splitlines()[0].endswith("elements")


def test_type_then_click(btools, session, site):
    btools.goto(site.url("form.html"))
    listing = btools.elements()
    field = number_of(listing, "Search terms")
    button = number_of(listing, "Submit")
    check(btools.type(field, "hello harness", 0))
    check(btools.click(button))
    assert "Submitted: hello harness" in session.page.inner_text("#result")


def test_back(btools, site):
    btools.goto(site.url("article.html"))
    btools.goto(site.url("hello.html"))
    out = check(btools.back())
    assert out.startswith("OK")
    assert "The Lighthouse Keeper" in out


def test_blocked_and_login_pages(btools, site):
    blocked = check(btools.goto(site.url("captcha.html")))
    assert blocked.startswith("BLOCKED")
    login = check(btools.goto(site.url("login.html")))
    assert login.startswith("LOGIN")


def test_navigation_failure(btools):
    out = check(btools.goto("http://127.0.0.1:1/"))
    assert out.startswith("ERR")


def test_cli_prints_status_and_text(tmp_path, site):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    # HOME is redirected, so point the subprocess at the real browser cache;
    # it lives under Library/Caches on macOS and .cache on Linux (CI).
    real_home = Path(os.path.expanduser("~"))
    for cache in (
        real_home / "Library" / "Caches" / "ms-playwright",
        real_home / ".cache" / "ms-playwright",
    ):
        if cache.exists():
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(cache)
            break
    proc = subprocess.run(
        [sys.executable, "-m", "harness", "goto", site.url("hello.html")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("OK")
    assert "Hello Harness" in proc.stdout


def test_registry_shape():
    assert {"goto", "read", "elements", "click", "type", "back"} <= set(registry.TOOLS)
    for group, names in registry.GROUPS.items():
        assert set(names) <= set(registry.TOOLS), group
    assert registry.GROUPS["web"] == [
        "goto",
        "read",
        "elements",
        "click",
        "type",
        "back",
    ]
    assert registry.GROUPS["computer"] == [
        "app_open",
        "file_find",
        "file_open",
        "ui",
        "ui_click",
        "ui_type",
    ]
    for name, tool in registry.TOOLS.items():
        assert tool.name == name
        assert tool.desc and "\n" not in tool.desc
        assert len(tool.desc) <= 100
        assert len(tool.args) <= 3
        assert all(value in (str, int) for value in tool.args.values())
        params = list(inspect.signature(tool.run).parameters)
        # "filter" is optional, so compare as sets.
        assert set(params) == set(tool.args)


def test_output_cap_on_long_text(btools):
    assert len(btools._cap("x" * 5000, "[more: call read(page=2)]")) <= 1500
    assert btools._cap("short") == "short"


def test_click_after_navigation_is_refused(btools, site):
    btools.goto(site.url("form.html"))
    n = number_of(btools.elements(), "Submit")
    btools.goto(site.url("hello.html"))
    out = check(btools.click(n))
    assert out.startswith("ERR")
    assert "elements again" in out


def test_locked_profile_returns_err(monkeypatch):
    from harness.browser import tools

    class Broken:
        def start(self):
            raise RuntimeError(
                "Failed to create a ProcessSingleton for your profile directory."
            )

    monkeypatch.setattr(tools, "get_session", lambda: Broken())
    out = check(tools.goto("https://example.com"))
    assert out.startswith("ERR local")
    assert "profile in use" in out


def test_other_start_failure_returns_err(monkeypatch):
    from harness.browser import tools

    class Broken:
        def start(self):
            raise RuntimeError("Executable doesn't exist at /nowhere")

    monkeypatch.setattr(tools, "get_session", lambda: Broken())
    out = check(tools.back())
    assert out.startswith("ERR local")
    assert "browser failed to start" in out


def test_elements_reports_truncation(btools, session, site):
    btools.goto(site.url("hello.html"))
    links = "".join(f'<a href="/x{i}">Headline number {i}</a>\n' for i in range(45))
    session.page.set_content(f"<html><body>{links}</body></html>")
    out = check(btools.elements())
    assert out.splitlines()[0].endswith("40 of 45 elements")


def test_second_process_on_live_profile_returns_err(monkeypatch, tmp_path):
    """A real second Chromium holding the profile is what users hit with B8."""
    from harness.browser import tools as tools_mod
    from harness.browser.session import Session as _Session

    profile = tmp_path / "profile"
    code = (
        "import time\n"
        "from harness.browser.session import Session\n"
        f"s = Session({str(profile)!r})\n"
        "s.start()\n"
        "time.sleep(20)\n"
        "s.stop()\n"
    )
    holder = subprocess.Popen([sys.executable, "-c", code], cwd=ROOT)
    try:
        deadline = time.time() + 30
        # SingletonLock is a dangling symlink, so is_symlink() is the right test.
        lock = profile / "SingletonLock"
        while time.time() < deadline and not lock.is_symlink():
            time.sleep(0.1)
        assert lock.is_symlink(), "holder never started"

        monkeypatch.setattr(tools_mod, "get_session", lambda: _Session(profile))
        out = check(tools_mod.goto("https://example.com"))
        assert out.startswith("ERR local")
        assert "profile in use" in out
    finally:
        holder.terminate()
        try:
            holder.wait(timeout=10)
        except subprocess.TimeoutExpired:
            holder.kill()


def test_read_on_blocked_page(btools, site):
    btools.goto(site.url("captcha.html"))
    out = check(btools.read(1))
    assert out.startswith("BLOCKED")
    assert "bot check" in out


def test_elements_on_blocked_page(btools, site):
    btools.goto(site.url("captcha.html"))
    out = check(btools.elements())
    assert out.startswith("BLOCKED")
    assert "list may be incomplete" in out


def test_type_into_a_link_is_err(btools, site):
    btools.goto(site.url("form.html"))
    link = number_of(btools.elements(), "Help page")
    out = check(btools.type(link, "nope"))
    assert out.startswith("ERR")
    assert "type into" in out


def test_back_without_history_is_err(btools, site):
    btools.goto(site.url("hello.html"))
    out = check(btools.back())
    assert out.startswith("ERR")
    assert "no history" in out


def test_goto_rejects_local_and_script_schemes():
    from harness.browser import tools as tools_mod

    for url in (
        "file:///etc/passwd",
        "data:text/html,<h1>hi</h1>",
        "about:blank",
        "javascript:alert(1)",
        "ftp://example.com/",
        "chrome://settings",
        "chrome-extension://abc/page.html",
    ):
        with pytest.raises(ValueError, match="unsupported URL scheme"):
            tools_mod._normalize_url(url)


def test_goto_builds_https_for_bare_hosts():
    from harness.browser import tools as tools_mod

    assert tools_mod._normalize_url("example.com/x") == "https://example.com/x"
    assert tools_mod._normalize_url(" https://example.com ") == "https://example.com"
    assert tools_mod._normalize_url("127.0.0.1:8000/x") == "https://127.0.0.1:8000/x"
    assert tools_mod._normalize_url("//example.com/x") == "https://example.com/x"
    with pytest.raises(ValueError, match="empty URL"):
        tools_mod._normalize_url("   ")


def test_goto_file_url_returns_err(btools):
    out = check(btools.goto("file:///etc/passwd"))
    assert out.startswith("ERR local")
    assert "unsupported URL scheme" in out
