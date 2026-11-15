"""E7: drafts are only written into a fresh, exactly-addressed compose."""

from __future__ import annotations

import pytest

from harness.email import draft


def _wired(session, site, monkeypatch):
    monkeypatch.setattr(draft, "get_session", lambda: session)
    monkeypatch.setattr(draft, "signed_in", lambda page: True)
    return draft


@pytest.fixture()
def wired(session, site, monkeypatch):
    page = _wired(session, site, monkeypatch)
    session.page.goto(site.url("gmail_list.html"))
    return page


@pytest.fixture()
def restore(session, site, monkeypatch):
    page = _wired(session, site, monkeypatch)
    session.page.goto(site.url("gmail_compose_restore.html"))
    return page


@pytest.fixture()
def bcc(session, site, monkeypatch):
    page = _wired(session, site, monkeypatch)
    session.page.goto(site.url("gmail_compose_bcc.html"))
    return page


def test_new_draft_is_filled_and_saved(wired, session):
    out = wired.new("friend@example.edu", "Hello there", "A short note.")
    assert out == "OK draft saved"

    page = session.page
    assert page.locator("span[email='friend@example.edu']").count() == 1
    assert page.input_value("input[name='subjectbox']") == "Hello there"
    body = page.locator("div[role='textbox'][aria-label='Message Body']")
    assert body.evaluate("e => e.textContent") == "A short note."
    # The compose window was closed after saving.
    assert not body.is_visible()


def test_restored_draft_is_refused(restore, session):
    out = restore.new("friend@example.edu", "New subject", "New body")
    assert out.startswith("ERR")
    assert "restored" in out

    page = session.page
    # The user's draft is untouched.
    assert page.input_value("input[name='subjectbox']") == "Old draft from last night"
    body = page.locator("#compose-body").evaluate("e => e.textContent")
    assert "Half-written note from last night" in body
    assert "New body" not in body
    assert page.locator("span[email='friend@example.edu']").count() == 0


def test_extra_bcc_aborts_before_writing(bcc, session):
    out = bcc.new("friend@example.edu", "Hello there", "A short note.")
    assert out.startswith("ERR")
    assert "recipients" in out

    page = session.page
    assert page.input_value("input[name='subjectbox']") == ""
    assert page.locator("#compose-body").evaluate("e => e.textContent").strip() == ""


def test_missing_recipient_is_refused(wired):
    out = wired.new("  ", "Hello", "Body")
    assert out.startswith("ERR")
    assert "recipient" in out


def test_signed_out_returns_login(wired, monkeypatch):
    monkeypatch.setattr(draft, "signed_in", lambda page: False)
    assert wired.new("friend@example.edu", "Hi", "Body").startswith("LOGIN")


def test_blank_problem_accepts_a_fresh_message():
    state = {"region": "New Message", "chips": [], "to": "", "cc": "", "bcc": "", "subject": "", "body": ""}
    assert draft.blank_problem(state) == ""


def test_blank_problem_flags_a_restored_draft():
    state = {
        "region": "New Message",
        "chips": ["old@example.edu"],
        "to": "",
        "cc": "",
        "bcc": "",
        "subject": "Old",
        "body": "",
    }
    problem = draft.blank_problem(state)
    assert "recipient" in problem and "Subject" in problem


def test_blank_problem_allows_a_signature_only():
    state = {
        "region": "New Message",
        "chips": [],
        "to": "",
        "cc": "",
        "bcc": "",
        "subject": "",
        "body": "-- \nAntranig\nCornell Engineering",
    }
    assert draft.blank_problem(state) == ""


def test_blank_problem_flags_a_reply_compose():
    state = {"region": "Reply", "chips": [], "to": "", "cc": "", "bcc": "", "subject": "", "body": ""}
    assert "new message" in draft.blank_problem(state)


def test_recipient_problem_needs_exactly_one_address():
    assert draft.recipient_problem({"chips": ["Friend@Example.edu"], "to": "", "cc": "", "bcc": ""}, "friend@example.edu") == ""
    extra = {"chips": ["friend@example.edu", "leak@example.com"], "to": "", "cc": "", "bcc": ""}
    assert "expected only" in draft.recipient_problem(extra, "friend@example.edu")
    with_bcc = {"chips": ["friend@example.edu"], "to": "", "cc": "", "bcc": "leak@example.com"}
    assert "BCC" in draft.recipient_problem(with_bcc, "friend@example.edu")
    typed_only = {"chips": [], "to": "friend@example.edu", "cc": None, "bcc": None}
    assert draft.recipient_problem(typed_only, "friend@example.edu") == ""
