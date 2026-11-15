"""E8: a reply draft is saved inside the chosen thread."""

from __future__ import annotations

import pytest

from harness.email import draft, read, search


@pytest.fixture()
def wired(session, site, monkeypatch):
    monkeypatch.setattr(draft, "get_session", lambda: session)
    monkeypatch.setattr(draft, "signed_in", lambda page: True)
    monkeypatch.setattr(read, "THREAD_URL", site.url("gmail_thread.html") + "#{thread_id}")
    monkeypatch.setattr(
        search,
        "last_rows",
        lambda: [
            search.Row(
                n=1,
                sender="Alex Chen",
                subject="Re: Lab safety training",
                date="Nov 14, 9:12 AM",
                snippet="Thanks.",
                thread_id="t1",
            )
        ],
    )
    return draft


def test_reply_draft_is_saved_in_the_thread(wired, session):
    out = wired.reply(1, "Sounds good, see you then.")
    assert out == "OK draft saved"

    body = session.page.locator("div[role='textbox'][aria-label='Message Body']")
    assert "Sounds good, see you then." in body.evaluate("e => e.textContent")
    assert not body.is_visible()


def test_reply_without_a_search(wired, monkeypatch):
    monkeypatch.setattr(search, "last_rows", lambda: [])
    out = wired.reply(1, "hi")
    assert out.startswith("ERR")
    assert "email_search" in out


def test_reply_row_out_of_range(wired):
    out = wired.reply(4, "hi")
    assert out.startswith("ERR")
    assert "1 to 1" in out


def test_reply_to_a_draft_row_is_refused(wired, monkeypatch):
    monkeypatch.setattr(
        search, "last_rows", lambda: [search.Row(1, "Draft", "(no subject)", "Nov 14", "x", "t9")]
    )
    out = wired.reply(1, "hi")
    assert out.startswith("ERR")
    assert "draft" in out
