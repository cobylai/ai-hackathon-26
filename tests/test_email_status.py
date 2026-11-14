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
