"""Fake Canvas pages from three real saved Canvas pages (mock Canvas, piece 2).

    uv run python scripts/make_test_canvas.py [--templates data/canvas-templates]
                                              [--out data/test-canvas] [--today YYYY-MM-DD]

The templates come from scripts/save_canvas_pages.py (gitignored, under data/):
dashboard.html, assignments.html (one course's list) and assignment.html.
Each output page keeps Canvas's real markup (the classes and data-testids
canvas/read.py looks for) with every course, title, date, link and
description replaced by made-up sample coursework (fixed list below, fixed
seed). Scripts, styles, frames and images are dropped, so pages open offline.

Output:
  dashboard.html                 planner list, today-3 .. today+14
  <course>/assignments.html      one per course
  <course>/<id>.html             one per assignment
  truth.json                     course, title, due date/time and link of each

The real names, courses, assignment titles, ids and host found in the
templates are collected first and scrubbed; the script stops if any remain.
"""
from __future__ import annotations

import argparse
import copy
import html
import json
import random
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import lxml.html

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TZ = ZoneInfo("America/New_York")
TODAY = date(2026, 11, 14)
SEED = 13

# Made-up sample coursework. Course numbers picked to look plausible, not to match anything.
COURSES = [
    ("HIST 2147", "Maps and Empires", "hist2147", [
        ("Map Analysis 3: Trade Winds", "Annotate the two harbor maps in the reader and write 300 words on what each mapmaker left out."),
        ("Reading Response: The Spice Routes", "Post a 250-word response to chapters 6 and 7 and reply to one classmate."),
        ("Essay 2 Draft", "Upload a full draft of essay 2 (1,200 words) for peer review."),
        ("Primary Source Quiz", "Short quiz on the ship logs from week 10. Open notes, one attempt."),
        ("Essay 2 Final", "Submit the revised essay 2 as a PDF with your peer review notes attached."),
        ("Archive Visit Reflection", "Write one page on the archive visit: one object, one question it raised."),
    ]),
    ("CHEM 1583", "Kitchen Chemistry", "chem1583", [
        ("Lab 7: Emulsions", "Submit the lab 7 data sheet and the two graphs from the mayonnaise trials."),
        ("Problem Set 8", "Problems 1-12 on acids and bases. Show your work for 9-12."),
        ("Lab 8 Pre-lab Quiz", "Ten questions on the bread-rising lab. Finish before your lab section."),
        ("Lab 8: Yeast and Gas", "Submit the lab 8 report: method, CO2 volume table and a short discussion."),
        ("Problem Set 9", "Problems 1-10 on reaction rates and temperature."),
        ("Recipe Chemistry Poster", "Upload your poster PDF explaining the chemistry of one family recipe."),
    ]),
    ("MATH 2938", "Linear Systems Lab", "math2938", [
        ("Homework 9", "Sections 5.1-5.3: exercises 4, 7, 12, 18 and 21."),
        ("Matrix Lab 4", "Run the Python notebook on Markov chains and submit your answers to parts a-e."),
        ("Quiz 5: Eigenvalues", "Timed quiz, 30 minutes, on eigenvalues and diagonalisation."),
        ("Homework 10", "Sections 5.4-6.1: exercises 3, 9, 14 and 20."),
        ("Project Proposal", "One page: the system you will model and the data you will use."),
        ("Matrix Lab 5", "Least squares fit on the bike-share data set; submit the notebook."),
    ]),
    ("INFO 3361", "Data Stories", "info3361", [
        ("Chart Critique 4", "Pick one chart from this week's news and write 300 words on what it hides."),
        ("Mini Project 2 Check-in", "Post a screenshot of your current chart and one question for your mentor."),
        ("Reading Quiz: Color and Scale", "Five questions on the color and scale readings."),
        ("Mini Project 2", "Submit your notebook and a 500-word story built around three charts."),
        ("Peer Review: Mini Project 2", "Review two classmates' projects using the rubric."),
        ("Final Project Pitch", "Upload a three-slide pitch for your final project."),
    ]),
]
# Due day offsets from today (24 slots, shuffled with the seed) and due times.
OFFSETS = [-3, -2, -1, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 8, 9, 10, 11, 12, 13, 14]
TIMES = [time(23, 59), time(17, 0), time(9, 0), time(12, 0), time(23, 59), time(13, 30)]


