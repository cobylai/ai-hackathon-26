"""Create Gmail drafts. There is deliberately no send function here.

Safety comes first: clicking Compose can surface a draft Gmail restored from an
earlier session. This module refuses to touch anything that is not a blank
"New Message", and after typing it checks that the recipient list is exactly
the one address asked for with no Cc or Bcc. On any doubt it returns ``ERR``
and leaves the compose alone instead of saving.
"""

from __future__ import annotations

from playwright.sync_api import Page

from harness.browser.session import get_session
from harness.email import read, search, selectors
from harness.email.status import LOGIN_LINE, signed_in

DRAFT_SAVED = "OK draft saved"

# Reads the compose form around a body textbox: recipients, fields and region.
COMPOSE_STATE_JS = """el => {
  const region = el.closest('[role=region]');
  let root = el;
  while (root && !root.querySelector("input[name='subjectbox']")) root = root.parentElement;
  if (!root) root = region;
  if (!root) return null;
  const copy = el.cloneNode(true);
  copy.querySelectorAll('.gmail_quote, blockquote').forEach(n => n.remove());
  const val = sel => { const e = root.querySelector(sel); return e ? e.value : null; };
  return {
    region: region ? (region.getAttribute('aria-label') || '') : '',
    chips: [...root.querySelectorAll('[email]')].map(e => e.getAttribute('email')).filter(Boolean),
    to: val("input[aria-label='To recipients']"),
    cc: val("input[aria-label='Cc recipients']"),
    bcc: val("input[aria-label='Bcc recipients']"),
    subject: val("input[name='subjectbox']"),
    body: copy.textContent || ''
  };
}"""


def _short(exc: Exception) -> str:
    return " ".join(str(exc).split())[:100]


def _wait_visible(page: Page, name: str, timeout_ms: int = 15000):
    """First visible match for ``name``, polling; Gmail pre-renders hidden copies."""
    waited = 0
    while waited < timeout_ms:
        found = selectors.first_visible(page, name)
        try:
            if found.count() and found.is_visible():
                return found
        except Exception:
            pass
        page.wait_for_timeout(400)
        waited += 400
    return selectors.first_visible(page, name)


def _body_without_signature(text: str) -> str:
    """What the user typed, ignoring a ``-- `` signature block."""
    kept: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped in ("--", "-- ") or stripped.startswith("-- "):
            break
        if stripped:
            kept.append(stripped)
    return " ".join(kept).strip()


def compose_state(page: Page, body) -> dict | None:
    """Recipients, fields and region of the compose form that holds ``body``."""
    try:
        return body.evaluate(COMPOSE_STATE_JS)
    except Exception:
        return None


def blank_problem(state: dict | None) -> str:
    """Why this compose must not be typed into ("" when it is a fresh message)."""
    if not state:
        return "compose form not found"
    region = (state.get("region") or "").strip().lower()
    if region and "new message" not in region:
        return f"compose is not a new message ({state['region']})"
    found: list[str] = []
    chips = [chip for chip in (state.get("chips") or []) if chip]
    if chips:
        found.append(f"{len(chips)} recipient(s)")
    for key in ("to", "cc", "bcc", "subject"):
        if (state.get(key) or "").strip():
            found.append(key.capitalize())
    if _body_without_signature(state.get("body") or ""):
        found.append("body")
    return ("draft already has " + ", ".join(found)) if found else ""


def recipient_problem(state: dict | None, address: str) -> str:
    """Why the recipients are not exactly ``address`` with empty Cc and Bcc."""
    if not state:
        return "compose form not found"
    want = (address or "").strip().lower()
    chips = [chip.strip().lower() for chip in (state.get("chips") or []) if chip]
    typed = (state.get("to") or "").strip().lower()
    if chips != [want] and not (not chips and typed == want):
        shown = ", ".join(chips) if chips else (typed or "none")
        return f"recipients are {shown}; expected only {want}"
    for key in ("cc", "bcc"):
        if (state.get(key) or "").strip():
            return f"{key.upper()} is not empty"
    return ""


