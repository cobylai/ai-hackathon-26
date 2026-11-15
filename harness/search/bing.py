"""Parse a Bing results page (www.bing.com/search?q=).

Last fallback, tried only after Google and DuckDuckGo both fail (added at
integration: on the hackathon network both showed bot checks while Bing did
not). Same ``Result`` shape as the other parsers.
"""

from __future__ import annotations

import base64
from urllib.parse import parse_qs, urlparse

import lxml.html

from harness.search.ddg import MAX_PER_DOMAIN, _clean, _cut, _domain
from harness.search.google import Result


def _unwrap(href: str) -> str:
    """Bing may wrap links as ``bing.com/ck/a?...&u=a1<base64url target>``."""
    parsed = urlparse(href or "")
    if parsed.netloc.lower().endswith("bing.com") and parsed.path.startswith("/ck/"):
        u = parse_qs(parsed.query).get("u", [""])[0]
        if not u.startswith("a1"):
            return ""
        b = u[2:]
        try:
            return base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
        except Exception:
            return ""
    return href or ""


def parse(html: str) -> list[Result]:
    """Organic results (``li.b_algo``) in page order, at most two per domain."""
    if not html:
        return []
    try:
        tree = lxml.html.fromstring(html)
    except (lxml.etree.ParserError, ValueError):
        return []
    results: list[Result] = []
    seen: set[str] = set()
    per_domain: dict[str, int] = {}
    for li in tree.xpath("//li[contains(concat(' ', normalize-space(@class), ' '), ' b_algo ')]"):
        anchors = li.xpath(".//h2//a[@href]")
        if not anchors:
            continue
        title = _clean(anchors[0].text_content())
        url = _unwrap(anchors[0].get("href"))
        if not title or urlparse(url).scheme not in ("http", "https") or url in seen:
            continue
        domain = _domain(url)
        if not domain or per_domain.get(domain, 0) >= MAX_PER_DOMAIN:
            continue
        paras = li.xpath(".//*[contains(@class, 'b_caption')]//p") or li.xpath(".//p")
        snippet = _cut(paras[0].text_content()) if paras else ""
        seen.add(url)
        per_domain[domain] = per_domain.get(domain, 0) + 1
        results.append(Result(title, url, domain, snippet))
    return results
