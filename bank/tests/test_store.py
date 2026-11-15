"""Store, de-duplication and index. The model call is stubbed; no server needed."""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import bank
from bank import extract, store

EMAIL = ("From: Marcus Bell <mb771@univ.example.edu>\nDate: Thu, 12 Nov 2026 22:47:19 -0500\n"
         "Subject: re: lab 6\n\nyo can you push your part to the shared doc? i want to start "
         "the writeup tomorrow morning.")
RAW = {"sender_name": "Marcus Bell", "sender_address": "Marcus Bell", "sender_is_person": True,
       "subject": "re: lab 6", "summary": "Marcus wants your circuit analysis in the shared doc.",
       "ask": "Push your part to the shared doc.", "deadlines": ["tomorrow morning"],
       "course": None, "topic": "lab 6"}


class StoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.calls = 0

        def fake(text, kind):
            self.calls += 1
            return dict(RAW)
        self.patch = mock.patch.object(extract, "ask_model", side_effect=fake)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()


class TestIngest(StoreCase):
    def test_entry_written_with_resolved_date(self):
        r = bank.ingest(EMAIL, "msg:1", "email", root=self.root)
        self.assertEqual(r["status"], "added")
        p = Path(r["path"])
        self.assertEqual(p.parent.name, "person")
        self.assertTrue(p.name.startswith("2026-11-12-lab-6-"))
        e = store.read_entry(p)
        self.assertEqual(e["sender_address"], "mb771@univ.example.edu")  # header beats the model's name
        self.assertEqual(e["deadlines"], [{"phrase": "tomorrow morning", "date": "2026-11-13", "time": None}])
        self.assertEqual(e["body"], RAW["summary"])
        idx = (self.root / "index.md").read_text()
        self.assertIn("2026-11-12 | Marcus Bell | person |", idx)
        self.assertIn("due 2026-11-13 (tomorrow morning)", idx)

    def test_duplicate_same_content(self):
        bank.ingest(EMAIL, "msg:1", "email", root=self.root)
        r = bank.ingest(EMAIL + "\n\n", "saved/other-name.txt", "email", root=self.root)
        self.assertEqual(r["status"], "duplicate")
        self.assertEqual(self.calls, 1)
        self.assertEqual(len(store.all_entries(self.root)), 1)

    def test_duplicate_same_source_changed_text(self):
        bank.ingest(EMAIL + "\n3 minutes ago", "msg:42", "email", root=self.root)
        r = bank.ingest(EMAIL + "\n1 hour ago", "msg:42", "email", root=self.root)
        self.assertEqual(r["status"], "duplicate")
        self.assertEqual(self.calls, 1)

    def test_different_items_both_added(self):
        bank.ingest(EMAIL, "msg:1", "email", root=self.root)
        r = bank.ingest(EMAIL.replace("lab 6", "lab 7"), "msg:2", "email", root=self.root)
        self.assertEqual(r["status"], "added")
        self.assertEqual(len(store.all_entries(self.root)), 2)

    def test_bad_kind(self):
        with self.assertRaises(ValueError):
            bank.ingest(EMAIL, "x", "tweet", root=self.root)

    def test_env_var_location(self):
        with mock.patch.dict(os.environ, {"MUSE_BANK_DIR": str(self.root / "elsewhere")}):
            self.assertEqual(store.bank_dir(), self.root / "elsewhere")
            r = bank.ingest(EMAIL, "msg:9", "email")
            self.assertTrue(r["path"].startswith(str(self.root / "elsewhere")))

    def test_page_uses_ingest_date(self):
        def fake(text, kind):
            return {"subject": "CS 2800 schedule", "summary": "Due dates.",
                    "deadlines": ["PS5 due Nov 24 at 11:59pm"], "sender_is_person": True}
        with mock.patch.object(extract, "ask_model", side_effect=fake):
            r = bank.ingest("CS 2800 - Fall 2026\nPS5 due Nov 24 at 11:59pm.",
                            "https://x.example/cs2800", "page", today=date(2026, 11, 14), root=self.root)
        e = r["entry"]
        self.assertEqual((e["folder"], e["course"], e["sent_date"]), ("course", "CS 2800", "2026-11-14"))
        self.assertIsNone(e["sender_address"])
        self.assertEqual(e["deadlines"][0]["date"], "2026-11-24")


class TestRoundTrip(unittest.TestCase):
    def test_render_parse(self):
        e = {"id": "abc123abc123", "kind": "email", "folder": "other", "source": "s",
             "sender_name": 'He said "hi"\n---', "sender_address": None, "sent_date": "2026-11-01",
             "subject": "x: y", "ask": None, "deadlines": [], "course": None, "topic": None,
             "ingested_at": "2026-11-14T00:00:00", "body": "Line one.\n---\nLine two."}
        back = store.parse(store.render(e))
        for k in store.FIELDS:
            self.assertEqual(back[k], e[k], k)
        self.assertEqual(back["body"], e["body"])


class TestIndexCap(StoreCase):
    def test_cap(self):
        from bank import index
        for i in range(5):
            bank.ingest(EMAIL.replace("lab 6", f"lab {i}"), f"msg:{i}", "email", root=self.root)
        with mock.patch.object(index, "INDEX_TOKEN_CAP", 200):
            index.rebuild_index(self.root)
        txt = (self.root / "index.md").read_text()
        self.assertIn("older entries omitted", txt)


if __name__ == "__main__":
    unittest.main()