def _cls(name: str) -> str:
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {name} ')"


def _txt(el) -> str:
    return re.sub(r"\s+", " ", el.text_content()).strip()


def build(today: date = None) -> list[dict]:
    today = today or TODAY
    rng = random.Random(SEED)
    offsets = OFFSETS[:]
    rng.shuffle(offsets)
    out, k = [], 0
    for ci, (code, name, slug, items) in enumerate(COURSES):
        for ai, (title, desc) in enumerate(items):
            due = datetime.combine(today + timedelta(days=offsets[k]), rng.choice(TIMES), TZ)
            out.append({"course": f"{code} {name}", "code": code, "slug": slug,
                        "course_id": 70001 + ci, "id": 50001 + k, "title": title,
                        "description": desc, "due": due})
            k += 1
    return out


# ---- real strings in the templates ------------------------------------------

def real_strings(trees: dict, raw: dict) -> set[str]:
    real: set[str] = set()
    d, l, a = trees["dashboard"], trees["assignments"], trees["assignment"]
    for el in d.xpath(f"//span[{_cls('Grouping-styles__title')}]|//div[{_cls('PlannerItem-styles__type')}]"):
        real.add(_txt(el))
    for el in d.xpath(f"//div[{_cls('planner-item')}]//a/span[last()]|//div[{_cls('planner-item')}]//button/span[last()]"):
        real.add(_txt(el))
    for el in d.xpath(f"//div[{_cls('PlannerItem-styles__location')}]"):
        real.add(_txt(el))
    for el in l.xpath(f"//a[{_cls('ig-title')}]") + a.xpath("//*[@data-testid='title']|//*[@id='breadcrumbs']//li"):
        real.add(_txt(el))
    for t in (trees["assignments"].findtext(".//title"), a.findtext(".//title")):
        real |= {x.strip() for x in (t or "").split(":")}
    for page in raw.values():
        for m in re.finditer(r'"(?:display_name|short_name|sortable_name|name)":"([^"]{3,80})"', page):
            if "current_user" in page[max(0, m.start() - 400):m.start()]:
                v = m.group(1).replace(",", " ")
                real.add(m.group(1))
                real |= {p for p in v.split() if len(p) >= 3}
        for m in re.finditer(r"https?://([a-z0-9.-]*canvas[a-z0-9.-]*)", page):
            host = m.group(1)
            real.add(host)
            real |= {p for p in host.split(".") if p not in ("canvas", "edu", "com", "org", "instructure", "login", "www", "net", "io")}
    from bank.classify import COURSE_RE
    for s in list(real):
        real |= {f"{m.group(1)} {m.group(2)}" for m in COURSE_RE.finditer(s)}
        real |= {f"{m.group(1)}{m.group(2)}" for m in COURSE_RE.finditer(s)}
    ui = {"assignments", "assignment", "dashboard", "courses", "course", "quiz", "lab", "lecture"}
    return {s for s in real if len(s) >= 3 and re.search("[A-Za-z]", s) and s.lower() not in ui}


def real_ids(raw: dict) -> set[str]:
    ids: set[str] = set()
    for page in raw.values():
        ids |= set(re.findall(r"/courses/(\d+)", page))
        ids |= set(re.findall(r"/assignments/(\d+)", page))
        ids |= set(re.findall(r"/submissions/(\d+)", page))
        ids |= set(re.findall(r"/items/(\d+)", page))
    return ids


# ---- rendering ----------------------------------------------------------------

