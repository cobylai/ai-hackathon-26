"""E5: email_read returns newest first, quoted replies and signatures gone."""

from __future__ import annotations

import pytest

from harness.email import read as read_mod
from harness.email import search


@pytest.fixture()
def wired(session, site, monkeypatch):
    monkeypatch.setattr(read_mod, "get_session", lambda: session)
    monkeypatch.setattr(read_mod, "signed_in", lambda page: True)
    monkeypatch.setattr(read_mod, "THREAD_URL", site.url("gmail_thread.html") + "#{thread_id}")
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
    return read_mod


def test_fixture_thread_newest_first_without_quotes(wired):
    out = wired.read(1)
    head = out.splitlines()[0]
    assert head.startswith("OK mail.google.com | thread 1: Re: Lab safety training")
    assert "3 messages" in head

    # Newest message first, oldest last.
    newest = out.index("Thanks. Could you also bring the sign-in sheet?")
    middle = out.index("Sure, I'll take a look tonight and send notes.")
    oldest = out.index("Can you review the lab safety checklist before Thursday?")
    assert newest < middle < oldest

    # The folded middle message was expanded, its quote and signature dropped.
    assert "On Thu, Nov 12, 2026" not in out
    assert "wrote:" not in out
    assert "Undergraduate TA" not in out

    # Every message is wrapped for the model.
    assert '<email from="Alex Chen <alex.chen@example.edu>" date="Sat, Nov 14, 2026, 9:12 AM"' in out
    assert out.count("<email from=") == 3
    assert out.count("</email>") == 3


def test_pages_stay_within_the_cap(wired, monkeypatch):
    monkeypatch.setattr(read_mod.config, "MAX_CHARS", 450)
    seen = []
    for page in range(1, 20):
        out = wired.read(1, page)
        assert len(out) <= 450, len(out)
        seen.append(out)
        if "[end of thread]" in out:
            break
    assert len(seen) > 1
    assert "Can you review the lab safety checklist" in "".join(seen)


def test_read_without_a_search_explains_itself(wired, monkeypatch):
    monkeypatch.setattr(search, "last_rows", lambda: [])
    out = wired.read(1)
    assert out.startswith("ERR")
    assert "email_search" in out


def test_read_row_out_of_range(wired):
    out = wired.read(9)
    assert out.startswith("ERR")
    assert "1 to 1" in out


def test_read_signed_out_returns_login(wired, monkeypatch):
    monkeypatch.setattr(read_mod, "signed_in", lambda page: False)
    assert wired.read(1).startswith("LOGIN")


def test_attachments_are_named_in_the_tag(wired):
    out = wired.read(1)
    assert 'attachments="Lab safety checklist.pdf"' in out
    # Only the message that has one carries the attribute.
    assert out.count("attachments=") == 1
