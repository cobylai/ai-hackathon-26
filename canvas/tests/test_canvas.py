"""Mock Canvas: generator scrub, reader round trip, filing, due route. No model server.

templates/ holds a tiny hand-written Canvas page set with the real markup's
classes and invented "real" strings (ZORK 4410, Pat Quimby, canvas.zork.example)
standing in for what a saved page would leak.
"""
import importlib.util
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import bank
from bank import extract
from canvas import read

ROOT = Path(__file__).resolve().parents[2]
TPL = Path(__file__).resolve().parent / "templates"
LEAKS = ["ZORK", "Secret Underground", "Grue", "Pat Quimby", "Quimby", "canvas.zork.example",
         "zorkcdn", "91919", "1234567", "7777777", "3333333", "Flathead", "@"]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load("make_test_canvas")
sync = _load("sync_test_canvas")


class Generated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "test-canvas"
        gen.main(["--templates", str(TPL), "--out", str(cls.out), "--today", "2026-11-15"])
        cls.truth = json.loads((cls.out / "truth.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_counts(self):
        a = self.truth["assignments"]
        self.assertGreaterEqual(len(a), 20)
        self.assertGreaterEqual(len({x["course"] for x in a}), 3)
        self.assertEqual(len(list(self.out.rglob("*.html"))), 1 + 4 + len(a))
        self.assertEqual(self.truth["today"], "2026-11-15")

    def test_no_template_strings_left(self):
        for p in self.out.rglob("*.html"):
            page = p.read_text()
            for s in LEAKS:
                self.assertNotIn(s.lower(), page.lower(), f"{s!r} left in {p.name}")
            self.assertNotIn("<script", page)
            self.assertNotIn("url(", page)
            self.assertIn("Sample coursework", page)

    def test_reader_matches_truth(self):
        want = {t["url"]: t for t in self.truth["assignments"]}
        n = 0
        for f in read.course_folders(self.out):
            for row in read.read_assignment_list(f / "assignments.html"):
                a = read.read_assignment(Path(row["url"].removeprefix("file://")))
                t = want[a["url"]]
                self.assertEqual((a["course"], a["title"], a["due_date"], a["due_time"], a["description"]),
                                 (t["course"], t["title"], t["due_date"], t["due_time"], t["description"]))
                self.assertEqual((row["title"], row["due_date"], row["due_time"]),
                                 (t["title"], t["due_date"], t["due_time"]))
                n += 1
        self.assertEqual(n, len(want))

    def test_dashboard_matches_truth(self):
        want = {t["url"]: t for t in self.truth["assignments"]}
        rows = read.read_dashboard(self.out / "dashboard.html")
        self.assertEqual(len(rows), len(want))
        for r in rows:
            t = want[r["url"]]
            self.assertEqual((r["course"], r["title"], r["due_date"], r["due_time"]),
                             (t["course"], t["title"], t["due_date"], t["due_time"]))

    def test_today_moves_dates(self):
        b = gen.build(date(2026, 11, 22))
        a = gen.build(date(2026, 11, 15))
        self.assertEqual([(x["due"].date() - date(2026, 11, 15)).days for x in a],
                         [(x["due"].date() - date(2026, 11, 22)).days for x in b])


class Scrub(unittest.TestCase):
    def test_stops_on_leftover(self):
        with tempfile.TemporaryDirectory() as d:
            bad = [list(c) for c in gen.COURSES]
            bad[0][3] = [(t, "Ask Pat Quimby about it.") for t, _ in bad[0][3]]
            with mock.patch.object(gen, "COURSES", [tuple(c) for c in bad]):
                with self.assertRaises(SystemExit) as e:
                    gen.main(["--templates", str(TPL), "--out", d])
            self.assertIn("real string", str(e.exception))
            self.assertNotIn("Quimby", str(e.exception))
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_committed_scripts_hold_no_template_strings(self):
        for p in (ROOT / "scripts" / "make_test_canvas.py", ROOT / "scripts" / "sync_test_canvas.py",
                  ROOT / "scripts" / "save_canvas_pages.py", ROOT / "canvas" / "read.py"):
            self.assertIsNone(re.search(r"cornell", p.read_text(), re.I), p.name)


class Filing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_due_phrase(self):
        self.assertEqual(read.due_phrase("2026-11-18", "23:59"), "Due Wed Nov 18 at 11:59pm")
        self.assertEqual(read.due_phrase("2026-11-18", "09:00"), "Due Wed Nov 18 at 9:00am")
        self.assertIsNone(read.due_phrase(None, None))

    def test_filed_entry_and_due_route(self):
        a = {"course": "HIST 2147 Maps and Empires", "title": "Essay 2 Final", "due_date": "2026-11-19",
             "due_time": "12:00", "url": "file:///x/hist2147/50005.html", "description": "Submit it."}

        def fake(text, kind):
            self.assertEqual(kind, "page")
            return {"summary": "Final essay.", "ask": "Submit the revised essay 2.",
                    "deadlines": ["Thursday"], "sender_is_person": False}
        with mock.patch.object(extract, "ask_model", side_effect=fake):
            r = sync.file_assignment(a, "2026-11-15", lambda *x, **k: bank.ingest(*x, root=self.root, **k))
        e = r["entry"]
        self.assertEqual((e["kind"], e["sender_name"], e["subject"], e["source"], e["course"]),
                         ("canvas", a["course"], a["title"], a["url"], "HIST 2147"))
        self.assertEqual(e["deadlines"], [{"phrase": "Due Thu Nov 19 at 12:00pm", "date": "2026-11-19",
                                           "time": "12:00"}])
        from reason.answer import _due
        ans = _due("what's due this week", date(2026, 11, 15), self.root)
        self.assertIn("Thu Nov 19 noon  Submit the revised essay 2 (HIST 2147 Maps and Empires, Nov 15)",
                      ans.text)

    def test_refuses_other_banks(self):
        (self.root / "truth.json").write_text('{"today": "2026-11-15", "assignments": []}')
        with mock.patch.dict("os.environ", {"MUSE_BANK_DIR": str(self.root / "bank")}):
            with self.assertRaises(SystemExit):
                sync.main([str(self.root)])


class MailCheck(unittest.TestCase):
    def test_due_check_counts_only_mail(self):
        mm = _load("make_test_mail")
        by_path = {"m.md": {"subject": "Hackathon team name", "kind": "email"},
                   "c.md": {"subject": "Essay 2 Final", "kind": "canvas"}}
        a = mock.Mock(sources=["m.md", "c.md"])
        self.assertEqual(mm._subjects_from(a, by_path, kinds=("email",)), {"Hackathon team name"})
        self.assertEqual(mm._subjects_from(a, by_path), {"Hackathon team name", "Essay 2 Final"})


if __name__ == "__main__":
    unittest.main()
