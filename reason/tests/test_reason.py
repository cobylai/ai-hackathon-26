"""Reasoning layer tests: routing, date ranges, and each route with the model stubbed.

    python -m unittest discover -s reason/tests -t .
No model server and no network needed.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from bank import store
from reason import OFFLINE_TEXT, answer
from reason import route

WED = date(2026, 11, 11)  # a Wednesday
D = date.fromisoformat


def E(id_, folder, name, addr, sent, subject, body, ask=None, deadlines=None, kind="email",
      source=None):
    return {"id": id_, "kind": kind, "folder": folder, "source": source or f"t:{id_}",
            "sender_name": name, "sender_address": addr, "sent_date": sent, "subject": subject,
            "ask": ask, "deadlines": deadlines or [], "course": None, "topic": None,
            "ingested_at": "2026-11-14T00:00:00", "body": body}


ENTRIES = [
    E("a00000000001", "course", "Prof. Daniel Reyes", "dreyes@univ.example.edu", "2026-11-12",
      "ENGRD 2700 project extension", "The project deadline moved to Monday 11:59pm.",
      ask="Submit your final notebook and a one page reflection.",
      deadlines=[{"phrase": "Monday 11:59pm", "date": "2026-11-16", "time": "23:59"}]),
    E("a00000000002", "person", "Emily Carter", "ec455@univ.example.edu", "2026-11-10",
      "lab 6 notes", "Emily asked for the lab 6 notes before Tuesday.",
      ask="Send Emily your lab 6 notes.",
      deadlines=[{"phrase": "before Tuesday", "date": "2026-11-17", "time": None}]),
    E("a00000000003", "person", "Will Turner", "wt12@univ.example.edu", "2026-11-09",
      "climbing trip", "Will is organizing a climbing trip on Saturday.",
      ask="Reply to Will if you can come.",
      deadlines=[{"phrase": "tomorrow at 5pm", "date": "2026-11-10", "time": "17:00"}]),
    E("a00000000004", "other", "Campus Dining Office", "dining@univ.example.edu", "2026-11-08",
      "Thanksgiving hours", "Dining halls close at 2pm on Thanksgiving.", ask=None),
]


class Bank(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for e in ENTRIES:
            store.write_entry(dict(e), self.root)

    def tearDown(self):
        self.tmp.cleanup()


class DueRange(unittest.TestCase):
    def check(self, q, lo, hi, today=WED):
        s, e, _ = route.due_range(q, today)
        self.assertEqual((s, e), (D(lo), D(hi)), q)

    def test_table(self):
        self.check("what is due today", "2026-11-11", "2026-11-11")
        self.check("anything due tonight", "2026-11-11", "2026-11-11")
        self.check("anything due tomorrow", "2026-11-12", "2026-11-12")
        self.check("what is due Tuesday", "2026-11-17", "2026-11-17")
        self.check("what's due by friday", "2026-11-13", "2026-11-13")
        self.check("what is due Wednesday", "2026-11-11", "2026-11-11")  # today is Wednesday
        self.check("what is due next Friday", "2026-11-20", "2026-11-20")
        self.check("what's due this week", "2026-11-11", "2026-11-15")
        self.check("what's due this weekend", "2026-11-14", "2026-11-15")
        self.check("deadlines next week", "2026-11-16", "2026-11-22")
        self.check("what is due Nov 20", "2026-11-20", "2026-11-20")
        self.check("what is due November 20th", "2026-11-20", "2026-11-20")
        self.check("what is due 11/20", "2026-11-20", "2026-11-20")
        self.check("what is due 2026-11-20", "2026-11-20", "2026-11-20")
        self.check("what's due?", "2026-11-11", "2026-11-17")

    def test_this_week_on_weekend(self):
        self.check("what's due this week", "2026-11-14", "2026-11-22", today=D("2026-11-14"))  # Sat
        self.check("what's due this week", "2026-11-15", "2026-11-22", today=D("2026-11-15"))  # Sun

    def test_weekend_from_sunday(self):
        self.check("due this weekend", "2026-11-15", "2026-11-15", today=D("2026-11-15"))

    def test_label_open_range(self):
        self.assertEqual(route.due_range("what's due", WED)[2], "in the next 7 days")


class Routing(unittest.TestCase):
    NAMES = (route.name_words("Emily Carter", "ec455@x.edu") | route.name_words("Will Turner", "wt12@x.edu")
             | route.name_words("Prof. Daniel Reyes", "dreyes@x.edu"))

    def test_due_words(self):
        self.assertTrue(route.is_due("anything due tomorrow"))
        self.assertTrue(route.is_due("any deadlines this week?"))
        self.assertFalse(route.is_due("what did Emily ask me"))

    def test_person(self):
        self.assertEqual(route.person_in("what did Emily ask me", self.NAMES), "emily")
        self.assertEqual(route.person_in("what did emily ask", self.NAMES), "emily")
        self.assertEqual(route.person_in("What did Reyes say?", self.NAMES), "reyes")
        self.assertEqual(route.person_in("Emily's email", self.NAMES), "emily")
        self.assertEqual(route.person_in("what did Will say", self.NAMES), "will")

    def test_common_words(self):
        self.assertIsNone(route.person_in("will it rain", self.NAMES))
        self.assertIsNone(route.person_in("Will it rain in Ithaca?", self.NAMES))
        self.assertIsNone(route.person_in("when do dining halls close", self.NAMES))

    def test_titles_and_automated(self):
        self.assertNotIn("prof", self.NAMES)
        self.assertEqual(route.name_words("Campus Dining Office", "dining@univ.edu"), set())
        self.assertEqual(route.name_words(None, "noreply@x.edu"), set())


class DueRoute(Bank):
    def test_one_day(self):
        with mock.patch("llm.client.chat", side_effect=AssertionError("no model on due")):
            a = answer("what is due Tuesday", today=WED, root=self.root)
        self.assertEqual(a.route, "due")
        self.assertIn("Due Tue Nov 17:", a.text)
        self.assertIn("Send Emily your lab 6 notes (Emily Carter, Nov 10)", a.text)
        self.assertEqual(len(a.sources), 1)

    def test_week(self):
        a = answer("what's due next week", today=WED, root=self.root)
        self.assertEqual(a.route, "due")
        lines = a.text.splitlines()
        self.assertTrue(lines[0].startswith("Due next week (Nov 16 to Nov 22)"))
        self.assertIn("Mon Nov 16 11:59pm  Submit your final notebook", lines[1])
        self.assertIn("(Prof. Daniel Reyes, Nov 12)", lines[1])
        self.assertEqual(lines[2], "    The project deadline moved to Monday 11:59pm.")  # summary row
        self.assertIn("Tue Nov 17", lines[3])

    def test_empty(self):
        a = answer("anything due tomorrow", today=WED, root=self.root)
        self.assertEqual(a.text, "Nothing due Thu Nov 12 in your saved mail.")


class PersonRoute(Bank):
    def test_answers_from_entries(self):
        seen = {}

        def fake(prompt, **kw):
            seen["prompt"] = prompt
            return {"answer": "She asked for your lab 6 notes before Tuesday.", "used": [1]}

        with mock.patch("llm.client.complete_json", side_effect=fake):
            a = answer("what did Emily say about the lab", today=WED, root=self.root)
        self.assertEqual(a.route, "person")
        self.assertIn("lab 6 notes", seen["prompt"])
        self.assertNotIn("Reyes", seen["prompt"])  # only Emily's entries go to the model
        self.assertTrue(a.text.endswith("Source: Emily Carter, Nov 10"))
        self.assertEqual(len(a.sources), 1)

    def test_ask_question_listed_by_code(self):
        with mock.patch("llm.client.complete_json", side_effect=AssertionError("no model")):
            a = answer("what did Emily ask me", today=WED, root=self.root)
            b = answer("What does Will want?", today=WED, root=self.root)
        self.assertEqual(a.route, "person")
        self.assertEqual(a.text, "From Emily Carter:\n- Nov 10  lab 6 notes: Send Emily your lab 6 notes.\n"
                                 "Source: Emily Carter, Nov 10")
        self.assertIn("Reply to Will if you can come.", b.text)

    def test_ask_question_no_ask_shows_summary(self):
        store.write_entry(E("a00000000005", "person", "Ivy Marlow", "im@x.edu", "2026-11-11", "garden news",
                            "The garden club planted tulips.", ask=None), self.root)
        with mock.patch("llm.client.complete_json", side_effect=AssertionError("no model")):
            a = answer("what did Ivy ask me", today=WED, root=self.root)
        self.assertIn("garden news: no ask. The garden club planted tulips.", a.text)

    def test_unknown_person_stops(self):
        with mock.patch("sufficiency.judge", side_effect=AssertionError("must not search")), \
             mock.patch("llm.client.complete_json", side_effect=AssertionError("no model")):
            a = answer("What did Priya ask me?", today=WED, root=self.root, _online=lambda: True)
        self.assertEqual((a.route, a.text, a.sources), ("person", "I have nothing from Priya.", []))
        self.assertIsNone(route.asked_name("what did you send them"))

    def test_bad_used_falls_back_to_all(self):
        with mock.patch("llm.client.complete_json", return_value={"answer": "x", "used": ["z", 9]}):
            a = answer("what did emily say", today=WED, root=self.root)
        self.assertEqual(len(a.sources), 1)  # Emily has one entry
        self.assertIn("Source: Emily Carter", a.text)


def verdict(enough, answer=None, evidence=None):
    return SimpleNamespace(enough=enough, answer=answer, evidence=evidence)


class SearchRoute(Bank):
    def test_bank_answers(self):
        v = verdict(True, "2pm", "Dining halls close at 2pm on Thanksgiving.")
        with mock.patch("sufficiency.judge", return_value=v) as j:
            a = answer("when do dining halls close on Thanksgiving", today=WED, root=self.root,
                       _online=lambda: self.fail("no network check when the bank answers"))
        self.assertEqual(a.route, "bank")
        self.assertIn("Dining halls close at 2pm", j.call_args.args[1])
        self.assertEqual(a.text, "2pm\nSource: Campus Dining Office, Nov 8")

    def test_offline_message(self):
        with mock.patch("sufficiency.judge", return_value=verdict(False)):
            a = answer("when do dining halls close on Thanksgiving", today=WED, root=self.root,
                       _online=lambda: False)
        self.assertEqual((a.route, a.text), ("offline", OFFLINE_TEXT))

    def test_no_bank_hits_offline_skips_judge(self):
        with mock.patch("sufficiency.judge", side_effect=AssertionError("no judge")):
            a = answer("what is the capital of Peru", today=WED, root=self.root,
                       _online=lambda: False)
        self.assertEqual(a.route, "offline")

    def test_web_route_ingests_page(self):
        page = "Lima is the capital of Peru."
        gr = SimpleNamespace(found=True, answer="Lima", evidence="Lima is the capital of Peru.",
                             source=SimpleNamespace(url="https://example.org/peru"),
                             opened=["https://example.org/peru"], message="")
        ingested = {}

        def fake_ingest(text, source, kind, subject=None, root=None):
            ingested.update(text=text, source=source, kind=kind, subject=subject)
            return {"status": "added"}

        with mock.patch("sufficiency.gather", return_value=gr):
            a = answer("what is the capital of Peru", today=WED, root=self.root,
                       _online=lambda: True,
                       _web_fns={"search_fn": lambda q: [], "open_fn": lambda u: ("OK", page),
                                 "ingest_fn": fake_ingest})
        self.assertEqual(a.route, "web")
        self.assertEqual(a.sources, ["https://example.org/peru"])
        self.assertIn("Source: https://example.org/peru", a.text)
        self.assertEqual((ingested["source"], ingested["kind"]), ("https://example.org/peru", "page"))
        self.assertIn("Answer: Lima", ingested["text"])
        self.assertIn('"Lima is the capital of Peru."', ingested["text"])
        self.assertEqual(ingested["subject"], "what is the capital of Peru Lima")
        self.assertEqual(a.text.count('"Lima is the capital of Peru."'), 1)

    def test_web_bot_check_answer_not_filed(self):
        gr = SimpleNamespace(found=True, answer="Prove your humanity",
                             evidence="Prove your humanity",
                             source=SimpleNamespace(url="https://www.reddit.com/r/x"),
                             opened=["https://www.reddit.com/r/x"], message="")
        ingest = mock.Mock(side_effect=AssertionError("must not file a bot-check page"))
        with mock.patch("sufficiency.gather", return_value=gr):
            # "what did everyone ask me" is the person route now, so a factual question here
            a = answer("who wrote the novel Frankenstein?", today=WED, root=self.root,
                       _online=lambda: True,
                       _web_fns={"search_fn": lambda q: [], "open_fn": lambda u: ("OK", ""),
                                 "ingest_fn": ingest})
        self.assertEqual(a.route, "not_found")
        self.assertNotIn("humanity", a.text)
        ingest.assert_not_called()

    def test_web_not_found(self):
        gr = SimpleNamespace(found=False, answer=None, evidence=None, source=None,
                             opened=[], message="No page answered it.")
        with mock.patch("sufficiency.gather", return_value=gr):
            a = answer("what is the capital of Peru", today=WED, root=self.root,
                       _online=lambda: True,
                       _web_fns={"search_fn": lambda q: [], "open_fn": lambda u: ("ERR", "")})
        self.assertEqual((a.route, a.text), ("not_found", "No page answered it."))


class Offline(unittest.TestCase):
    def test_due_route_imports_no_harness(self):
        import subprocess
        import sys
        code = ("import sys, tempfile; from reason import answer; "
                "a = answer('what is due today', root=__import__('pathlib').Path(tempfile.mkdtemp())); "
                "print(a.route, 'harness' in sys.modules, 'playwright' in sys.modules)")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                             cwd=Path(__file__).resolve().parents[2])
        self.assertEqual(out.stdout.split(), ["due", "False", "False"], out.stderr)


if __name__ == "__main__":
    unittest.main()