def _strip(el) -> None:
    for x in el.xpath(".//script|.//style|.//noscript|.//iframe|.//img|.//link|.//meta"):
        x.getparent().remove(x)


def _set(el, text: str) -> None:
    for c in list(el):
        el.remove(c)
    el.text = text


def _neutral(el, ids: set[str]) -> None:
    """Links we did not set point nowhere; real ids in attributes are zeroed."""
    for x in el.iter():
        if not isinstance(x.tag, str):
            continue
        for k, v in list(x.attrib.items()):
            if k == "style" and "url(" in v:
                del x.attrib[k]
            elif k in ("href", "src", "action") and not x.get("data-fake"):
                x.attrib[k] = "#"
            elif re.search(r"\d{5,}", v):
                x.attrib[k] = re.sub(r"\d{5,}", lambda m: "0" if m.group(0) in ids else m.group(0), v)
        x.attrib.pop("data-fake", None)


def _when(d: datetime) -> str:
    """Canvas's list format, e.g. 'Nov 18 at 11:59pm'."""
    return f"{d:%b} {d.day} at {d.hour % 12 or 12}:{d:%M}{'am' if d.hour < 12 else 'pm'}"


def _time_el(d: datetime) -> lxml.html.HtmlElement:
    t = lxml.html.Element("time")
    t.attrib["datetime"] = d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    t.attrib["title"] = _when(d)
    t.text = _when(d)
    return t


def _page(title: str, *parts) -> str:
    body = "".join(lxml.html.tostring(p, encoding="unicode") for p in parts)
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"</head><body><p class='sample-note'>Sample coursework (made up for the Muse demo).</p>"
            f"{body}</body></html>\n")


def render_list(tree, course: list[dict], ids: set[str]) -> str:
    ag = copy.deepcopy(tree.xpath("//*[@id='ag-list']")[0])
    _strip(ag)
    groups = ag.xpath(f".//li[{_cls('item-group-condensed')}]")
    for g in groups[1:]:
        g.getparent().remove(g)
    g = groups[0]
    for b in g.xpath(f".//*[{_cls('ig-header-title')}]//button"):
        b.attrib["aria-label"] = "Assignments toggle assignment visibility"
        b.tail = "Assignments"
    rows = g.xpath(f".//li[{_cls('assignment')}]")
    ul = rows[0].getparent()
    tpl = rows[0]
    for r in rows:
        ul.remove(r)
    for a in course:
        li = copy.deepcopy(tpl)
        row = li.xpath(f".//div[{_cls('ig-row')}]")[0]
        row.attrib["id"] = f"assignment_{a['id']}"
        link = li.xpath(f".//a[{_cls('ig-title')}]")[0]
        link.attrib.update({"href": f"{a['id']}.html", "data-fake": "1"})
        _set(link, a["title"])
        for det in li.xpath(f".//div[{_cls('ig-details')}]"):
            det.attrib["id"] = f"assignment_details_{a['id']}"
            due = det.xpath(f".//div[{_cls('assignment-date-due')}]")[0]
            for c in list(det):
                if c is not due:
                    det.remove(c)
            fd = due.xpath(".//*[@data-testid='friendly-date-time']")[0]
            _set(fd, None)
            s = lxml.html.Element("span")
            s.text = _when(a["due"])
            fd.append(s)
            fd.append(_time_el(a["due"]))
        ul.append(li)
    _neutral(ag, ids)
    return _page(f"{course[0]['code']}: Assignments", ag)


