"""applecal tests with osascript mocked: no Calendar access needed.

    uv run python -m unittest discover applecal/tests
"""
from __future__ import annotations

import subprocess
import unittest
from datetime import date, datetime
from unittest import mock

import applecal

US, RS = "\x1f", "\x1e"
OUT = (f"Standup{US}2026-11-16T09:30{US}2026-11-16T10:00{US}Room 204{US}false{RS}"
       f"Demo day{US}2026-11-15T00:00{US}2026-11-16T00:00{US}{US}true{RS}\n")


def _run(stdout="", stderr="", code=0):
    return mock.patch("applecal.subprocess.run",
                      return_value=subprocess.CompletedProcess([], code, stdout, stderr))


class Parse(unittest.TestCase):
    def test_fields_and_order(self):
        evs = applecal.parse(OUT)
        self.assertEqual([e["title"] for e in evs], ["Demo day", "Standup"])
        self.assertEqual(evs[1]["start"], datetime(2026, 11, 16, 9, 30))
        self.assertEqual(evs[1]["location"], "Room 204")
        self.assertTrue(evs[0]["all_day"])
        self.assertFalse(evs[1]["all_day"])

    def test_empty(self):
        self.assertEqual(applecal.parse(""), [])
        self.assertEqual(applecal.parse("\n"), [])


class Events(unittest.TestCase):
    def test_args_end_is_exclusive_next_day(self):
        with _run(OUT) as run:
            evs = applecal.events(date(2026, 11, 15), date(2026, 11, 30), calendar="X")
        argv = run.call_args.args[0]
        self.assertEqual(argv[:2], ["osascript", "-"])
        self.assertEqual(argv[2:], ["X", "2026", "11", "15", "2026", "12", "1"])
        self.assertEqual(len(evs), 2)

    def test_calendar_name_env(self):
        with mock.patch.dict("os.environ", {"MUSE_CALENDAR": "Hearth"}):
            self.assertEqual(applecal.calendar_name(), "Hearth")
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(applecal.calendar_name(), "Muse demo")

    def test_missing_calendar(self):
        with _run(stderr="execution error: no calendar named Muse demo (4040)", code=1):
            with self.assertRaisesRegex(applecal.CalendarError, "no calendar named"):
                applecal.events(date(2026, 11, 15), date(2026, 11, 15))

    def test_no_permission(self):
        with _run(stderr="execution error: Not authorized to send Apple events to Calendar. (-1743)",
                  code=1):
            with self.assertRaisesRegex(applecal.CalendarError, "Automation"):
                applecal.events(date(2026, 11, 15), date(2026, 11, 15))

    def test_timeout(self):
        with mock.patch("applecal.subprocess.run", side_effect=subprocess.TimeoutExpired("osascript", 20)):
            with self.assertRaises(applecal.CalendarError):
                applecal.events(date(2026, 11, 15), date(2026, 11, 15))


if __name__ == "__main__":
    unittest.main()
