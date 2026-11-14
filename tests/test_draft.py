"""E7: a new draft is filled, saved and closed on the fixture page."""

from __future__ import annotations

import pytest

from harness.email import draft


@pytest.fixture()
def wired(session, site, monkeypatch):
    monkeypatch.setattr(draft, "get_session", lambda: session)
    monkeypatch.setattr(draft, "signed_in", lambda page: True)
    session.page.goto(site.url("gmail_list.html"))
    return draft


def test_new_draft_is_filled_and_saved(wired, session):
    out = wired.new("friend@example.edu", "Hello there", "A short note.")
    assert out == "OK draft saved"

    page = session.page
    assert page.input_value("input[aria-label='To recipients']") == "friend@example.edu"
    assert page.input_value("input[name='subjectbox']") == "Hello there"
    body = page.locator("div[role='textbox'][aria-label='Message Body']")
    assert body.evaluate("e => e.textContent") == "A short note."
    # The compose window was closed after saving.
    assert not body.is_visible()


def test_missing_recipient_is_refused(wired):
    out = wired.new("  ", "Hello", "Body")
    assert out.startswith("ERR")
    assert "recipient" in out


def test_signed_out_returns_login(wired, monkeypatch):
    monkeypatch.setattr(draft, "signed_in", lambda page: False)
    assert wired.new("friend@example.edu", "Hi", "Body").startswith("LOGIN")
