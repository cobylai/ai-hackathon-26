"""B3: images, media, fonts and filter-matched requests are aborted."""

from harness.browser.blocking import install, load_engine


def test_ads_page_still_reads(session, site):
    # A tiny stand-in for EasyList so the test works offline.
    engine = load_engine(extra_lists=["||doubleclick.net^"])
    stats = install(session.page, engine)
    failed = []
    session.page.on("requestfailed", lambda req: failed.append(req.url))

    session.page.goto(site.url("ads.html"))

    assert "readable text survives" in session.page.inner_text("body")
    assert any("doubleclick.net/x.js" in url for url in stats.urls)
    assert any(url.endswith("/pixel.png") for url in stats.urls)
    assert stats.blocked == 2
    assert len(failed) == 2
    assert set(stats.reasons) == {"filter", "image"}


def test_allowlisted_page_loads(session, site):
    engine = load_engine(extra_lists=["||doubleclick.net^"])
    stats = install(session.page, engine)
    session.page.goto(site.url("hello.html"))
    assert session.page.title() == "Hello Harness"
    assert stats.blocked == 0
    assert session.page.url.endswith("/hello.html")