def render_assignment(tree, a: dict, ids: set[str]) -> str:
    crumbs = copy.deepcopy(tree.xpath("//*[@id='breadcrumbs']")[0])
    content = copy.deepcopy(tree.xpath("//*[@id='content']")[0])
    for el in (crumbs, content):
        _strip(el)
    lis = crumbs.xpath(".//li")
    for li, (href, text) in zip(lis, (("assignments.html", a["course"]), ("assignments.html", "Assignments"),
                                      (None, a["title"]))):
        tgt = li.xpath(".//a") or li.xpath(".//span[not(*)]") or [li]
        if href and tgt[0].tag == "a":
            tgt[0].attrib.update({"href": href, "data-fake": "1"})
        _set(tgt[0], text)
    for h in content.xpath("//*[@data-testid='assignment-student-header']//h1"):
        _set(h, a["title"])
    for t in content.xpath(".//*[@data-testid='title']"):
        _set(t, a["title"])
    for sh in content.xpath(".//*[@data-testid='assignment-sub-header']"):
        _set(sh, None)
        fd = lxml.html.Element("span", **{"data-testid": "friendly-date-time"})
        fd.text = f"Due: {a['due']:%a %b} {a['due'].day}, {a['due']:%Y} "
        fd.append(_time_el(a["due"]))
        sh.append(fd)
    for kill in content.xpath(".//*[@data-testid='late-pill']|.//*[@data-testid='view-submission-link']"
                              "|.//*[@data-testid='student-footer']|.//*[@data-testid='submission-workflow-tracker']"
                              f"|.//*[{_cls('selected-submission-grade')}]"):
        kill.getparent().remove(kill)
    for d in content.xpath(".//*[@data-testid='assignments-2-assignment-description']"):
        _set(d, None)
        p = lxml.html.Element("p")
        p.text = a["description"]
        d.append(p)
    _neutral(crumbs, ids)
    _neutral(content, ids)
    return _page(a["title"], crumbs, content)


def render_dashboard(tree, items: list[dict], today: date, ids: set[str]) -> str:
    day_tpl = tree.xpath(f"//div[{_cls('planner-day')}]")[0]
    item_li = next(it.getparent() for it in tree.xpath(f"//div[{_cls('planner-item')}]")
                   if any("/assignments/" in (x.get("href") or "") for x in it.xpath(".//a")))
    app = lxml.html.Element("div", **{"class": "PlannerApp large"})
    by_day: dict[date, list[dict]] = {}
    for a in sorted(items, key=lambda a: a["due"]):
        by_day.setdefault(a["due"].date(), []).append(a)
    for d, rows in by_day.items():
        day = copy.deepcopy(day_tpl)
        _strip(day)
        h = day.xpath(".//h2")[0]
        label = ("Today, " if d == today else "Tomorrow, " if d == today + timedelta(days=1)
                 else "Yesterday, " if d == today - timedelta(days=1) else f"{d:%A}, ")
        _set(h, None)
        sec = lxml.html.Element("div", **{"class": "Day-styles__secondary"})
        sec.text = f"{label}{d:%B} {d.day}"
        h.append(sec)
        groups = day.xpath(f".//div[{_cls('planner-grouping')}]")
        gtpl = copy.deepcopy(groups[0])
        holder = groups[0].getparent()
        for g in groups:
            holder.remove(g)
        for course in dict.fromkeys(a["course"] for a in rows):
            g = copy.deepcopy(gtpl)
            hero = g.xpath(f".//a[{_cls('Grouping-styles__hero')}]")[0]
            slug = next(a["slug"] for a in rows if a["course"] == course)
            hero.attrib.update({"href": f"{slug}/assignments.html", "data-fake": "1"})
            _set(g.xpath(f".//span[{_cls('Grouping-styles__title')}]")[0], course)
            ol = g.xpath(f".//ol[{_cls('Grouping-styles__items')}]")[0]
            for c in list(ol):
                ol.remove(c)
            for a in (x for x in rows if x["course"] == course):
                li = copy.deepcopy(item_li)
                _strip(li)
                for lab in li.xpath(f".//div[{_cls('PlannerItem-styles__completed')}]//label//span[not(*)]"):
                    lab.text = f"Assignment {a['title']} is not marked as done." if lab.text else lab.text
                _set(li.xpath(f".//div[{_cls('PlannerItem-styles__type')}]")[0], None)
                li.xpath(f".//div[{_cls('PlannerItem-styles__type')}]")[0].append(
                    lxml.html.fromstring(f"<span>{html.escape(course)}</span>"))
                link = [x for x in li.xpath(".//a") if "/assignments/" in (x.get("href") or "")][0]
                link.attrib.update({"href": f"{a['slug']}/{a['id']}.html", "data-fake": "1"})
                sp = link.xpath("./span")
                due_txt = f"{a['due']:%A, %B} {a['due'].day}, {a['due']:%Y} {a['due']:%I:%M %p}".replace(" 0", " ")
                _set(sp[0], f"Assignment {a['title']}, due {due_txt}.")
                _set(sp[-1], a["title"])
                for loc in li.xpath(f".//div[{_cls('PlannerItem-styles__location')}]"):
                    loc.getparent().remove(loc)
                for due in li.xpath(f".//div[{_cls('PlannerItem-styles__due')}]"):
                    _set(due, f"Due: {a['due']:%I:%M %p}".replace(": 0", ": "))
                for sc in li.xpath(f".//div[{_cls('PlannerItem-styles__score')}]"):
                    sc.getparent().remove(sc)
                ol.append(li)
            holder.append(g)
        app.append(day)
    _neutral(app, ids)
    return _page("Dashboard", app)


