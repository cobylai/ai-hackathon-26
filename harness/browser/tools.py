"""The six browser tools the model sees, all returning short plain text."""

from __future__ import annotations

import functools
from urllib.parse import urlparse

from playwright.sync_api import Page

from harness import config
from harness.browser import blocking, state
from harness.browser import elements as elements_mod
from harness.browser.session import get_session
from harness.browser.text import page_text, paginate

STATUS_WORDS = ("OK", "BLOCKED", "LOGIN", "ERR")

# Leave room for the status line inside the hard 1500-char answer cap.
TEXT_CHARS = max(200, config.MAX_CHARS - 160)

class BrowserStartError(RuntimeError):
    """Chromium could not be started (profile lock, missing build)."""


_blocked_page: Page | None = None


def _page() -> Page:
    """The shared page, with request blocking installed once."""
    global _blocked_page
    try:
        page = get_session().start().page
    except Exception as exc:
        text = " ".join(str(exc).split())
        if "ProcessSingleton" in text or "profile directory" in text:
            raise BrowserStartError(
                "profile in use; close the other Chromium window and retry"
            ) from exc
        raise BrowserStartError(f"browser failed to start: {text[:100]}") from exc
    if page is not _blocked_page:
        blocking.install(page)
        _blocked_page = page
    return page


def _domain(page: Page) -> str:
    host = urlparse(page.url).netloc or "local"
    return host[4:] if host.startswith("www.") else host


def _title(page: Page) -> str:
    try:
        title = " ".join(page.title().split())
    except Exception:
        title = ""
    return (title or "(untitled)")[:60]


def _text_of(page: Page) -> str:
    """Main text of the current page, with the visible body as a reference."""
    try:
        body = page.inner_text("body")
    except Exception:
        body = ""
    return page_text(page.content(), body)


def _status_line(word: str, page: Page, suffix: str = "") -> str:
    line = f"{word} {_domain(page)} | {_title(page)}"
    return f"{line} | {suffix}" if suffix else line


def _cutline(text: str, hint: str) -> str:
    """Trim to the 1500 cap on a line boundary, then add the hint."""
    room = config.MAX_CHARS - len(hint) - 1
    body = text[:room].rstrip()
    if "\n" in body:
        body = body.rsplit("\n", 1)[0]
    return f"{body}\n{hint}"


def _cap(text: str, hint: str = "[more: call read(page=2)]") -> str:
    text = text.strip()
    return text if len(text) <= config.MAX_CHARS else _cutline(text, hint)


def _note(word: str, page: Page, message: str) -> str:
    return _cap(_status_line(word, page, message), hint="[end]")


