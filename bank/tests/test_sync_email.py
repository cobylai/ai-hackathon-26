import importlib.util
import unittest
from pathlib import Path

_p = Path(__file__).resolve().parents[2] / "scripts" / "sync_email.py"
_spec = importlib.util.spec_from_file_location("sync_email", _p)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)


class TestSyncEmail(unittest.TestCase):
    def test_split_sender(self):
        self.assertEqual(S.split_sender("Alex Chen <alex@example.edu>"), ("Alex Chen", "alex@example.edu"))
        self.assertEqual(S.split_sender("alex@example.edu"), (None, "alex@example.edu"))
        self.assertEqual(S.split_sender("Alex"), ("Alex", None))
        self.assertEqual(S.split_sender(""), (None, None))

    def test_iso_date(self):
        self.assertEqual(S.iso_date("Thu, Nov 12, 2026, 4:30 PM"), "2026-11-12")
        self.assertEqual(S.iso_date("Sat, Nov 14, 2026, 9:12 AM"), "2026-11-14")
        self.assertEqual(S.iso_date("14 Nov 2026, 22:24"), "2026-11-14")
        self.assertIsNone(S.iso_date("9:12 AM"))

    def test_file_thread_oldest_first_and_skips_empty(self):
        calls = []

        def fake_ingest(text, **kw):
            calls.append((text, kw))
            return {"status": "added", "path": kw["source"]}

        msgs = [("B <b@x.org>", "Sat, Nov 14, 2026, 9:12 AM", "newest"),
                ("A <a@x.org>", "Thu, Nov 12, 2026, 4:30 PM", "   "),
                ("A <a@x.org>", "Thu, Nov 12, 2026, 4:00 PM", "oldest")]
        S.file_thread("t1", "Subj", msgs, fake_ingest)
        self.assertEqual([c[0] for c in calls], ["oldest", "newest"])
        self.assertEqual(calls[0][1]["source"], "gmail:t1#0")
        self.assertEqual(calls[1][1]["sender_address"], "b@x.org")
        self.assertEqual(calls[1][1]["sent_date"], "2026-11-14")
        self.assertEqual(calls[1][1]["kind"], "email")


if __name__ == "__main__":
    unittest.main()
