"""B3: images, media, fonts and filter-matched requests are aborted."""

from harness.browser.blocking import install, load_engine


def _offline_engine(tmp_path):
    # A tiny stand-in for EasyList so the tests never depend on downloads.
    return load_engine(directory=tmp_path / "no-filters", extra_lists=["||doubleclick.net^"])


def test_ads_page_still_reads(session, site, tmp_path):
    stats = install(session.page, _offline_engine(tmp_path))
    failed = []
    session.page.on("requestfailed", lambda req: failed.append(req.url))

    session.page.goto(site.url("ads.html"))

    assert "readable text survives" in session.page.inner_text("body")
    assert any("doubleclick.net/x.js" in url for url in stats.urls)
    assert any(url.endswith("/pixel.png") for url in stats.urls)
    assert stats.blocked == 2
    assert len(failed) == 2
    assert set(stats.reasons) == {"filter", "image"}


def test_allowlisted_page_loads(session, site, tmp_path):
    stats = install(session.page, _offline_engine(tmp_path))
    session.page.goto(site.url("hello.html"))
    assert session.page.title() == "Hello Harness"
    assert stats.blocked == 0
    assert session.page.url.endswith("/hello.html")


def test_empty_engine_only_blocks_non_text_resources(session, site, tmp_path):
    stats = install(session.page, load_engine(directory=tmp_path / "no-filters"))
    session.page.goto(site.url("ads.html"))
    assert stats.blocked == 1
    assert stats.reasons == ["image"]