def _browser_tool(fn):
    """Turn a failed browser start into a clean ERR line instead of a traceback."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except BrowserStartError as exc:
            return _cap(f"ERR local | {exc}", hint="[end]")

    return wrapper


WEB_SCHEMES = ("http", "https")

# Scheme prefixes that must never reach the browser, with or without "//".
BLOCKED_SCHEMES = (
    "about",
    "blob",
    "chrome",
    "chrome-extension",
    "data",
    "file",
    "ftp",
    "javascript",
    "mailto",
    "view-source",
)


def _normalize_url(url: str) -> str:
    """Accept only web URLs; a page cannot lure the model into local files."""
    url = url.strip()
    if not url:
        raise ValueError("empty URL")
    if "://" in url:
        scheme = url.split("://", 1)[0].lower()
        if scheme not in WEB_SCHEMES:
            raise ValueError(f"unsupported URL scheme: {scheme}")
        return url
    if url.startswith("//"):
        return f"https:{url}"
    prefix = url.split(":", 1)[0].lower()
    if prefix in BLOCKED_SCHEMES:
        raise ValueError(f"unsupported URL scheme: {prefix}")
    return f"https://{url}"


@_browser_tool
def goto(url: str) -> str:
    """Open a URL; return status line, title and the first page of text."""
    try:
        target = _normalize_url(url)
    except ValueError as exc:
        return _cap(f"ERR local | {exc}", hint="[end]")
    page = _page()
    try:
        response = page.goto(target, wait_until="domcontentloaded", timeout=20000)
    except Exception as exc:
        message = " ".join(str(exc).split())[:80]
        return _cap(f"ERR {_domain(page)} | navigation failed | {message}", hint=message)

    status = response.status if response is not None else None
    word = state.classify(page, status=status)
    if word != "OK":
        message = {
            "BLOCKED": "bot check, try another result",
            "LOGIN": "password field, sign-in needed",
            "ERR": f"http {status}" if status else "page not usable",
        }[word]
        return _note(word, page, message)

    text = _text_of(page)
    chunk, total = paginate(text, 1, max_chars=TEXT_CHARS)
    hint = "[more: call read(page=2)]" if total > 1 else "[no more text]"
    return _cap(f"{_status_line('OK', page, f'page 1/{total}')}\n{chunk}", hint)


@_browser_tool
def read(page: int = 1) -> str:
    """Return page N of the current page's main text."""
    current = _page()
    word = state.classify(current)
    if word != "OK":
        message = {
            "BLOCKED": "bot check, try another result",
            "LOGIN": "password field, sign-in needed",
            "ERR": "page not usable",
        }[word]
        return _note(word, current, message)

    page = max(1, int(page))
    text = _text_of(current)
    chunk, total = paginate(text, page, max_chars=TEXT_CHARS)
    suffix = f"page {page}/{total}"
    if not chunk:
        return _cap(f"{_status_line('OK', current, suffix)}\n(no text on that page)")
    hint = f"[more: call read(page={page + 1})]" if page < total else "[end of text]"
    return _cap(f"{_status_line('OK', current, suffix)}\n{chunk}", hint)


@_browser_tool
def elements(filter: str | None = None) -> str:
    """List visible clickable and typeable items as numbered lines."""
    current = _page()
    listing, shown, matched = elements_mod.list_elements_counts(current, filter)
    word = state.classify(current)
    if word in ("BLOCKED", "LOGIN", "ERR"):
        listing = "(page is not usable; list may be incomplete)\n" + listing
    suffix = f"{shown} of {matched} elements" if shown < matched else f"{matched} elements"
    hint = "[more: call elements with a filter]"
    return _cap(f"{_status_line(word, current, suffix)}\n{listing}", hint)


@_browser_tool
def click(n: int) -> str:
    """Click element N from the last numbered list."""
    current = _page()
    try:
        elements_mod.click(current, n)
    except Exception as exc:
        message = " ".join(str(exc).split())[:80]
        return _cap(f"ERR {_domain(current)} | click {n} failed | {message}", hint=message)
    word = state.classify(current)
    return _cap(_status_line(word, current), hint="[end]")


@_browser_tool
def type(n: int, text: str, enter: int = 0) -> str:
    """Type text into element N; enter=1 also presses Enter."""
    current = _page()
    try:
        elements_mod.type_into(current, n, text, int(enter))
    except Exception as exc:
        message = " ".join(str(exc).split())[:80]
        return _cap(f"ERR {_domain(current)} | type into {n} failed | {message}", hint=message)
    suffix = f"typed {len(text)} chars" + (" + enter" if int(enter) else "")
    return _cap(_status_line("OK", current, suffix), hint="[end]")


@_browser_tool
def back() -> str:
    """Go back one page in the current tab."""
    current = _page()
    try:
        response = current.go_back(wait_until="domcontentloaded", timeout=20000)
    except Exception as exc:
        message = " ".join(str(exc).split())[:80]
        return _cap(f"ERR {_domain(current)} | back failed | {message}", hint=message)
    if response is None:
        return _cap(f"ERR {_domain(current)} | no history to go back to", hint="[end]")
    word = state.classify(current, status=response.status)
    return _cap(_status_line(word, current), hint="[end]")
