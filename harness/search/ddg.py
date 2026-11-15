"""Parse a DuckDuckGo HTML results page (html.duckduckgo.com/html/?q=).

Used when Google shows a bot wall or returns nothing. Same ``Result`` shape as
the Google parser, so the caller cannot tell the two engines apart.
"""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

import lxml.html

from harness.search.google import SNIPPET_CHARS, Result

MAX_PER_DOMAIN = 2
AD_CLASSES = {"result--ad", "result--sponsored", "badge--ad"}
WRAPPER_HOSTS = {"duckduckgo.com", "html.duckduckgo.com", "external-content.duckduckgo.com"}


def _clean(text: str) -> str:
    return " ".join(text.split())


def _cut(text: str) -> str:
    text = _clean(text)
    if len(text) <= SNIPPET_CHARS:
        return text
    return text[: SNIPPET_CHARS - 3].rstrip(" ,.;:-") + "..."


def _classes(node) -> set[str]:
    return set((node.get("class") or "").split())


def _skipped(anchor) -> bool:
    node = anchor
    for _ in range(4):
        if node is None:
            return False
        if _classes(node) & AD_CLASSES:
            return True
        node = node.getparent()
    return False


def _unwrap(href: str) -> str:
    """DDG links look like ``//duckduckgo.com/l/?uddg=<encoded target>``."""
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.lower() in WRAPPER_HOSTS:
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target)
    return href


def _url(anchor) -> str:
    url = _unwrap(anchor.get("href") or "")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return ""
    if parsed.netloc.lower() in WRAPPER_HOSTS:
        return ""
    return url


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _container(anchor):
    node = anchor.getparent()
    for _ in range(4):
        if node is None:
            break
        if "result" in _classes(node):
            return node
        node = node.getparent()
    return anchor.getparent() if anchor.getparent() is not None else anchor


def _snippet(container, title: str) -> str:
    for node in container.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), ' result__snippet ')]"
    ):
        text = _clean(node.text_content())
        if text and text != title:
            return _cut(text)
    return ""


def parse(html: str) -> list[Result]:
    """Organic results in page order; ads and extra domains are dropped."""
    if not html:
        return []
    try:
        tree = lxml.html.fromstring(html)
    except (lxml.etree.ParserError, ValueError):
        return []

    results: list[Result] = []
    seen_urls: set[str] = set()
    per_domain: dict[str, int] = {}

    anchors = tree.xpath(
        "//a[contains(concat(' ', normalize-space(@class), ' '), ' result__a ')]"
    )
    for anchor in anchors:
        title = _clean(anchor.text_content())
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
