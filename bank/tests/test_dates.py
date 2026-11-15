import unittest
from datetime import date

from bank.dates import resolve

MON9, WED11, THU12, FRI13 = date(2026, 11, 9), date(2026, 11, 11), date(2026, 11, 12), date(2026, 11, 13)
D = lambda s: date.fromisoformat(s)  # noqa: E731


class TestResolve(unittest.TestCase):
    def check(self, phrase, sent, want_date, want_time=None, prev=None):
        d, t = resolve(phrase, sent, prev)
        self.assertEqual(d, D(want_date) if want_date else None, phrase)
        self.assertEqual(t, want_time, phrase)

    def test_today_words(self):
        for p in ("today", "tonight", "this afternoon", "end of day", "EOD"):
            self.check(p, THU12, "2026-11-12")

    def test_tomorrow(self):
        self.check("tomorrow morning", THU12, "2026-11-13")
        self.check("tomorrow", date(2026, 12, 31), "2027-01-01")

    def test_weekday(self):
        self.check("Friday at 5pm", MON9, "2026-11-13", "17:00")
        self.check("by 5pm Friday", MON9, "2026-11-13", "17:00")
        self.check("before Tuesday", WED11, "2026-11-17")
        self.check("Monday 11:59pm", THU12, "2026-11-16", "23:59")
        self.check("Thursday at noon", date(2026, 11, 10), "2026-11-12", "12:00")
        self.check("this Friday", WED11, "2026-11-13")

    def test_same_weekday_is_a_week_later(self):
        self.check("by Friday", FRI13, "2026-11-20")

    def test_next_weekday(self):
        self.check("next Friday", MON9, "2026-11-20")
        self.check("next Monday", WED11, "2026-11-16")
        self.check("next Monday", date(2026, 11, 15), "2026-11-16")  # Sunday -> next day

    def test_weekday_after_previous(self):
        self.check("the Friday after", FRI13, "2026-11-20", prev=D("2026-11-18"))
        self.check("the Friday after", MON9, "2026-11-13")

    def test_end_of_week_and_next_week(self):
        self.check("end of the week", MON9, "2026-11-13")
        self.check("end of week", FRI13, "2026-11-13")
        self.check("next week", WED11, "2026-11-16")

    def test_explicit_dates(self):
        self.check("Nov 20", MON9, "2026-11-20")
        self.check("November 20th at 11:59pm", MON9, "2026-11-20", "23:59")
        self.check("20 Nov", MON9, "2026-11-20")
        self.check("11/20", MON9, "2026-11-20")
        self.check("2026-11-20", MON9, "2026-11-20")
        self.check("Jan 5", D("2026-12-10"), "2027-01-05")  # rolls to next year
        self.check("Oct 30", MON9, "2026-10-30")            # recent past stays this year

    def test_day_of_month(self):
        self.check("by 5:00pm on the 25th", WED11, "2026-11-25", "17:00")
        self.check("the 3rd", WED11, "2026-12-03")

    def test_in_n(self):
        self.check("in 3 days", MON9, "2026-11-12")
        self.check("in 2 weeks", MON9, "2026-11-23")

    def test_midnight(self):
        self.check("Sunday at midnight", FRI13, "2026-11-15", "23:59")

    def test_find_phrases_in_ask(self):
        from bank.dates import find_phrases
        self.assertEqual(find_phrases("start the writeup tomorrow morning"), ["tomorrow morning"])
        self.assertEqual(find_phrases("push it by Friday at 5pm please"), ["by Friday at 5pm"])
        self.assertEqual(find_phrases("Submit the notebook"), [])
        self.assertEqual(find_phrases("monitor the mon"), [])

    def test_unresolvable(self):
        self.check("soon", MON9, None)
        self.check("when you get a chance", MON9, None)
        self.check("ASAP", MON9, None)


if __name__ == "__main__":
    unittest.main()
