"""B3b: uBlock Origin Lite launch args and headless behaviour.

Findings on 2026-11-14 (uBOL 2026.1110.1816, Chromium 159): the extension does
load headless and blocks network requests, but the default Basic filtering mode
does no cosmetic filtering. Even in Complete mode the literal ``.ad-banner``
stays visible because no shipped list targets that selector; a selector EasyList
does list (``.ad-banner-content``) is hidden. See docs/plan/notes-ubol.md.
"""

import time

import pytest

from harness import config
from harness.browser.extensions import launch_args
from harness.browser.session import Session

UBOL_MANIFEST = config.EXTENSIONS_DIR / "ubol" / "manifest.json"
HAS_UBOL = UBOL_MANIFEST.is_file()
needs_ubol = pytest.mark.skipif(not HAS_UBOL, reason="run scripts/fetch_ubol.py first")


def _worker(context, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if context.service_workers:
            return context.service_workers[0]
        time.sleep(0.2)
    return None


def _set_filtering_mode(browser, level):
    """Raise uBOL's default mode the way its dashboard does (2=optimal, 3=complete)."""
    worker = _worker(browser._context)
    assert worker is not None
    extension_id = worker.url.split("/")[2]
    dashboard = browser._context.new_page()
    dashboard.goto(f"chrome-extension://{extension_id}/dashboard.html")
    result = dashboard.evaluate(
        "async (level) => await chrome.runtime.sendMessage("
        "{what:'setDefaultFilteringMode', level})",
        level,
    )
    dashboard.close()
    return result


def test_use_ubol_is_off_by_default():
    assert config.USE_UBOL is False


def test_no_args_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "USE_UBOL", False)
    assert launch_args() == []


def test_args_only_when_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "USE_UBOL", True)
    assert launch_args(tmp_path / "missing") == []


@needs_ubol
def test_args_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "USE_UBOL", True)
    args = launch_args()
    folder = config.EXTENSIONS_DIR / "ubol"
    assert f"--load-extension={folder}" in args
    assert f"--disable-extensions-except={folder}" in args


def test_banner_visible_without_extension(session, site):
    """With UBOL off (the default) both cosmetic ad elements are visible."""
    session.page.goto(site.url("ads.html"))
    assert session.page.locator(".ad-banner").is_visible()
    assert session.page.locator(".ad-banner-content").is_visible()


@needs_ubol
def test_headless_extension_loads_but_basic_mode_hides_no_cosmetics(monkeypatch, tmp_path, site):
    monkeypatch.setattr(config, "USE_UBOL", True)
    browser = Session(tmp_path / "profile")
    browser.start()
    try:
        failed = []
        browser.page.on("requestfailed", lambda req: failed.append((req.url, req.failure)))
        browser.page.goto(site.url("ads.html"))
        worker = _worker(browser._context)
        assert worker is not None
        assert worker.url.startswith("chrome-extension://")
        assert any(
            "doubleclick.net/x.js" in url and failure == "net::ERR_BLOCKED_BY_CLIENT"
            for url, failure in failed
        )
        assert browser.page.locator(".ad-banner").is_visible()
        assert browser.page.locator(".ad-banner-content").is_visible()
    finally:
        browser.stop()


@needs_ubol
def test_complete_mode_hides_a_listed_generic_banner(monkeypatch, tmp_path, site):
    """Cosmetic filtering works headless, but only from Complete mode and only
    for selectors that appear in the compiled lists."""
    monkeypatch.setattr(config, "USE_UBOL", True)
    browser = Session(tmp_path / "profile")
    browser.start()
    try:
        browser.page.goto(site.url("ads.html"))
        assert _set_filtering_mode(browser, 3) == 3

        for _ in range(20):
            browser.page.goto(site.url("ads.html"))
            if not browser.page.locator(".ad-banner-content").is_visible():
                break
            time.sleep(0.3)

        assert not browser.page.locator(".ad-banner-content").is_visible()
        assert browser.page.locator(".ad-banner").is_visible()
    finally:
        browser.stop()
