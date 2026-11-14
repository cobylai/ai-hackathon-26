"""Shared fixtures: a local fixture-page server and a throwaway browser profile."""

from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

PAGES_DIR = Path(__file__).parent / "pages"


@pytest.fixture(autouse=True)
def isolated_page_cache(tmp_path, monkeypatch):
    """Keep the S7 page cache out of ~/.harness and out of other tests."""
    monkeypatch.setenv("HARNESS_CACHE_DB", str(tmp_path / "cache.db"))


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):  # silence server output in tests
        pass


class Site:
    """URL helper for pages served from tests/pages/."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def url(self, name: str) -> str:
        return f"{self.base_url}/{name.lstrip('/')}"


@pytest.fixture(scope="session")
def site():
    handler = partial(_QuietHandler, directory=str(PAGES_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Site(f"http://127.0.0.1:{server.server_address[1]}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def session(tmp_path):
    """A real Chromium session on a temporary profile, closed afterwards."""
    from harness.browser.session import Session

    s = Session(profile_dir=tmp_path / "profile")
    s.start()
    try:
        yield s
    finally:
        s.stop()
