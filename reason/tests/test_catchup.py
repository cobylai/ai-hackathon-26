"""Catch-up route tests: bank in a temp dir, calendar mocked, no model, no network.

    uv run python -m unittest discover reason/tests
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import applecal
from bank import store
from reason import answer, catchup

SUN = date(2026, 11, 15)


def E(id_, name, sent, subject, body, ask=None, deadlines=None, kind="email", folder="person"):
    return {"id": id_, "kind": kind, "folder": folder, "source": f"t:{id_}", "sender_name": name,
            "sender_address": f"{id_}@example.edu", "sent_date": sent, "subject": subject,
            "ask": ask, "deadlines": deadlines or [], "course": None, "topic": None,
            "ingested_at": "2026-11-15T00:00:00", "body": body}


ENTRIES = [
    E("c00000000001", "Felix Ambrose", "2026-11-14", "cabin", "Felix wants the cabin money.",
      ask="Send me your $35 share", deadlines=[{"phrase": "Tuesday noon", "date": "2026-11-17", "time": "12:00"}]),
    E("c00000000002", "Hugo Sato", "2026-11-12", "team name", "Vote on the team name.",
      ask="Reply with your vote"),
    E("c00000000003", "Old Sender", "2026-11-01", "old", "An old ask.", ask="Do the old thing"),
    E("c00000000004", "ZOOL 2150", "2026-11-10", "PS 7", "Problem set 7 is posted.", kind="email",
      folder="course", deadlines=[{"phrase": "Due Sun Nov 15 at 11:59pm", "date": "2026-11-15", "time": "23:59"}]),
    E("c00000000005", "Prof. Far", "2026-11-13", "later", "Due next week.",
      ask="Turn in the essay", deadlines=[{"phrase": "Nov 20", "date": "2026-11-20", "time": None}]),
]

EVENTS = [{"title": "Hackathon judging", "start": datetime(2026, 11, 15, 12, 0),
           "end": datetime(2026, 11, 15, 13, 30), "location": "Duffield Atrium", "all_day": False}]


class Triggers(unittest.TestCase):
    def test_yes(self):
        for q in ["Catch me up", "catch me up please", "What's my day?", "what is my day like",
                  "What’s going on today?", "brief me", "How's my day looking?"]:
            self.assertTrue(catchup.is_catchup(q), q)

    def test_no(self):
        for q in ["what's due today", "what's on my calendar today", "what did Felix ask me",
                  "what is the capital of Peru", "my birthday is in May"]:
            self.assertFalse(catchup.is_catchup(q), q)


class Answers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for e in ENTRIES:
            store.write_entry(dict(e), self.root)
        p = mock.patch("llm.chat", side_effect=AssertionError("no model call"), create=True)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def ask(self, q, events=None):
        cal = events or (lambda s, e: [x for x in EVENTS if s <= x["start"].date() <= e])
        return answer(q, SUN, root=self.root, _events=cal, _now=datetime(2026, 11, 15, 8, 0),
                      _online=lambda: self.fail("no network check"))

    @mock.patch.dict("os.environ", {"FLUX_MODE": "demo", "FLUX_CALENDAR": ""})
    def test_three_sections_in_order(self):
        a = self.ask("Catch me up")
        self.assertEqual(a.route, "catchup")
        t = a.text
        i_cal, i_due, i_ask = (t.index("Today on your calendar (Sun Nov 15):"),
                               t.index("Due today through Tue Nov 17:"),
                               t.index("Asks in mail from the last 7 days:"))
        self.assertLess(i_cal, i_due)
        self.assertLess(i_due, i_ask)
        self.assertIn("- noon–1:30pm  Hackathon judging (Duffield Atrium)", t)
        self.assertIn("Source: Apple Calendar (Flux demo)", t)
        self.assertIn("- Sun Nov 15 11:59pm  Problem set 7 is posted (ZOOL 2150, Nov 10)", t)
        self.assertIn("- Tue Nov 17 noon  Send me your $35 share (Felix Ambrose, Nov 14)", t)
        self.assertNotIn("Turn in the essay (Prof", t)          # due Nov 20: outside the 3 days
        self.assertIn("Source: saved mail and Canvas", t)
        self.assertIn("- Nov 14  Felix Ambrose: Send me your $35 share", t)
        self.assertIn("- Nov 12  Hugo Sato: Reply with your vote", t)
        self.assertNotIn("Do the old thing", t)                 # sent Nov 1: older than 7 days
        self.assertTrue(t.endswith("Source: email received in the last 7 days"))
        self.assertLess(t.index("Felix Ambrose: Send"), t.index("Hugo Sato: Reply"))  # newest first

    def test_calendar_error_keeps_other_sections(self):
        def broken(s, e):
            raise applecal.CalendarError("no permission to control Calendar")
        a = self.ask("what's my day", broken)
        self.assertTrue(a.text.startswith("Calendar: I couldn't read Apple Calendar (no permission"))
        self.assertIn("Due today through Tue Nov 17:", a.text)
        self.assertIn("Asks in mail from the last 7 days:", a.text)

    def test_empty_sections(self):
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        a = answer("brief me", SUN, root=empty, _events=lambda s, e: [], _now=datetime(2026, 11, 15, 8, 0))
        self.assertIn("- Nothing on your calendar today.", a.text)
        self.assertIn("- Nothing due in the next 3 days.", a.text)
        self.assertIn("- No asks in mail from the last 7 days.", a.text)

    def test_ask_limit(self):
        for i in range(10):
            store.write_entry(E(f"d0000000000{i}", f"Sender{i}", "2026-11-15", f"s{i}", "b",
                                ask=f"Ask number {i}"), self.root)
        a = self.ask("catch me up")
        self.assertIn("- …and 5 more.", a.text)

    def test_other_routes_unchanged(self):
        self.assertEqual(self.ask("what's due tomorrow").route, "due")
        self.assertEqual(self.ask("what's on my calendar today").route, "calendar")


if __name__ == "__main__":
    unittest.main()
