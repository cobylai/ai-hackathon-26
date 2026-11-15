"""E1: signed-in detection, checked on local pages (no network)."""

from __future__ import annotations

from harness.email import status


def test_inbox_looks_signed_in(session, site):
    session.page.goto(site.url("gmail_list.html"))
    assert status.looks_signed_in(session.page)


def test_empty_result_page_looks_signed_in(session, site):
    session.page.goto(site.url("gmail_empty.html"))
    assert status.looks_signed_in(session.page)


def test_login_page_is_not_signed_in(session, site):
    session.page.goto(site.url("login.html"))
    assert not status.looks_signed_in(session.page)


def test_login_line_tells_the_user_what_to_run():
    assert status.LOGIN_LINE.startswith("LOGIN")
    assert "harness login https://mail.google.com" in status.LOGIN_LINE


def _dead_browser():
    def boom():
        raise RuntimeError("Failed to create a ProcessSingleton for your profile directory")

    return boom


def test_search_reports_a_dead_browser_cleanly(monkeypatch):
    from harness.email import search as search_mod

    monkeypatch.setattr(search_mod, "get_session", _dead_browser())
    out = search_mod.search(text="x")
    assert out.startswith("ERR")
    assert "browser did not start" in out


def test_read_reports_a_dead_browser_cleanly(monkeypatch):
    from harness.email import read, search

    monkeypatch.setattr(search, "last_rows", lambda: [search.Row(1, "A", "S", "D", "x", "t")])
    monkeypatch.setattr(read, "get_session", _dead_browser())
    assert "browser did not start" in read.read(1)


def test_asks_reports_a_dead_browser_cleanly(monkeypatch):
    from harness.email import asks

    monkeypatch.setattr(asks, "get_session", _dead_browser())
    assert "browser did not start" in asks.email_asks()


def test_draft_reports_a_dead_browser_cleanly(monkeypatch):
    from harness.email import draft

    monkeypatch.setattr(draft, "get_session", _dead_browser())
    assert "browser did not start" in draft.new("friend@example.edu", "s", "b")
