"""E2-E8 together: search -> read -> asks -> draft -> reply on the fixtures.

Each tool is tested on its own elsewhere; this one proves they compose: the row
order `email_search` remembers is what `email_read` and `email_reply_draft`
reuse, and the page moves between list, thread and compose the way it does live.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def wired(session, site, monkeypatch):
    from harness.email import asks, draft, read, search

    for module in (search, read, asks, draft):
        monkeypatch.setattr(module, "get_session", lambda: session)
    for module in (search, read, draft):
        monkeypatch.setattr(module, "signed_in", lambda page: True)
    monkeypatch.setattr(search.query, "search_url", lambda query: site.url("gmail_list.html"))
    monkeypatch.setattr(read, "THREAD_URL", site.url("gmail_thread.html") + "#{thread_id}")
    # Every fixture row points at the same thread page, so skip the title guard.
    monkeypatch.setattr(asks, "_title_matches", lambda page, subject: True)
    return session


def test_search_read_asks_draft_reply(wired, site):
    from harness.email import asks, draft, read, search

    listed = search.search(sender="priya")
    assert listed.startswith("OK 5 results | from:priya")
    assert [row.n for row in search.last_rows()] == [1, 2, 3, 4, 5]

    thread = read.read(1)
    assert thread.startswith("OK mail.google.com | thread 1")
    assert "Can you review the lab safety checklist before Thursday?" in thread
    assert "On Thu, Nov 12, 2026" not in thread  # quoted reply removed

    found = asks.email_asks(sender="priya")
    assert found == (
        "OK 2 asks | from:priya\n"
        "1. Could you also bring the sign-in sheet?\n"
        "1. Can you review the lab safety checklist before Thursday?"
    )

    # Back to a Gmail screen, as a real draft call would be after a search.
    assert search.search(sender="priya").startswith("OK 5 results")
    assert draft.new("friend@example.edu", "[harness test] flow", "One line.") == "OK draft saved"
    chip = wired.page.locator("#compose-to-area span[email]").first
    assert chip.get_attribute("email") == "friend@example.edu"

    assert draft.reply(1, "[harness test] reply flow").startswith("OK draft saved")
