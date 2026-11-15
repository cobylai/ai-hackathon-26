"""B7: every tool returns a short, status-led string; registry and CLI work."""

import inspect
import os
import subprocess
import sys
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
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(
        Path(os.path.expanduser("~")) / "Library" / "Caches" / "ms-playwright"
    )
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
