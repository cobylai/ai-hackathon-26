"""B2: one persistent Chromium session loads a local page."""

import time

import pytest

from harness.browser.session import Session, get_session


def test_session_reads_title(session, site):
    session.page.goto(site.url("hello.html"))
    assert session.page.title() == "Hello Harness"


def test_page_property_is_stable(session, site):
    session.page.goto(site.url("hello.html"))
    assert session.page is session.page


def test_get_session_is_shared():
    assert get_session() is get_session()
    assert isinstance(get_session(), Session)


def test_profile_keeps_cookies_across_restarts(tmp_path):
    """B8 rests on this: a sign-in written by one session is visible to the next."""
    profile = tmp_path / "profile"
    first = Session(profile)
    first.start()
    try:
        first._context.add_cookies(
            [
                {
                    "name": "signed_in",
                    "value": "yes",
                    "domain": "example.com",
                    "path": "/",
                    "expires": time.time() + 3600,  # session cookies die with the browser
                }
            ]
        )
    finally:
        first.stop()

    second = Session(profile)
    second.start()
    try:
        cookies = {c["name"]: c["value"] for c in second._context.cookies("https://example.com")}
        assert cookies.get("signed_in") == "yes"
    finally:
        second.stop()



def test_failed_start_releases_playwright(monkeypatch, tmp_path):
    """A failed launch must not leave a driver behind (it poisons later starts)."""
    stopped = []

    class FakeChromium:
        def launch_persistent_context(self, *args, **kwargs):
            raise RuntimeError("profile locked")

    class FakePlaywright:
        chromium = FakeChromium()

        def stop(self):
            stopped.append(True)

    class FakeManager:
        def start(self):
            return FakePlaywright()

    monkeypatch.setattr("harness.browser.session.sync_playwright", lambda: FakeManager())

    session = Session(tmp_path / "profile")
    with pytest.raises(RuntimeError, match="profile locked"):
        session.start()
    assert stopped == [True]
    assert session._playwright is None