def close_open_composes(page: Page, limit: int = 5) -> int:
    """Save & close every compose that is open, leaving its content unchanged."""
    closed = 0
    for _ in range(limit):
        buttons = selectors.all_in(page, "compose_close")
        target = None
        for i in range(buttons.count()):
            try:
                if buttons.nth(i).is_visible():
                    target = buttons.nth(i)
            except Exception:
                continue
        if target is None:
            break
        target.click()
        page.wait_for_timeout(400)
        closed += 1
    return closed


def open_compose(page: Page) -> None:
    button = selectors.first_visible(page, "compose_button")
    if not button.count():
        raise RuntimeError("no Compose button")
    button.click()
    if not _wait_visible(page, "compose_to", timeout_ms=10000).count():
        raise RuntimeError("compose did not open")


def wait_saved(page: Page, timeout_ms: int = 20000) -> bool:
    label = _wait_visible(page, "draft_saved_label", timeout_ms=timeout_ms)
    try:
        return bool(label.count() and label.is_visible())
    except Exception:
        return False


def close_compose(page: Page) -> None:
    close = _wait_visible(page, "compose_close", timeout_ms=3000)
    if close.count():
        close.click()
        page.wait_for_timeout(500)


def new(to: str, subject: str, body: str) -> str:
    """Compose and save a new draft; returns ``OK draft saved`` or ``ERR ...``."""
    address = (to or "").strip()
    if not address:
        return "ERR mail.google.com | no recipient | give a to address"
    page = get_session().start().page
    if not signed_in(page):
        return LOGIN_LINE
    try:
        close_open_composes(page)
        open_compose(page)
        box = _wait_visible(page, "compose_body", timeout_ms=10000)
        if not box.count():
            return "ERR mail.google.com | compose did not open"

        problem = blank_problem(compose_state(page, box))
        if problem:
            close_compose(page)  # saves the restored draft unchanged
            return f"ERR mail.google.com | refused to edit a restored draft | {problem}"

        _wait_visible(page, "compose_to", timeout_ms=10000).fill(address)
        page.keyboard.press("Enter")  # turn the typed address into a chip
        page.wait_for_timeout(400)
        problem = recipient_problem(compose_state(page, box), address)
        if problem:
            return f"ERR mail.google.com | stopped before writing | {problem}"

        _wait_visible(page, "compose_subject").fill(subject or "")
        box.fill(body or "")
        page.wait_for_timeout(300)
        problem = recipient_problem(compose_state(page, box), address)
        if problem:
            return f"ERR mail.google.com | not saved | {problem}"
        if not wait_saved(page):
            close_compose(page)
            return "ERR mail.google.com | draft did not save | Gmail showed no 'Draft saved'"
        close_compose(page)
        return DRAFT_SAVED
    except Exception as exc:
        return f"ERR mail.google.com | draft failed | {_short(exc)}"


def reply(n: int, body: str) -> str:
    """Save a reply draft in thread ``n`` from the last search."""
    rows = search.last_rows()
    if not rows:
        return "ERR mail.google.com | no search results | call email_search first"
    try:
        index = int(n)
    except (TypeError, ValueError):
        index = 0
    if index < 1 or index > len(rows):
        return f"ERR mail.google.com | no row {n} | results are 1 to {len(rows)}"

    page = get_session().start().page
    if not signed_in(page):
        return LOGIN_LINE
    row = rows[index - 1]
    if not read.open_thread(page, row.thread_id):
        return "ERR mail.google.com | thread did not open | try email_search again"

    try:
        buttons = selectors.all_in(page, "reply_button")
        target = None
        for i in range(buttons.count()):
            try:
                if buttons.nth(i).is_visible():
                    target = buttons.nth(i)
            except Exception:
                continue
        if target is None:
            return "ERR mail.google.com | no Reply button | thread has no reply box"
        target.click()
        box = _wait_visible(page, "compose_body", timeout_ms=10000)
        if not box.count():
            return "ERR mail.google.com | reply box did not open"

        state = compose_state(page, box)
        if state and _body_without_signature(state.get("body") or ""):
            return "ERR mail.google.com | refused to edit a restored reply draft | body is not empty"

        box.fill(body or "")
        if not wait_saved(page):
            close_compose(page)
            return "ERR mail.google.com | draft did not save | Gmail showed no 'Draft saved'"
        close_compose(page)
        return DRAFT_SAVED
    except Exception as exc:
        return f"ERR mail.google.com | reply draft failed | {_short(exc)}"
