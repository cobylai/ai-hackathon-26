"""B2: one persistent Chromium session loads a local page."""

import os
import subprocess
import sys
from pathlib import Path

from harness.browser.session import Session, get_session

ROOT = Path(__file__).resolve().parents[1]


def test_session_reads_title(session, site):
    session.page.goto(site.url("hello.html"))
    assert session.page.title() == "Hello Harness"


def test_page_property_is_stable(session, site):
    session.page.goto(site.url("hello.html"))
    assert session.page is session.page


def test_get_session_is_shared():
    assert get_session() is get_session()
    assert isinstance(get_session(), Session)


def test_restart_reopens_the_browser(session, site):
    session.page.goto(site.url("hello.html"))
    assert session.page.title() == "Hello Harness"
    session.restart()
    session.page.goto(site.url("hello.html"))
    assert session.page.title() == "Hello Harness"


def profile_dir_from_env(env: dict) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", "from harness import config; print(config.PROFILE_DIR)"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_profile_dir_defaults_to_home():
    env = {k: v for k, v in os.environ.items() if k != "HARNESS_PROFILE_DIR"}
    assert profile_dir_from_env(env) == str(Path.home() / ".harness" / "profile")


def test_profile_dir_can_be_overridden(tmp_path):
    # Lets a second harness process (an eval, a test run) keep its own profile
    # while another one holds the default.
    env = dict(os.environ, HARNESS_PROFILE_DIR=str(tmp_path / "other-profile"))
    assert profile_dir_from_env(env) == str(tmp_path / "other-profile")
