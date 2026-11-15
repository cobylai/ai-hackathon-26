"""Calendar route tests with the events source mocked: no Calendar access, no model.

    uv run python -m unittest discover reason/tests
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import applecal
from reason import answer, route

SAT = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 12, 0)

EVENTS = [
    {"title": "Brunch with Ivy", "start": datetime(2026, 11, 14, 10, 0),
     "end": datetime(2026, 11, 14, 11, 0), "location": "Collegetown Bagels", "all_day": False},
    {"title": "Hackathon demo", "start": datetime(2026, 11, 15, 12, 0),
     "end": datetime(2026, 11, 15, 13, 30), "location": "Duffield Atrium", "all_day": False},
    {"title": "Team standup", "start": datetime(2026, 11, 16, 9, 30),
     "end": datetime(2026, 11, 16, 10, 0), "location": "", "all_day": False},
    {"title": "Thanksgiving break", "start": datetime(2026, 11, 25, 0, 0),
     "end": datetime(2026, 11, 26, 0, 0), "location": "", "all_day": True},
]


class FakeCal:
    def __init__(self, evs=EVENTS):
        self.evs, self.calls = evs, []

    def __call__(self, start, end):
        self.calls.append((start, end))
        return [e for e in self.evs if start <= e["start"].date() <= end]


class Routing(unittest.TestCase):
    def test_calendar_questions(self):
        for q in ["what's on my calendar tomorrow", "When is my next meeting?",
                  "what do I have this week", "What's my schedule today", "am I free Monday",
                  "when is the next event", "do I have any appointments next week"]:
            self.assertTrue(route.is_calendar(q), q)

    def test_not_calendar(self):
        for q in ["what is due Monday", "what did Emily say about the meeting",
                  "what events is the club hosting", "is the gym open on Thanksgiving",
                  "what is the capital of Peru", "will it rain"]:
            self.assertFalse(route.is_calendar(q) and not route.is_due(q), q)

    def test_next_event(self):
        self.assertTrue(route.is_next_event("when is my next meeting"))
        self.assertFalse(route.is_next_event("what's on my calendar next week"))


class Answers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.no_model = mock.patch("llm.chat", side_effect=AssertionError("no model call"),
                                   create=True)
        self.no_model.start()

    def tearDown(self):
        self.no_model.stop()
        self.tmp.cleanup()

    def ask(self, q, cal=None):
        cal = cal or FakeCal()
        a = answer(q, SAT, root=self.root, _events=cal, _now=NOW,
                   _online=lambda: self.fail("no network check"))
        return a, cal

    @mock.patch.dict("os.environ", {"FLUX_MODE": "demo", "FLUX_CALENDAR": ""})
    def test_tomorrow(self):
        a, cal = self.ask("what's on my calendar tomorrow")
        self.assertEqual(a.route, "calendar")
        self.assertEqual(cal.calls, [(date(2026, 11, 15), date(2026, 11, 15))])
        self.assertIn("On your calendar Sun Nov 15:", a.text)
        self.assertIn("- noon–1:30pm  Hackathon demo (Duffield Atrium)", a.text)
        self.assertTrue(a.text.endswith("Source: Apple Calendar (Flux demo)"))

    def test_this_week_on_saturday_runs_to_next_sunday(self):
        a, cal = self.ask("what do I have this week")
        self.assertEqual(cal.calls, [(SAT, date(2026, 11, 22))])
        self.assertIn("(Nov 14 to Nov 22)", a.text)
        self.assertIn("- Sat Nov 14 10am–11am  Brunch with Ivy (Collegetown Bagels)", a.text)
        self.assertIn("- Mon Nov 16 9:30am–10am  Team standup", a.text)

    def test_next_week_all_day(self):
        a, cal = self.ask("what's on my schedule next week")
        self.assertEqual(cal.calls, [(date(2026, 11, 16), date(2026, 11, 22))])
        a, _ = self.ask("anything on my calendar on Nov 25")
        self.assertIn("all day  Thanksgiving break", a.text)

    def test_weekday(self):
        _, cal = self.ask("am I free Monday")
        self.assertEqual(cal.calls, [(date(2026, 11, 16), date(2026, 11, 16))])

    def test_next_meeting_skips_past_events(self):
        a, _ = self.ask("when is my next meeting")
        self.assertEqual(a.route, "calendar")
        self.assertIn("Your next event:\n- Sun Nov 15 noon–1:30pm  Hackathon demo", a.text)

    def test_nothing(self):
        a, _ = self.ask("what's on my calendar tomorrow", FakeCal([]))
        self.assertIn("Nothing on your calendar Sun Nov 15.", a.text)
        a, _ = self.ask("when is my next meeting", FakeCal([]))
        self.assertIn("Nothing coming up", a.text)

    def test_calendar_error(self):
        def broken(start, end):
            raise applecal.CalendarError('no calendar named "Flux demo" in Calendar.app')
        a, _ = self.ask("what's on my calendar today", broken)
        self.assertEqual(a.route, "calendar")
        self.assertIn("I couldn't read Apple Calendar (no calendar named", a.text)

    def test_due_still_wins(self):
        a, cal = self.ask("what's due on my calendar this week")
        self.assertEqual(a.route, "due")
        self.assertEqual(cal.calls, [])


if __name__ == "__main__":
    unittest.main()


class RealCalendars(unittest.TestCase):
    """FLUX_CALENDARS=all: answers name the calendar; demo mode wording is unchanged."""
    EVS = [dict(EVENTS[2], calendar="Work"),
           {"title": "Dinner", "start": datetime(2026, 11, 16, 18, 0), "end": datetime(2026, 11, 16, 19, 0),
            "location": "", "all_day": False, "calendar": "Home"}]

    def ask(self, mode, flux_mode=None):
        env = {"FLUX_CALENDARS": mode}
        if flux_mode:  # the calendar's name comes from the mode (bank/mode.py); live has none by default
            env["FLUX_MODE"] = flux_mode
        with mock.patch.dict("os.environ", env):
            return __import__("reason.answer", fromlist=["x"])._calendar("what do I have Monday", SAT, NOW, FakeCal(self.EVS))

    def test_all_mode_cites_calendars(self):
        a = self.ask("all")
        self.assertIn("Team standup [Work]", a.text)
        self.assertIn("Dinner [Home]", a.text)
        self.assertIn("Source: Apple Calendar (Home, Work)", a.text)

    def test_demo_mode_source_line_unchanged(self):
        a = self.ask("demo", flux_mode="demo")
        self.assertIn("Source: Apple Calendar (Flux demo)", a.text)
