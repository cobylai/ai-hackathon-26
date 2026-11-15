"""search / by_person / due over a hand-written bank. No model, no network."""
import socket
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from bank import by_person, due, search, store


def E(id_, folder, name, addr, sent, subject, body, deadlines=(), course=None, ask=None):
    return {"id": id_, "kind": "email", "folder": folder, "source": f"msg:{id_}",
            "sender_name": name, "sender_address": addr, "sent_date": sent, "subject": subject,
            "ask": ask, "deadlines": [dict(zip(("phrase", "date", "time"), d)) for d in deadlines],
            "course": course, "topic": None, "ingested_at": "2026-11-14T10:00:00", "body": body}


ENTRIES = [
    E("a00000000001", "course", "Priya Natarajan", "pn42@univ.example.edu", "2026-11-09",
      "CS 3110 PS4 regrade", "Priya needs the commit hash for the PS4 regrade.",
      [("Friday at 5pm", "2026-11-13", "17:00")], "CS 3110", "Send the commit hash."),
    E("a00000000002", "course", "Prof. Daniel Reyes", "dreyes@univ.example.edu", "2026-11-12",
      "ENGRD 2700 project extension", "Project 2 now due Monday night.",
      [("Monday 11:59pm", "2026-11-16", "23:59")], "ENGRD 2700"),
    E("a00000000003", "person", "Dr. Helen Okafor", "hokafor@univ.example.edu", "2026-11-11",
      "Pre-enrollment check-in", "Book a slot before Tuesday to confirm the spring schedule.",
      [("before Tuesday", "2026-11-17", None)]),
    E("a00000000004", "other", "Bursar Office", "bursar@univ.example.edu", "2026-11-11",
      "Statement available", "November statement is out; payment due on the 25th.",
      [("5:00pm on the 25th", "2026-11-25", "17:00")]),
    E("a00000000005", "person", "Priya Natarajan", "pn42@univ.example.edu", "2026-11-13",
      "coffee?", "Priya asks about coffee next week, no deadline.", [("sometime", None, None)]),
    E("a00000000006", "course", "Aisha Rahman", "ar512@univ.example.edu", "2026-11-13",
      "INFO 1200 group project", "Slides draft Sunday, presentation Wednesday.",
      [("Sunday night", "2026-11-15", None), ("Wednesday at 2:30", "2026-11-18", None),
       ("the Friday after", "2026-11-20", None)], "INFO 1200"),
]


def _no_network(*a, **k):
    raise AssertionError("reader touched the network")


class TestReaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        for e in ENTRIES:
            store.write_entry(e, cls.root)
        cls.net = mock.patch.object(socket.socket, "connect", _no_network)
        cls.net.start()

    @classmethod
    def tearDownClass(cls):
        cls.net.stop()
        cls.tmp.cleanup()

    def ids(self, rows):
        return [r["id"] for r in rows]

    def test_search_subject_beats_body(self):
        rows = search("regrade", root=self.root)
        self.assertEqual(self.ids(rows), ["a00000000001"])
        rows = search("Priya commit", root=self.root)
        self.assertEqual(rows[0]["id"], "a00000000001")  # 2 hits beats 1
        self.assertIn("a00000000005", self.ids(rows))

    def test_search_ties_newest_first(self):
        rows = search("priya", root=self.root)
        self.assertEqual(self.ids(rows), ["a00000000005", "a00000000001"])

    def test_search_stopwords_and_limit(self):
        self.assertEqual(search("what is the", root=self.root), [])
        self.assertEqual(len(search("2026 project statement slot", limit=2, root=self.root)), 2)

    def test_search_course_and_deadline_phrase(self):
        self.assertEqual(self.ids(search("ENGRD", root=self.root)), ["a00000000002"])
        self.assertIn("a00000000004", self.ids(search("25th", root=self.root)))

    def test_by_person(self):
        self.assertEqual(self.ids(by_person("priya", root=self.root)), ["a00000000005", "a00000000001"])
        self.assertEqual(self.ids(by_person("bursar@", root=self.root)), ["a00000000004"])
        self.assertEqual(by_person("nobody", root=self.root), [])

    def test_due_range_inclusive_sorted(self):
        rows = due("2026-11-16", "2026-11-20", root=self.root)
        self.assertEqual([(r["date"], r["time"]) for r in rows],
                         [("2026-11-16", "23:59"), ("2026-11-17", None), ("2026-11-18", None),
                          ("2026-11-20", None)])
        self.assertEqual(rows[0]["entry"]["subject"], "ENGRD 2700 project extension")
        self.assertEqual(rows[1]["phrase"], "before Tuesday")

    def test_due_single_day_and_date_objects(self):
        rows = due(date(2026, 11, 13), date(2026, 11, 13), root=self.root)
        self.assertEqual([r["entry"]["id"] for r in rows], ["a00000000001"])
        self.assertEqual(due("2026-12-01", "2026-12-31", root=self.root), [])

    def test_unresolved_never_due(self):
        rows = due("2000-01-01", "2100-01-01", root=self.root)
        self.assertNotIn("sometime", [r["phrase"] for r in rows])

    def test_time_ordering_same_day(self):
        tmp = tempfile.TemporaryDirectory()
        r = Path(tmp.name)
        store.write_entry(E("b00000000001", "other", "A", "a@x.edu", "2026-11-10", "a", "a",
                            [("Fri", "2026-11-13", None)]), r)
        store.write_entry(E("b00000000002", "other", "B", "b@x.edu", "2026-11-10", "b", "b",
                            [("Fri 9am", "2026-11-13", "09:00")]), r)
        self.assertEqual([x["time"] for x in due("2026-11-13", "2026-11-13", root=r)], ["09:00", None])
        tmp.cleanup()

    def test_readers_do_not_import_llm(self):
        import subprocess
        import sys
        code = ("import sys, tempfile; from bank import search, by_person, due; "
                "d = tempfile.mkdtemp(); search('x', root=__import__('pathlib').Path(d)); "
                "due('2026-01-01', '2026-12-31', root=__import__('pathlib').Path(d)); "
                "print('llm' in sys.modules)")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                             cwd=Path(__file__).resolve().parents[2])
        self.assertEqual(out.stdout.strip(), "False", out.stderr)


if __name__ == "__main__":
    unittest.main()
