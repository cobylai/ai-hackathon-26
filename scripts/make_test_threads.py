"""Fake Gmail thread pages from one real saved thread page (brief N).

    uv run python scripts/make_test_threads.py N [--template data/templates/thread.html]
                                                 [--out data/test-threads]

The template is a single-message thread page saved from the test account
(gitignored, under data/). Each output page keeps Gmail's real message markup
(the classes the partner's reader looks for) but has the sender name, address,
date, subject and body replaced with one email from scripts/make_test_mail.py
(same senders, text and fixed seed as brief M). Gmail's scripts are dropped, so
the page opens offline as a local file. Also writes truth.json (brief M's shape).
The template's own sender is read from the page and scrubbed everywhere, so
no real name or address ends up in the output or in this script.
"""
from __future__ import annotations

import argparse
import copy
import html
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import lxml.html

ROOT = Path(__file__).resolve().parents[1]


def _cls(name: str) -> str:
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {name} ')"


def load_generator(path: Path = ROOT / "scripts" / "make_test_mail.py"):
    spec = importlib.util.spec_from_file_location("make_test_mail", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_mail(m: dict) -> dict:
    """Split brief M's text into header date/time and body."""
    head, _, body = m["text"].partition("\n\n")
    dm = re.search(r"^Date: (.+?) [-+]\d{4}$", head, re.M)
    sent = datetime.strptime(dm.group(1), "%a, %d %b %Y %H:%M:%S")
    return {**m, "body": body.strip(), "sent_dt": sent}


def gmail_date(d: datetime) -> str:
    """The live account's title format, e.g. '14 Nov 2026, 22:33'."""
    return f"{d.day} {d:%b %Y}, {d:%H:%M}"


def load_template(path: Path):
    tree = lxml.html.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    msgs = tree.xpath(f"//div[{_cls('adn')} and {_cls('ads')}]")
    if len(msgs) != 1:
        raise SystemExit(f"template must be a single-message thread, found {len(msgs)} messages")
    sender = msgs[0].xpath(f".//span[{_cls('gD')}]")[0]
    real = {sender.get("email") or "", sender.get("name") or ""} - {""}
    for s in msgs[0].xpath(".//script|.//style"):
        s.getparent().remove(s)
    return msgs[0], real


def render(msg_tpl, real: set[str], m: dict) -> str:
    msg = copy.deepcopy(msg_tpl)
    for el in msg.xpath(f".//span[{_cls('gD')}]"):
        el.attrib["email"], el.attrib["name"] = m["address"], m["name"]
        for c in list(el):
            el.remove(c)
        el.text = m["name"]
    for el in msg.xpath(f".//span[{_cls('g3')}]"):
        for c in list(el):
            el.remove(c)
        el.attrib["title"] = gmail_date(m["sent_dt"])
        el.text = f"{m['sent_dt']:%b} {m['sent_dt'].day}"
    for el in msg.xpath(f".//div[{_cls('a3s')}]"):
        for c in list(el):
            el.remove(c)
        el.text = None
        for line in m["body"].split("\n"):
            div = lxml.html.Element("div")
            div.text = line
            if not line:
                div.append(lxml.html.Element("br"))
            el.append(div)
    # Scrub the template's sender anywhere else (hovercards, avatar alt text, ...).
    for el in msg.iter():
        for k, v in list(el.attrib.items()):
            for r in real:
                if r in v:
                    el.attrib[k] = v.replace(r, m["address"] if "@" in r else m["name"])
        for part in ("text", "tail"):
            v = getattr(el, part)
            if v:
                for r in real:
                    v = v.replace(r, m["address"] if "@" in r else m["name"])
                setattr(el, part, v)
    subject = html.escape(m["subject"])
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{subject} - Gmail</title></head>"
            f"<body><h2 class='hP'>{subject}</h2>"
            + lxml.html.tostring(msg, encoding="unicode") + "</body></html>\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts/make_test_threads.py")
    ap.add_argument("n", type=int)
    ap.add_argument("--template", type=Path, default=ROOT / "data" / "templates" / "thread.html")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "test-threads")
    ap.add_argument("--generator", type=Path, default=ROOT / "scripts" / "make_test_mail.py")
    a = ap.parse_args(argv)

    gen = load_generator(a.generator)
    mails = [parse_mail(m) for m in gen.build()]
    if a.n > len(mails):
        print(f"make_test_mail.py builds {len(mails)} emails; writing {len(mails)}, not {a.n}")
    mails = mails[: a.n]
    msg_tpl, real = load_template(a.template)
    a.out.mkdir(parents=True, exist_ok=True)
    for m in mails:
        page = render(msg_tpl, real, m)
        if any(r in page for r in real):
            raise SystemExit(f"{m['key']}: template sender still in output")
        (a.out / f"{m['key']}.html").write_text(page, encoding="utf-8")
    truth = [{k: v for k, v in m.items() if k not in ("text", "body", "sent_dt")} | {
        "date_shown": gmail_date(m["sent_dt"])} for m in mails]
    (a.out / "truth.json").write_text(json.dumps({"today": gen.TODAY.isoformat(), "mail": truth}, indent=1))
    print(f"wrote {len(mails)} thread pages to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
