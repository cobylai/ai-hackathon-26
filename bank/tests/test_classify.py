import json
import unittest
from datetime import date
from pathlib import Path

from bank import classify
from bank.extract import build_fields, parse_headers

FIX = Path(__file__).resolve().parent.parent / "eval" / "fixtures"


class TestCourse(unittest.TestCase):
    def test_finds_and_normalises(self):
        self.assertEqual(classify.find_course("CS 3110 PS4 regrade"), "CS 3110")
        self.assertEqual(classify.find_course("ENGRD2700 project"), "ENGRD 2700")
        self.assertEqual(classify.find_course(None, "the PHYS 1112 quiz"), "PHYS 1112")
        self.assertEqual(classify.find_course("CS 2024 lecture"), "CS 2024")  # real course, not a year

    def test_rejects_month_season_year(self):
        for t in ("FALL 2026 schedule", "NOV 2026 statement", "SPRING 2027 enrollment",
                  "DECEMBER 2025 recap"):
            self.assertIsNone(classify.find_course(t), t)

    def test_rejects_stoplist_prefixes(self):
        for t in ("ROOM 1234", "PIN 4821", "CODE 5521", "ZOOM 9988", "REF 1002", "ID 4455"):
            self.assertIsNone(classify.find_course(t), t)
        self.assertEqual(classify.find_course("Fall 2026: CS 2800 in ROOM 1234"), "CS 2800")


class TestPerson(unittest.TestCase):
    def test_people(self):
        self.assertTrue(classify.is_person("Marcus Bell", "mb771@univ.example.edu", True))
        self.assertTrue(classify.is_person("Dr. Helen Okafor", "hokafor@univ.example.edu", None))

    def test_automated(self):
        self.assertFalse(classify.is_person("Bursar Office", "bursar@univ.example.edu", True))
        self.assertFalse(classify.is_person("Campus Dining", "dining-news@univ.example.edu", True))
        self.assertFalse(classify.is_person("Outing Club", "outing@clubs.univ.example.edu", True))
        self.assertFalse(classify.is_person("Olin Library", "library-notices@univ.example.edu", True))
        self.assertFalse(classify.is_person("Pat Lee", "pat@univ.example.edu", False))

    def test_folder_rule(self):
        self.assertEqual(classify.folder_for("email", "CS 3110", True), "course")
        self.assertEqual(classify.folder_for("email", None, True), "person")
        self.assertEqual(classify.folder_for("email", None, False), "other")
        self.assertEqual(classify.folder_for("page", None, True), "other")


class TestFixtureFolders(unittest.TestCase):
    """Folder and course from headers + code rules alone (model says 'person' for all)."""

    def test_every_fixture(self):
        for p in sorted(FIX.glob("*.json")):
            f = json.loads(p.read_text())
            raw = {"sender_is_person": True, "summary": "x", "deadlines": []}
            e = build_fields(f["text"], f["kind"], date.fromisoformat(f.get("ingest_date", "2026-11-14")), [raw])
            exp = f["expected"]
            self.assertEqual(e["folder"], exp["folder"], f["id"])
            self.assertEqual(e["course"], exp["course"], f["id"])
            self.assertEqual(e["sender_address"], exp["sender_address"], f["id"])
            self.assertEqual(e["sent_date"], exp["sent_date"], f["id"])


class TestHeaders(unittest.TestCase):
    def test_parse(self):
        h = parse_headers("From: Jordan Kim <jk2290@univ.example.edu>\n"
                          "Date: Tue, 10 Nov 2026 01:12:55 -0500\nSubject: Fwd: hi\n\nbody\n"
                          "From: Hack Club\n")
        self.assertEqual(h["sender_address"], "jk2290@univ.example.edu")
        self.assertEqual(h["sender_name"], "Jordan Kim")
        self.assertEqual(h["sent_date"], date(2026, 11, 10))
        self.assertEqual(h["subject"], "Fwd: hi")

    def test_no_headers(self):
        self.assertEqual(parse_headers("CS 2800 Discrete Structures - Fall 2026\nSchedule"), {})


if __name__ == "__main__":
    unittest.main()
