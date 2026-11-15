"""``email_read``: open thread n from the last search and return its messages.

Gmail shows oldest first and folds quoted replies; this returns newest first,
with quoted text and signatures removed, wrapped in ``<email>`` tags so the
model treats the text as data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Page

from harness import config
from harness.browser.session import get_session
from harness.browser.text import paginate
from harness.email import search, selectors
from harness.email.status import BROWSER_LINE, LOGIN_LINE, signed_in

THREAD_URL = "https://mail.google.com/mail/u/0/#all/{thread_id}"
QUOTE_HEADER = re.compile(r"^On .{0,120} wrote:$")
BODY_JS = """el => {
  const copy = el.cloneNode(true);
  copy.querySelectorAll('.gmail_quote, blockquote').forEach(n => n.remove());
  const body = copy.querySelector('.a3s');
  if (!body) return '';
  // innerText needs a laid-out node, so park the copy off-screen briefly.
  const host = document.createElement('div');
  host.style.cssText = 'position:absolute;left:-9999px;top:0;width:600px';
  host.appendChild(copy);
  document.body.appendChild(host);
  const text = body.innerText;
  host.remove();
  return text;
}"""


@dataclass(frozen=True)
class Message:
    sender: str
    date: str
    body: str
    attachments: tuple[str, ...] = ()


def clean_body(raw: str) -> str:
    """Drop a quoted-reply header and anything after the ``-- `` signature."""
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped in ("--", "-- ") or stripped.startswith("-- "):
            break
        if QUOTE_HEADER.match(stripped) or stripped.startswith("-----Original Message-----"):
            break
        lines.append(line.rstrip())
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _sender(message) -> str:
    loc = selectors.locator(message, "message_sender")
    name = ""
    try:
        name = " ".join(loc.inner_text().split())
    except Exception:
        pass
    address = ""
    try:
        if loc.count():
            address = loc.get_attribute("email") or ""
    except Exception:
        pass
    if name and address and address not in name:
        return f"{name} <{address}>"
    return name or address


def _date(message) -> str:
    loc = selectors.locator(message, "message_date")
    try:
        if loc.count():
            return " ".join((loc.get_attribute("title") or loc.inner_text()).split())
    except Exception:
        pass
    return ""


def _body(message) -> str | None:
    """Body text without quoted replies, or None while the message is folded."""
    try:
        if not selectors.locator(message, "message_body").count():
            return None
        return message.evaluate(BODY_JS)
    except Exception:
        return ""


def open_thread(page: Page, thread_id: str) -> bool:
    """Load a thread with a full page load.

    A thread URL is a hash change, so Gmail swaps the URL first and keeps the
    previous thread's messages on screen for a while; waiting for those would
    read the wrong mail. Reloading the same URL always renders that thread.
    """
    page.goto(THREAD_URL.format(thread_id=thread_id), wait_until="domcontentloaded", timeout=60000)
    try:
        page.reload(wait_until="domcontentloaded", timeout=60000)
    except Exception:
        pass
    return _wait_messages(page, timeout_ms=20000)


def _any_body(page: Page) -> bool:
    items = selectors.all_in(page, "thread_message")
    return any(selectors.locator(items.nth(i), "message_body").count() for i in range(items.count()))


def wait_for_thread(page: Page, timeout_ms: int = 20000) -> bool:
    """True once a thread's messages and at least one body are rendered."""
    return _wait_messages(page, timeout_ms=timeout_ms)


def _wait_messages(page: Page, timeout_ms: int = 20000) -> bool:
    """Wait for a message container *and* a rendered body (they arrive apart)."""
    waited = 0
    while waited < timeout_ms:
        if selectors.all_in(page, "thread_message").count() and _any_body(page):
            return True
        page.wait_for_timeout(400)
        waited += 400
    return bool(selectors.all_in(page, "thread_message").count())


def _expand(page: Page, message) -> None:
    """Click a folded message's header so its body is rendered."""
    try:
        selectors.locator(message, "message_sender").click()
        page.wait_for_timeout(600)
    except Exception:
        pass


def _attachments(message) -> tuple[str, ...]:
    """File names on one message (Gmail's chips, never downloaded)."""
    items = selectors.all_in(message, "attachment_name")
    names: list[str] = []
    for i in range(items.count()):
        try:
            name = " ".join(items.nth(i).inner_text().split())
        except Exception:
            continue
        if name and name not in names:
            names.append(name)
    return tuple(names)


def read_messages(page: Page) -> list[Message]:
    """Messages newest first, quotes and signatures removed."""
    items = selectors.all_in(page, "thread_message")
    found: list[Message] = []
    for i in range(items.count()):
        message = items.nth(i)
        body = _body(message)
        if body is None:
            _expand(page, message)
            body = _body(message)
            if body is None:
                page.wait_for_timeout(500)
                body = _body(message)
            if body is None:
                body = ""
        found.append(
            Message(
                sender=_sender(message),
                date=_date(message),
                body=clean_body(body),
                attachments=_attachments(message),
            )
        )
    found.reverse()
    return found


def _attr(value: str) -> str:
    """One attribute value: no quotes, no newlines, no doubled spaces."""
    return " ".join(str(value or "").split()).replace('"', "'")


def render(messages: list[Message]) -> str:
    blocks = []
    for message in messages:
        attrs = f'from="{_attr(message.sender)}" date="{_attr(message.date)}"'
        if message.attachments:
            names = "; ".join(filter(None, (_attr(name) for name in message.attachments)))
            if names:
                attrs += f' attachments="{names}"'
        blocks.append(f"<email {attrs}>\n{message.body}\n</email>")
    return "\n".join(blocks)


def read(n: int, page_no: int = 1) -> str:
    """Read page ``page_no`` of thread ``n`` from the last search."""
    rows = search.last_rows()
    if not rows:
        return "ERR mail.google.com | no search results | call email_search first"
    try:
        index = int(n)
    except (TypeError, ValueError):
        index = 0
    if index < 1 or index > len(rows):
        return f"ERR mail.google.com | no row {n} | results are 1 to {len(rows)}"

    row = rows[index - 1]
    problem = search.row_problem(row, index)
    if problem:
        return f"ERR mail.google.com | {problem} | run email_search again"

    try:
        page = get_session().start().page
    except Exception:
        return BROWSER_LINE
    if not signed_in(page):
        return LOGIN_LINE
    if not open_thread(page, row.thread_id):
        return "ERR mail.google.com | thread did not open | try email_search again"

    messages = read_messages(page)
    count = len(messages)
    try:
        page_no = max(1, int(page_no))
    except (TypeError, ValueError):
        page_no = 1

    plural = "message" if count == 1 else "messages"
    head = f"OK mail.google.com | thread {index}: {row.subject[:60]} | {count} {plural}"
    hint = f"[more: call email_read(n={index}, page={page_no + 1})]"
    room = max(200, config.MAX_CHARS - len(head) - len(hint) - 4)
    chunk, total = paginate(render(messages), page_no, max_chars=room)
    chunk = chunk.rstrip()  # a trailing blank line would eat the cap

    if not chunk:
        return f"{head} | page {page_no}/{total}\n(no text on that page)"
    tail = hint if page_no < total else "[end of thread]"
    return f"{head} | page {page_no}/{total}\n{chunk}\n{tail}"
