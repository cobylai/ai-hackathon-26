"""E2: the selector map finds every field on the fixture pages."""

from __future__ import annotations

from harness.email import selectors


def _rows(page):
    return selectors.all_in(page, "list_row")


def test_list_fixture_has_every_field(session, site):
    page = session.page
    page.goto(site.url("gmail_list.html"))
    rows = _rows(page)
    assert rows.count() == 5
    for name in ("row_sender", "row_subject", "row_snippet", "row_date"):
        found = [selectors.locator(rows.nth(i), name).count() for i in range(rows.count())]
        assert found == [1] * 5, (name, found)

    first = rows.nth(0)
    assert selectors.locator(first, "row_sender").inner_text() == "Priya Raman"
    assert selectors.locator(first, "row_subject").inner_text() == "Re: Lab safety training"
    assert "checklist" in selectors.locator(first, "row_snippet").inner_text()
    assert selectors.locator(first, "row_date").get_attribute("title").startswith("Sat, Nov 14")


def test_compose_fixture(session, site):
    page = session.page
    page.goto(site.url("gmail_list.html"))
    assert selectors.matches(page, "compose_button") == 1
    selectors.locator(page, "compose_button").click()
    for name in ("compose_to", "compose_subject", "compose_body", "compose_close"):
        assert selectors.matches(page, name) == 1, name

    selectors.locator(page, "compose_to").fill("friend@example.edu")
    selectors.locator(page, "compose_subject").fill("Hello")
    selectors.locator(page, "compose_body").fill("A short note.")
    label = selectors.wait_for(page, "draft_saved_label")
    assert label.is_visible()
    assert label.inner_text() == "Draft saved"

    selectors.locator(page, "compose_close").click()
    assert not selectors.locator(page, "compose_to").is_visible()


def test_thread_fixture(session, site):
    page = session.page
    page.goto(site.url("gmail_thread.html"))
    messages = selectors.all_in(page, "thread_message")
    assert messages.count() == 3

    senders = [
        selectors.locator(messages.nth(i), "message_sender").get_attribute("email")
        for i in range(3)
    ]
    assert senders == ["alex.chen@example.edu", "priya.raman@example.edu", "alex.chen@example.edu"]

    # The middle message is collapsed until it is clicked, like Gmail.
    assert selectors.locator(messages.nth(1), "message_body").count() == 0
    messages.nth(1).locator(".gs").click()
    assert selectors.locator(messages.nth(1), "message_body").count() == 1

    assert selectors.matches(messages.nth(2), "quoted_text") == 1
    assert selectors.matches(page, "reply_button") == 3


def test_reply_box_fixture(session, site):
    page = session.page
    page.goto(site.url("gmail_thread.html"))
    selectors.all_in(page, "reply_button").nth(2).click()
    body = selectors.locator(page, "compose_body")
    body.fill("Sounds good, see you then.")
    assert selectors.wait_for(page, "draft_saved_label").is_visible()
    selectors.locator(page, "compose_close").click()
    assert not body.is_visible()
