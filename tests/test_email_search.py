"""E4: email_search returns numbered rows, remembers them, respects the cap."""

from __future__ import annotations

import pytest

from harness.email import search as search_mod


@pytest.fixture()
def wired(session, site, monkeypatch):
    """search() pointed at a fixture page and a logged-in session."""
    monkeypatch.setattr(search_mod, "get_session", lambda: session)
    monkeypatch.setattr(search_mod, "signed_in", lambda page: True)
    monkeypatch.setattr(search_mod.query, "search_url", lambda q: site.url("gmail_list.html"))
    return search_mod


def test_rows_are_numbered_and_formatted(wired):
    out = wired.search(sender="priya")
    lines = out.splitlines()
    assert lines[0] == "OK 5 results | from:priya"
    assert lines[1] == (
        "1. Priya Raman | Re: Lab safety training | Nov 14, 9:12 AM | "
        "Yes, Thursday at 2 works for me. I'll bring the checklist."
    )
    assert lines[2] == (
        "2. me | BME 3030 HW5 Oral Defense - Scheduling Correction | Nov 14, 1:07 PM | "
        "to add on, please reach out to them with your availability"
    )
    assert len(lines) == 6
    assert len(out) <= 1500


def test_row_order_is_remembered_for_the_session(wired):
    wired.search(text="anything")
    rows = wired.last_rows()
    assert [row.n for row in rows] == [1, 2, 3, 4, 5]
    assert rows[0].thread_id == "t1"
    assert rows[1].sender == "me"
    assert rows[2].date == "Nov 14, 1:05 PM"
    assert len(rows[2].snippet) == 80


def test_empty_result_is_ok_zero_results(wired, site, monkeypatch):
    monkeypatch.setattr(search_mod.query, "search_url", lambda q: site.url("gmail_empty.html"))
    assert wired.search(text="zzz") == "OK 0 results | zzz"


def test_signed_out_returns_login(wired, monkeypatch):
    monkeypatch.setattr(search_mod, "signed_in", lambda page: False)
    out = wired.search(text="anything")
    assert out.startswith("LOGIN")
    assert "harness login" in out


def test_cap_cuts_rows_and_adds_a_hint():
    rows = [
        search_mod.Row(
            n=i,
            sender="x" * 40,
            subject="y" * 80,
            date="Nov 14, 3:53 PM",
            snippet="z" * 80,
            thread_id="t",
        )
        for i in range(1, 11)
    ]
    out = search_mod.format_rows("from:someone", rows, 42)
    assert len(out) <= 1500
    assert out.endswith(search_mod.HINT)
    assert out.splitlines()[0] == "OK 42 results | from:someone"


def test_transient_no_results_is_not_believed(session, site):
    """Gmail flashes its empty note before the rows of a new query render."""
    session.page.goto(site.url("gmail_slow_results.html"))
    assert search_mod.wait_results(session.page, timeout_ms=8000) == 3


def test_a_real_empty_result_is_still_zero(session, site):
    session.page.goto(site.url("gmail_empty.html"))
    assert search_mod.wait_results(session.page, timeout_ms=8000) == 0
