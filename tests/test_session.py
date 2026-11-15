"""B2: one persistent Chromium session loads a local page."""

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