def check_clean(name: str, page: str, real: set[str], ids: set[str]) -> None:
    left = sorted(r for r in real if re.search(rf"(?<![A-Za-z0-9]){re.escape(r)}(?![A-Za-z0-9])", page, re.I))
    left += sorted(i for i in ids if re.search(rf"(?<!\d){i}(?!\d)", page))
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", page):
        left.append("an email address")
    if left:
        raise SystemExit(f"{name}: {len(left)} real string(s) still in output; stopping "
                         f"(not printed). Kinds: {sorted({'id' if x in ids else 'text' for x in left})}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts/make_test_canvas.py")
    ap.add_argument("--templates", type=Path, default=ROOT / "data" / "canvas-templates")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "test-canvas")
    ap.add_argument("--today", help=f"YYYY-MM-DD the coursework is built for (default {TODAY})")
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else TODAY

    raw = {n: (a.templates / f"{n}.html").read_text(encoding="utf-8", errors="replace")
           for n in ("dashboard", "assignments", "assignment")}
    trees = {n: lxml.html.fromstring(v) for n, v in raw.items()}
    real, ids = real_strings(trees, raw), real_ids(raw)
    fake_words = " ".join(f"{c} {n} {s}" for c, n, s, _ in COURSES).lower()
    real = {r for r in real if r.lower() not in fake_words}
    items = build(today)
    out = a.out.resolve()
    pages: dict[Path, str] = {out / "dashboard.html": render_dashboard(trees["dashboard"], items, today, ids)}
    for code, _, slug, _ in COURSES:
        course = [x for x in items if x["slug"] == slug]
        pages[out / slug / "assignments.html"] = render_list(trees["assignments"], course, ids)
        for x in course:
            pages[out / slug / f"{x['id']}.html"] = render_assignment(trees["assignment"], x, ids)
    for p, page in pages.items():
        check_clean(p.relative_to(out).as_posix(), page, real, ids)
    for p, page in pages.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(page, encoding="utf-8")
    truth = [{"course": x["course"], "code": x["code"], "title": x["title"],
              "due_date": x["due"].date().isoformat(), "due_time": f"{x['due']:%H:%M}",
              "url": (out / x["slug"] / f"{x['id']}.html").as_uri(), "description": x["description"]}
             for x in items]
    (out / "truth.json").write_text(json.dumps({"today": today.isoformat(), "assignments": truth}, indent=1))
    print(f"wrote {len(pages)} pages ({len(items)} assignments, {len(COURSES)} courses) to {out}; "
          f"scrubbed {len(real)} real strings and {len(ids)} ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
