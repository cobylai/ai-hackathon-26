"""E6: the asks rule, and the fixture thread's two known asks."""

from __future__ import annotations

import pytest

from harness.email import asks, read, search

SAMPLES = [
    ("Can you send the slides?", True),
    ("I'll be out on Thursday.", True),
    ("The deadline is March 3.", True),
    ("Let's meet at 9:30 am.", True),
    ("Please review the draft.", True),
    ("Due Friday.", True),
    ("Could you check the budget by tomorrow?", True),
    ("We shipped the order yesterday.", False),
    ("The lab is closed for the holiday.", False),
    ("Bring your laptop.", False),
]


@pytest.mark.parametrize("sentence, expected", SAMPLES)
def test_sentence_rule(sentence, expected):
    assert bool(asks.extract(sentence)) is expected


def test_extract_keeps_order_strips_bullets_and_dedupes():
    text = "Intro line.\n- Please send the form.\nPlease send the form.\nSee you Monday."
    assert asks.extract(text) == ["Please send the form.", "See you Monday."]


def test_extract_splits_sentences_inside_one_line():
    got = asks.extract("Thanks. Could you sign this? The room opens early.")
    assert got == ["Could you sign this?"]


@pytest.fixture()
def wired(session, site, monkeypatch):
    monkeypatch.setattr(asks, "get_session", lambda: session)
    monkeypatch.setattr(asks.search, "search", lambda **kwargs: "OK 1 results | from:alex")
    monkeypatch.setattr(
        asks.search,
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
    monkeypatch.setattr(read, "THREAD_URL", site.url("gmail_thread.html") + "#{thread_id}")
    return asks


def test_fixture_thread_yields_its_two_asks(wired):
    out = wired.email_asks(sender="alex")
    lines = out.splitlines()
    assert lines[0] == "OK 2 asks | from:alex"
    assert lines[1] == "1. Could you also bring the sign-in sheet?"
    assert lines[2] == "1. Can you review the lab safety checklist before Thursday?"
    assert "The room opens early" not in out
    assert "Thanks." not in out


def test_no_results_is_ok_zero_asks(wired, monkeypatch):
    monkeypatch.setattr(asks.search, "search", lambda **kwargs: "OK 0 results | from:alex")
    monkeypatch.setattr(asks.search, "last_rows", lambda: [])
    assert wired.email_asks(sender="alex") == "OK 0 asks | from:alex"


def test_login_from_search_is_passed_through(wired, monkeypatch):
    monkeypatch.setattr(
        asks.search, "search", lambda **kwargs: "LOGIN mail.google.com | sign-in needed"
    )
    assert wired.email_asks(sender="alex").startswith("LOGIN")
