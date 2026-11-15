"""collect_rows pages through a result list (fake fixture) and de-duplicates by thread."""
from harness.email import read as read_mod
from harness.email import search as search_mod


def test_collect_rows_reads_all_rows_not_ten(session, site, monkeypatch):
    monkeypatch.setattr(search_mod.query, "search_url", lambda q: site.url("gmail_list.html"))
    rows = search_mod.collect_rows(session.start().page, days=14, limit=200)
    assert [r.thread_id for r in rows] == ["t1", "t2", "t3", "t4", "t5"]
    assert len(search_mod.collect_rows(session.start().page, days=14, limit=2)) == 2


def test_message_ids_follow_read_order(session, site):
    page = session.start().page
    page.goto(site.url("gmail_thread.html"))
    n = len(read_mod.read_messages(page))
    assert len(read_mod.message_ids(page)) == n
