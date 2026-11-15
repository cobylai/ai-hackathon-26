"""One hidden Chromium with a persistent profile, shared for the session."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from harness import config
from harness.browser.extensions import launch_args


class Session:
    """A persistent-context Chromium that stays up between tool calls."""

    def __init__(self, profile_dir: str | Path | None = None) -> None:
        self.profile_dir = Path(profile_dir) if profile_dir else config.PROFILE_DIR
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def start(self) -> "Session":
        """Launch Chromium with the bundled full build in new headless mode."""
        if self._context is not None:
            return self
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            str(self.profile_dir),
            # "chromium" (not the default headless shell) so the full build runs
            # in new headless mode; extensions only load there too (B3b).
            channel="chromium",
            headless=True,
            args=["--headless=new", *launch_args()],
        )
        pages = self._context.pages
        self._page = pages[0] if pages else self._context.new_page()
        return self

    @property
    def page(self) -> Page:
        if self._context is None:
            raise RuntimeError("session not started; call start() first")
        if self._page is None or self._page.is_closed():
            pages = self._context.pages
            self._page = pages[0] if pages else self._context.new_page()
        return self._page

    def stop(self) -> None:
        """Close the browser and stop Playwright. Safe to call twice."""
        if self._context is not None:
            try:
                self._context.close()
            finally:
                self._context = None
                self._page = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            finally:
                self._playwright = None


_session: Session | None = None


def get_session() -> Session:
    """Return the one shared session, starting it on first use."""
    global _session
    if _session is None:
        _session = Session()
    return _session
