"""Read saved Canvas pages (local HTML files) into assignment rows. Offline, no browser.

    from canvas.read import read_assignment, read_assignment_list, read_dashboard
    read_assignment(path)       -> {"course", "title", "due_date", "due_time", "url", "description"}
    read_assignment_list(path)  -> [{"title", "url", "due_date", "due_time"}]
    read_dashboard(path)        -> [{"course", "title", "url", "due_date", "due_time"}]

The class names and data-testids are the ones a real Canvas page uses (saved
from the student view, Nov 2026). Due times come from each <time datetime>
(UTC), shown in $FLUX_TZ (default America/New_York); on the dashboard they come
from the planner link's label, which is already local. Links are resolved
against the page's own location, so a saved page gives file:// links.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import lxml.html

TZ = ZoneInfo(os.environ.get("FLUX_TZ") or os.environ.get("MUSE_TZ", "America/New_York"))


def _cls(name: str) -> str:
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {name} ')"


def _text(el) -> str:
    return re.sub(r"\s+", " ", el.text_content()).strip() if el is not None else ""


def _load(path: Path):
    path = Path(path).resolve()
    tree = lxml.html.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    return tree, path.as_uri()


def _due(el) -> tuple[str | None, str | None]:
    """(YYYY-MM-DD, HH:MM) from the first <time datetime> under el, in local time."""
    t = el.xpath(".//time[@datetime]")
    if not t:
        return None, None
    d = datetime.fromisoformat(t[0].get("datetime").replace("Z", "+00:00")).astimezone(TZ)
    return d.date().isoformat(), f"{d:%H:%M}"


def read_assignment_list(path) -> list[dict]:
    """One course's Assignments page: every row with a title link."""
    tree, base = _load(path)
    out = []
    for row in tree.xpath(f"//div[{_cls('ig-row')}]"):
        a = row.xpath(f".//a[{_cls('ig-title')}]")
        if not a:
            continue
        due = row.xpath(f".//div[{_cls('assignment-date-due')}]")
        d, t = _due(due[0]) if due else (None, None)
        out.append({"title": _text(a[0]), "url": urljoin(base, a[0].get("href")),
                    "due_date": d, "due_time": t})
    return out


def read_assignment(path) -> dict:
    """One assignment page (the student view): course from the breadcrumbs."""
    tree, base = _load(path)
    crumbs = tree.xpath("//*[@id='breadcrumbs']//li")
    course = _text(crumbs[0]) if crumbs else ""
    title = tree.xpath("//*[@data-testid='assignment-student-header']//*[@data-testid='title']")
    head = tree.xpath("//*[@data-testid='assignment-sub-header']")
    d, t = _due(head[0]) if head else (None, None)
    desc = tree.xpath("//*[@data-testid='assignments-2-assignment-description']")
    return {"course": course, "title": _text(title[0]) if title else "", "due_date": d,
            "due_time": t, "url": base,
            "description": "\n".join(_text(p) for p in desc[0].xpath(".//p")) if desc else ""}


_PLANNER_DUE = re.compile(r", due \w+day, (\w+ \d{1,2}, \d{4}) (\d{1,2}:\d{2} [AP]M)")


def _planner_due(label: str) -> tuple[str | None, str | None]:
    """The planner link's screen-reader label: 'Assignment X, due Monday, November 16, 2026 11:59 PM.'"""
    m = _PLANNER_DUE.search(label)
    if not m:
        return None, None
    d = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%B %d, %Y %I:%M %p")
    return d.date().isoformat(), f"{d:%H:%M}"


def read_dashboard(path) -> list[dict]:
    """Dashboard planner (list view): one row per item that links to an assignment."""
    tree, base = _load(path)
    out = []
    for g in tree.xpath(f"//div[{_cls('planner-grouping')}]"):
        course = _text((g.xpath(f".//span[{_cls('Grouping-styles__title')}]") or [None])[0])
        for it in g.xpath(f".//div[{_cls('planner-item')}]"):
            a = [x for x in it.xpath(".//a[@href]") if "/assignments/" in x.get("href")
                 or x.get("href").endswith(".html")]
            if not a:
                continue
            spans = a[0].xpath("./span")
            d, t = _planner_due(_text(spans[0]) if spans else "")
            out.append({"course": course, "title": _text(spans[-1] if spans else a[0]),
                        "url": urljoin(base, a[0].get("href")), "due_date": d, "due_time": t})
    return out


def due_phrase(due_date: str | None, due_time: str | None) -> str | None:
    """'Due Wed Nov 18 at 11:59pm', the phrase filed with the deadline."""
    if not due_date:
        return None
    d = datetime.fromisoformat(f"{due_date}T{due_time or '23:59'}")
    t = f"{d:%I:%M%p}".lstrip("0").lower() if due_time else ""
    return f"Due {d:%a %b} {d.day}" + (f" at {t}" if t else "")


def course_folders(root) -> list[Path]:
    """Course folders under a generated (or saved) Canvas folder: each has assignments.html."""
    return sorted(p.parent for p in Path(root).glob("*/assignments.html"))
