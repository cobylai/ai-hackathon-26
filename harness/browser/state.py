"""Tell the caller whether a page is usable, walled, a login or broken."""

from __future__ import annotations

from playwright.sync_api import Page

# Short list on purpose: a long list starts matching real articles.
BLOCKED_PHRASES = (
    "are you a robot",
    "unusual traffic",
    "verify you are human",
    "captcha",
    "access denied",
)

CHALLENGE_SELECTORS = (
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='challenges.cloudflare.com']",
    "iframe[src*='turnstile']",
)

# Cloudflare interstitial titles. Matched on the title only, and before the
# HTTP status check, because these pages come back as 403 or 503.
BLOCKED_TITLES = ("just a moment", "attention required")

# Sign-in pages whose first step has no password field yet.
LOGIN_URL_PREFIXES = (
    "https://accounts.google.com/",
    "https://login.microsoftonline.com/",
    "https://login.live.com/",
)

PASSWORD_SELECTOR = "input[type='password']:visible"


def _status(page: Page) -> int | None:
    """HTTP status of the main document, from navigation timing."""
    try:
        value = page.evaluate(
            "() => performance.getEntriesByType('navigation')[0]?.responseStatus ?? null"
        )
    except Exception:
        return None
    return int(value) if value else None


def _title_blocked(page: Page) -> bool:
    try:
        return page.title().strip().lower().startswith(BLOCKED_TITLES)
    except Exception:
        return False


def _looks_blocked(page: Page) -> bool:
    try:
        text = f"{page.title()}\n{page.inner_text('body')}".lower()
    except Exception:
        text = ""
    if any(phrase in text for phrase in BLOCKED_PHRASES):
        return True
    for selector in CHALLENGE_SELECTORS:
        try:
            if page.query_selector(selector) is not None:
                return True
        except Exception:
            continue
    return False


def _has_password_field(page: Page) -> bool:
    try:
        return page.locator(PASSWORD_SELECTOR).count() > 0
    except Exception:
        return False


def classify(
    page: Page,
    status: int | None = None,
    failed: bool = False,
) -> str:
    """Return ``OK``, ``BLOCKED``, ``LOGIN`` or ``ERR``.

    ``status`` and ``failed`` let the caller pass what ``goto`` already knows;
    both are inferred from the page when omitted.
    """
    if failed:
        return "ERR"
    url = ""
    try:
        url = page.url
    except Exception:
        return "ERR"
    if status is None:
        status = _status(page)
    if status is None and url.startswith(("about:", "chrome-error:", "")):
        return "ERR"
    if _title_blocked(page):
        return "BLOCKED"
    if status is not None and status >= 500:
        return "ERR"
    if _looks_blocked(page):
        return "BLOCKED"
    if status is not None and status >= 400:
        return "ERR"
    if _has_password_field(page) or url.startswith(LOGIN_URL_PREFIXES):
        return "LOGIN"
    return "OK"
