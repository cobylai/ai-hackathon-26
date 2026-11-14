"""E3: plain fields become a Gmail query, and a query becomes a search URL."""

from __future__ import annotations

import pytest

from harness.email.query import INBOX_URL, build, search_url

CASES = [
    # One field at a time.
    ({"sender": "emily"}, "from:emily"),
    ({"sender": "emily@example.edu"}, "from:emily@example.edu"),
    ({"sender": "Emily Smith"}, 'from:"Emily Smith"'),
    ({"text": "homework"}, "homework"),
    ({"text": "lab safety"}, '"lab safety"'),
    ({"text": "  lab   safety  "}, '"lab safety"'),
    ({"days": 7}, "newer_than:7d"),
    ({"days": "14"}, "newer_than:14d"),
    ({"days": 0}, ""),
    ({"days": -3}, ""),
    ({"unread": True}, "is:unread"),
    ({"unread": False}, ""),
    ({"has_attachment": True}, "has:attachment"),
    # Nothing at all.
    ({}, ""),
    # Combined, in a stable order.
    (
        {"sender": "emily", "text": "homework", "days": 14, "unread": True},
        "from:emily homework newer_than:14d is:unread",
    ),
    (
        {"sender": "Emily Smith", "text": "lab safety", "days": 3},
        'from:"Emily Smith" "lab safety" newer_than:3d',
    ),
    (
        {"text": "read this", "has_attachment": True},
        '"read this" has:attachment',
    ),
    # Stray quotes cannot break the query.
    ({"text": 'say "hi" now'}, '"say hi now"'),
    ({"sender": '"emily"', "text": ""}, "from:emily"),
]


@pytest.mark.parametrize("fields, expected", CASES)
def test_build(fields, expected):
    assert build(**fields) == expected


def test_search_url_encodes_query():
    assert search_url("from:emily") == "https://mail.google.com/mail/u/0/#search/from%3Aemily"
    assert (
        search_url('from:"Emily Smith" "lab safety"')
        == "https://mail.google.com/mail/u/0/#search/from%3A%22Emily%20Smith%22%20%22lab%20safety%22"
    )
    assert search_url("newer_than:7d is:unread") == (
        "https://mail.google.com/mail/u/0/#search/newer_than%3A7d%20is%3Aunread"
    )


def test_search_url_of_blank_query_is_the_inbox():
    assert search_url("") == INBOX_URL
    assert search_url("   ") == INBOX_URL


def test_build_then_url():
    query = build(sender="emily", text="lab safety", days=7)
    assert query == 'from:emily "lab safety" newer_than:7d'
    assert search_url(query) == (
        "https://mail.google.com/mail/u/0/#search/"
        "from%3Aemily%20%22lab%20safety%22%20newer_than%3A7d"
    )
