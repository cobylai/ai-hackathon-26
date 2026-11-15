"""B5: controls are numbered, typeable and clickable."""

import pytest

from harness.browser.elements import click, list_elements, type_into


def number_of(listing: str, needle: str) -> int:
    for line in listing.splitlines():
        if needle in line:
            return int(line.split(".")[0])
    raise AssertionError(f"{needle!r} not in listing:\n{listing}")


@pytest.fixture()
def form(session, site):
    session.page.goto(site.url("form.html"))
    return session.page


def test_lists_fields_and_links(form):
    listing = list_elements(form)
    assert 'input "Search terms"' in listing
    assert "select " in listing
    assert 'textarea "Notes"' in listing
    assert 'button "Submit"' in listing
    assert 'link "Help page"' in listing
    assert "Hidden button" not in listing
    assert "Hidden link" not in listing
    assert len(listing.splitlines()) <= 40


def test_filter_and_stable_numbering(form):
    listing = list_elements(form)
    filtered = list_elements(form, "search")
    assert filtered == '1. input "Search terms"'
    assert number_of(listing, "Search terms") == number_of(filtered, "Search terms")


def test_type_click_and_see_result(form):
    listing = list_elements(form)
    type_into(form, number_of(listing, "Search terms"), "hello harness")
    click(form, number_of(listing, "Submit"))
    assert "Submitted: hello harness" in form.inner_text("#result")


def test_enter_submits(form):
    listing = list_elements(form)
    type_into(form, number_of(listing, "Search terms"), "lighthouse", enter=1)
    assert "Submitted: lighthouse" in form.inner_text("#result")
