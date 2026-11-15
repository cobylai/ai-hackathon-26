"""The digest groups asks by thread and passes status lines through."""

from __future__ import annotations

import pytest

from harness.email import asks, digest, read, search


@pytest.fixture()
def wired(session, site, monkeypatch):
    monkeypatch.setattr(asks, "get_session", lambda: session)
    monkeypatch.setattr(asks.search, "search", lambda **kwargs: "OK 2 results | newer_than:1d")
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
            ),
            search.Row(
                n=2,
                sender="Priya Raman",
                subject="Re: Lab safety training",
                date="Nov 12, 5:02 PM",
                snippet="Notes.",
                thread_id="t2",
            ),
        ],
    )
    monkeypatch.setattr(read, "THREAD_URL", site.url("gmail_thread.html") + "#{thread_id}")
    # Both fixture rows open the same thread page, so skip the title guard.
    monkeypatch.setattr(asks, "_title_matches", lambda page, subject: True)
    return digest


def test_digest_groups_asks_by_thread(wired):
    out = wired.build(days=1, limit=2)
    lines = out.splitlines()
    assert lines[0] == "OK 2 threads, 4 asks | newer_than:1d"
    assert lines[1] == "1. Re: Lab safety training (2)"
    assert lines[2].startswith("   - ")
    assert "2. Re: Lab safety training (2)" in out
    assert out.count("Could you also bring the sign-in sheet?") == 2
    assert len(out) <= 1500


def test_digest_passes_a_login_line_through(wired, monkeypatch):
    monkeypatch.setattr(
        asks.search, "search", lambda **kwargs: "LOGIN mail.google.com | sign-in needed"
    )
    assert wired.build().startswith("LOGIN")


def test_digest_never_builds_a_draft():
    import inspect

    source = inspect.getsource(digest)
    assert "email_draft" not in source and "draft_mod" not in source
