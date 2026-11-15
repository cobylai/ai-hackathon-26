"""B6: each kind of page gets the right label."""

from harness.browser.state import classify


def test_article_is_ok(session, site):
    session.page.goto(site.url("article.html"))
    assert classify(session.page) == "OK"


def test_captcha_page_is_blocked(session, site):
    session.page.goto(site.url("captcha.html"))
    assert classify(session.page) == "BLOCKED"


def test_challenge_iframe_is_blocked(session, site):
    session.page.goto(site.url("hello.html"))
    session.page.set_content(
        "<html><head><title>One moment</title></head><body>"
        "<iframe src='https://challenges.cloudflare.com/cdn-cgi/challenge-platform/x'></iframe>"
        "</body></html>"
    )
    assert classify(session.page) == "BLOCKED"


def test_duckduckgo_challenge_is_blocked(session, site):
    session.page.goto(site.url("hello.html"))
    session.page.set_content(
        "<html><head><title>DuckDuckGo</title></head><body>"
        "<p>Unfortunately, bots use DuckDuckGo too. Please complete the following "
        "challenge to confirm this search was made by a human. "
        "Select all squares containing a duck:</p></body></html>"
    )
    assert classify(session.page) == "BLOCKED"


def test_login_page_is_login(session, site):
    session.page.goto(site.url("login.html"))
    assert classify(session.page) == "LOGIN"


def test_hidden_password_field_is_not_login(session, site):
    session.page.goto(site.url("hello.html"))
    session.page.set_content(
        "<html><head><title>Members</title></head><body>"
        "<div style='display:none'><input type='password'></div>"
        "<p>Members area</p></body></html>"
    )
    assert classify(session.page) == "OK"


def test_http_error_is_err(session, site):
    session.page.goto(site.url("missing-page.html"))
    assert classify(session.page) == "ERR"


def test_navigation_failure_is_err(session):
    try:
        session.page.goto("http://127.0.0.1:1/", timeout=2000)
    except Exception:
        pass
    assert classify(session.page, failed=True) == "ERR"
