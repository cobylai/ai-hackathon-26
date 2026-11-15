"""EventKit reader tests with the helper mocked: fake events only, offline, no Calendar access.

    uv run python -m unittest discover applecal/tests
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import applecal
from applecal import real, write


def ts(y, mo, d, h=0, mi=0):
    return datetime(y, mo, d, h, mi).timestamp()


def rec(cal, title, start, end, kind="caldav", all_day=False, loc=""):
    return {"calendar": cal, "type": kind, "title": title, "location": loc,
            "start": start, "end": end, "all_day": all_day}


PAYLOAD = {"status": "ok", "calendars": [], "events": [
    rec("Work", "Standup", ts(2026, 11, 16, 9, 30), ts(2026, 11, 16, 10)),
    rec("Work", "Standup", ts(2026, 11, 17, 9, 30), ts(2026, 11, 17, 10)),   # 2nd occurrence
    rec("Home", "Dinner", ts(2026, 11, 16, 18), ts(2026, 11, 16, 19, 30), loc="Ivy's"),
    rec("US Holidays", "Fake holiday", ts(2026, 11, 16), ts(2026, 11, 16, 23, 59), "subscription", True),
    rec("Birthdays", "Someone", ts(2026, 11, 16), ts(2026, 11, 16, 23, 59), "birthday", True),
    rec("Home", "Trip", ts(2026, 11, 18), ts(2026, 11, 19) + 86399, "caldav", True),
]}


class Base(unittest.TestCase):
    def setUp(self):
        real._CACHE.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"FLUX_CALENDARS": "all", "FLUX_HOME": self.tmp.name,
                                           "FLUX_CALENDARS_CONFIG": str(Path(self.tmp.name) / "c.json")})
        env.start()
        self.addCleanup(env.stop)

    def cfg(self, d):
        Path(self.tmp.name, "c.json").write_text(json.dumps(d))

    def read(self, a, b, payload=PAYLOAD):
        with mock.patch.object(real, "run_helper", return_value=payload):
            return applecal.events(a, b)


class Filtering(Base):
    def test_default_skips_holiday_and_birthday_keeps_all_others(self):
        evs = self.read(date(2026, 11, 16), date(2026, 11, 19))
        self.assertEqual({e["calendar"] for e in evs}, {"Work", "Home"})
        self.assertEqual(len(evs), 4)

    def test_recurring_occurrences_all_returned(self):
        evs = self.read(date(2026, 11, 16), date(2026, 11, 17))
        self.assertEqual([e["title"] for e in evs if e["title"] == "Standup"], ["Standup"] * 2)

    def test_allow_list_includes_even_subscribed(self):
        self.cfg({"allow": ["us holidays"]})
        evs = self.read(date(2026, 11, 16), date(2026, 11, 16))
        self.assertEqual([e["title"] for e in evs], ["Fake holiday"])

    def test_deny_beats_allow_and_default(self):
        self.cfg({"allow": ["Work", "Home"], "deny": ["home"]})
        evs = self.read(date(2026, 11, 16), date(2026, 11, 19))
        self.assertEqual({e["calendar"] for e in evs}, {"Work"})

    def test_opt_in_subscribed_and_birthdays(self):
        self.cfg({"include_subscribed": True, "include_birthdays": True})
        evs = self.read(date(2026, 11, 16), date(2026, 11, 16))
        self.assertEqual({e["calendar"] for e in evs}, {"Work", "Home", "US Holidays", "Birthdays"})

    def test_bad_config_falls_back_to_defaults(self):
        Path(self.tmp.name, "c.json").write_text("{not json")
        self.assertEqual(len(self.read(date(2026, 11, 16), date(2026, 11, 19))), 4)


class Convert(Base):
    def test_all_day_runs_to_next_midnight_and_multi_day(self):
        evs = self.read(date(2026, 11, 18), date(2026, 11, 19))
        trip = evs[0]
        self.assertTrue(trip["all_day"])
        self.assertEqual(trip["start"], datetime(2026, 11, 18))
        self.assertEqual(trip["end"], datetime(2026, 11, 20))

    def test_all_day_overlaps_each_day_of_window_only(self):
        self.assertEqual(self.read(date(2026, 11, 20), date(2026, 11, 20)), [])

    def test_timezone_instant_shown_in_local_time(self):
        # 14:00 UTC is an absolute instant; it is shown in this Mac's zone, not as 14:00.
        t = datetime(2026, 11, 16, 14, 0, tzinfo=__import__("datetime").timezone.utc).timestamp()
        e = real.convert(rec("Work", "Call", t, t + 3600))
        self.assertEqual(e["start"], datetime.fromtimestamp(t))
        self.assertIsNone(e["start"].tzinfo)

    def test_window_passed_as_local_midnights(self):
        with mock.patch.object(real, "run_helper", return_value=PAYLOAD) as rh:
            applecal.events(date(2026, 11, 16), date(2026, 11, 16))
        lo, hi = rh.call_args.args
        self.assertEqual((lo, hi), (datetime(2026, 11, 16), datetime(2026, 11, 17)))


class Errors(Base):
    def test_denied_is_a_calendar_error_with_instructions(self):
        with self.assertRaises(applecal.CalendarError) as c:
            self.read(date(2026, 11, 16), date(2026, 11, 16), {"status": "denied", "events": []})
        self.assertIn("Calendars", str(c.exception))

    def test_helper_failure_is_a_calendar_error(self):
        with mock.patch.object(real, "run_helper", side_effect=OSError("boom")):
            with self.assertRaises(applecal.CalendarError):
                applecal.events(date(2026, 11, 16), date(2026, 11, 16))


class Modes(unittest.TestCase):
    def test_default_is_demo_and_uses_osascript_not_eventkit(self):
        # demo mode names the calendar (bank/mode.py); live mode names yours, so pin the mode here
        with mock.patch.dict(os.environ, {"FLUX_MODE": "demo"}, clear=False):
            os.environ.pop("FLUX_CALENDARS", None)
            self.assertFalse(applecal.read_all())
            self.assertEqual(applecal.source_label(), "Flux demo")
            with mock.patch.object(real, "read") as r, mock.patch.object(applecal, "_fetch", return_value=[]):
                applecal.events(date(2026, 11, 16), date(2026, 11, 16))
            r.assert_not_called()

    def test_source_label_names_calendars_of_shown_events(self):
        with mock.patch.dict(os.environ, {"FLUX_CALENDARS": "all"}):
            self.assertEqual(applecal.source_label([{"calendar": "Work"}, {"calendar": "Home"}, {"calendar": "Work"}]),
                             "Home, Work")
            self.assertEqual(applecal.source_label([]), "all calendars")


class WritesStayOnDemo(unittest.TestCase):
    def test_add_event_refuses_other_calendar_in_all_mode(self):
        with mock.patch.dict(os.environ, {"FLUX_CALENDARS": "all"}), mock.patch.object(write, "_run") as run:
            with self.assertRaises(applecal.CalendarError):
                write.add_event("x", datetime(2026, 11, 16, 9), datetime(2026, 11, 16, 10), calendar="Work")
            run.assert_not_called()
            write.add_event("x", datetime(2026, 11, 16, 9), datetime(2026, 11, 16, 10))
            self.assertEqual(run.call_args.args[1][0], "Flux demo")


if __name__ == "__main__":
    unittest.main()
