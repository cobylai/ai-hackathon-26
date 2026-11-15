"""The overview's output rules, enforced for every email tool at once.

Rule 1: at most 1500 characters. Rule 2: the first word is OK/BLOCKED/LOGIN/ERR.
Rule 3: lists are numbered, so the model answers with a number and never with a
selector.
"""

from __future__ import annotations

import re

import pytest

STATUS_WORDS = {"OK", "BLOCKED", "LOGIN", "ERR"}
NUMBERED = re.compile(r"^\d+\. ")


@pytest.fixture()
def wired(session, site, monkeypatch):
    from harness.email import asks, draft, read, search

    for module in (search, read, asks, draft):
        monkeypatch.setattr(module, "get_session", lambda: session)
    for module in (search, read, draft):
        monkeypatch.setattr(module, "signed_in", lambda page: True)
    monkeypatch.setattr(search.query, "search_url", lambda query: site.url("gmail_list.html"))
    monkeypatch.setattr(read, "THREAD_URL", site.url("gmail_thread.html") + "#{thread_id}")
    monkeypatch.setattr(asks, "_title_matches", lambda page, subject: True)
    return session


def test_every_email_tool_honours_the_output_contract(wired):
    from harness.email import asks, draft, read, search

    outputs: dict[str, str] = {}

    outputs["email_search"] = search.search(sender="priya")
    outputs["email_read"] = read.read(1)
    outputs["email_asks"] = asks.email_asks(sender="priya")
    # Back to a mail list, the way a real draft call finds the page.
    assert search.search(sender="priya").startswith("OK")
    outputs["email_draft"] = draft.new("friend@example.edu", "[harness test] contract", "One line.")
    outputs["email_reply_draft"] = draft.reply(1, "[harness test] contract reply")

    for name, out in outputs.items():
        assert isinstance(out, str) and out, name
        assert len(out) <= 1500, (name, len(out))
        assert out.split(" ", 1)[0] in STATUS_WORDS, (name, out[:60])
        assert out.startswith("OK"), (name, out[:60])

    rows = outputs["email_search"].splitlines()[1:]
    assert rows and all(NUMBERED.match(line) for line in rows), outputs["email_search"][:200]

    asks_lines = outputs["email_asks"].splitlines()[1:]
    assert asks_lines and all(NUMBERED.match(line) for line in asks_lines)

    read_out = outputs["email_read"]
    assert read_out.count("<email ") == read_out.count("</email>") == 3
