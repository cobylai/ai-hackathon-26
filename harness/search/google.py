"""Parse a Google results page into a short list of organic results.

Works on both the older ``div.g`` markup and the current markup, where every
organic result is an ``<a>`` that wraps an ``<h3>``. Ads, "People also ask"
cards and more than two results from one domain are dropped here, so callers
never have to think about them.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

import lxml.html

SNIPPET_CHARS = 120
MAX_PER_DOMAIN = 2

# Classes that mark an ad block on the old and new results pages.
AD_CLASSES = {"uEierd", "ads-ad", "commercial-unit-desktop-top", "commercial-unit-desktop-rhs"}
# "People also ask" and related-question cards are not organic results.
SKIP_CLASSES = {"related-question-pair", "related-question-pair-li"}
# Containers that hold a result; used to find the snippet.
RESULT_CLASSES = {"g", "MjjYud", "Gx5Zad", "tF2Cxc"}
SNIPPET_CLASSES = ("VwiC3b", "aCOpRe", "st")
MAX_ANCESTORS = 12

# Hosts that only wrap a result or point back into Google.
GOOGLE_HOSTS = {"google.com", "www.google.com", "googleusercontent.com",
                "webcache.googleusercontent.com"}


@dataclass(frozen=True)
class Result:
    title: str
    url: str
    domain: str
    snippet: str = ""


def _clean(text: str) -> str:
    return " ".join(text.split())


def _classes(node) -> set[str]:
    return set((node.get("class") or "").split())


def _ancestors(node):
    parent = node.getparent()
    steps = 0
    while parent is not None and steps < MAX_ANCESTORS:
        yield parent
        parent = parent.getparent()
        steps += 1


def _has_class(node, names: set[str]) -> bool:
    return bool(_classes(node) & names)


def _skipped(anchor) -> bool:
    """True for ads and question cards, checked on the anchor itself and above."""
    for node in (anchor, *_ancestors(anchor)):
        classes = _classes(node)
        if classes & AD_CLASSES or classes & SKIP_CLASSES:
            return True
        if node.get("data-text-ad") == "1":
            return True
        if node.get("id") in ("tads", "tadsb", "bottomads", "rhs"):
            return True
    return False


def _container(anchor):
    """The nearest block that holds this result's title and snippet."""
    for node in _ancestors(anchor):
        if _classes(node) & RESULT_CLASSES or node.get("data-hveid"):
            return node
    return anchor.getparent() if anchor.getparent() is not None else anchor


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _unwrap(url: str) -> str:
    """Turn Google's ``/url?q=...`` redirects into the real target."""
    if url.startswith("/url?") or url.startswith("https://www.google.com/url?"):
        query = urlparse(url).query
        target = parse_qs(query).get("q", [""])[0]
        if target:
            url = unquote(target)
    return url


def _url(anchor) -> str:
    href = (anchor.get("href") or "").strip()
    if not href or href.startswith(("#", "javascript:")):
        return ""
    url = _unwrap(href)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return ""
    if parsed.netloc.lower() in GOOGLE_HOSTS:
        return ""
    return url


def _snippet(container, title: str) -> str:
    for name in SNIPPET_CLASSES:
        found = container.xpath(
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' %s ')]" % name
        )
        for node in found:
            text = _clean(node.text_content())
            if text and text != title:
                return _cut(text)
    return ""


def _cut(text: str) -> str:
    text = _clean(text)
    if len(text) <= SNIPPET_CHARS:
        return text
    return text[: SNIPPET_CHARS - 3].rstrip(" ,.;:-") + "..."


def parse(html: str) -> list[Result]:
    """Organic results in page order, each with a title, URL, domain, snippet."""
    if not html:
        return []
    try:
        tree = lxml.html.fromstring(html)
    except (lxml.etree.ParserError, ValueError):
        return []

    results: list[Result] = []
    seen_urls: set[str] = set()
    per_domain: dict[str, int] = {}

    for anchor in tree.xpath("//a[h3]"):
        heading = anchor.xpath(".//h3")[0]
        title = _clean(heading.text_content())
        if not title or _skipped(anchor):
            continue
        url = _url(anchor)
        if not url or url in seen_urls:
            continue
        domain = _domain(url)
        if not domain or per_domain.get(domain, 0) >= MAX_PER_DOMAIN:
            continue
        seen_urls.add(url)
        per_domain[domain] = per_domain.get(domain, 0) + 1
        results.append(Result(title, url, domain, _snippet(_container(anchor), title)))
    return results
