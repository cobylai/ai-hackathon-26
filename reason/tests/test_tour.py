"""What's Flux and the guided tour (reason/tour.py, playbooks/about.md): bank in a temp dir,
no model, no network. Most tests pass a fake run() so only the tour's own logic is checked.

    uv run python -m unittest discover reason/tests
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from bank import store
from reason import playbook, tour
from reason.answer import STEPS, Answer, answer
from reason.session import Session

SUN = date(2026, 11, 15)


def E(id_, name, sent, subject, ask=None, deadlines=None, folder="person"):
    return {"id": id_, "kind": "email", "folder": folder, "source": f"t:{id_}", "sender_name": name,
            "sender_address": f"{id_}@example.edu", "sent_date": sent, "subject": subject,
            "ask": ask, "deadlines": deadlines or [], "course": None, "topic": None,
            "ingested_at": "2026-11-15T00:00:00", "body": subject}


ENTRIES = [
    E("t00000000001", "Felix Ambrose", "2026-11-14", "cabin", ask="Send me your $35 share"),
    E("t00000000002", "Hugo Sato", "2026-11-12", "team name", ask="Reply with your vote",
      deadlines=[{"phrase": "Monday 5pm", "date": "2026-11-16", "time": "17:00"}]),
    E("t00000000003", "ZOOL 2150", "2026-11-10", "Problem set 7", folder="course",
      deadlines=[{"phrase": "Thu Nov 19", "date": "2026-11-19", "time": None}]),
]


class Fake:
    """Stands in for answer(): records each example question, answers it plainly."""
    def __init__(self):
        self.asked = []

    def __call__(self, q, today=None, root=None, session=None, _events=None):
        self.asked.append(q)
        return Answer(f"ANSWER to {q}\nSource: test", "x", [f"src:{q}"])


class Base(unittest.TestCase):
    entries = ENTRIES

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for e in self.entries:
            store.write_entry(dict(e), self.root)
        self.run_ = Fake()
        self.s = Session()

    def tearDown(self):
        self.tmp.cleanup()

    def ask(self, q):
        return tour.handle(q, SUN, self.root, session=self.s, run=self.run_)


class Overview(Base):
    def test_overview(self):
        for q in ["What's Flux?", "what is this", "What can you do?", "help", "How do I use this?",
                  "Flux, what's Flux?", "What is flock?", "what's flocks", "Flocks, what is Flux?"]:
            a = self.ask(q)
            self.assertIsNotNone(a, q)
            self.assertEqual(a.route, "about")
        a = self.ask("What is Flux?")
        self.assertTrue(a.text.startswith("I'm Flux, a personal assistant that lives on your Mac.\n"))
        self.assertIn("Try asking:", a.text)
        self.assertTrue(a.text.rstrip().splitlines()[-1].startswith("Source:"))
        qs = [c[1] for c in a.choices]
        # examples come from the routes' playbooks, kept when the bank has their name, else the bank's own
        self.assertIn("What did Felix ask me?", qs)            # Felix is a sender here: kept
        self.assertIn("Set me up for Problem set 7", qs)      # no "lab report" here: the bank's due item
        self.assertIn("- Remember that my lab is Tuesdays at 2\n", a.text)  # no closing full stop
        self.assertEqual(self.run_.asked, [])  # the overview runs nothing

    def test_whole_question_only(self):
        for q in ["help me draft a reply to Felix", "show me my calendar", "what's next week",
                  "skip the meeting?", "stop by the lab"]:
            self.assertIsNone(self.ask(q), q)


class Fixed(Base):
    def test_each_fixed_answer(self):
        for q, starts in [("Do you need the internet?", "No. I read your mail and coursework"),
                          ("How did you get my mail?", "Through my own hidden browser."),
                          ("What model are you running?", "Bonsai 2, the 4B model"),
                          ("Will you send that?", "No. I write the draft and you send it."),
                          ("Flux, what model are you running?", "Bonsai 2")]:
            a = self.ask(q)
            self.assertEqual(a.route, "about", q)
            self.assertTrue(a.text.startswith(starts), q)
            self.assertEqual(self.run_.asked, [])  # no route, no model

    def test_internet_says_whether_online(self):
        with mock.patch("reason.answer.online", return_value=False):
            self.assertIn("You're offline right now, and I still work.", self.ask("Do you need the internet?").text)
        with mock.patch("reason.answer.online", return_value=True):
            self.assertIn("I only go online to sync and to look things up.", self.ask("Do you need the internet?").text)

    def test_send_question_while_a_draft_waits(self):
        """Asked right after a draft, while compose or act waits: answered, and the hold is untouched."""
        from reason import act, compose
        with mock.patch.object(compose, "waiting", return_value=True), \
             mock.patch.object(act, "waiting", return_value=True), \
             mock.patch.object(act, "reset") as act_reset, mock.patch.object(compose, "reset") as comp_reset:
            a = answer("Will you send that?", today=SUN, root=self.root, session=self.s)
            self.assertEqual(a.route, "about")
            self.assertIn("I never send anything myself.", a.text)
            self.assertFalse(act_reset.called or comp_reset.called)
            self.assertIsNone(tour.handle("What is Flux?", SUN, self.root, session=self.s, held=True))  # waits

    def test_not_part_of_another_question(self):
        for q in ["will you send that to Felix tomorrow and also the other one?", "what model is the bike"]:
            self.assertIsNone(self.ask(q), q)


class Tour(Base):
    def test_walk_through(self):
        n = len(tour._steps())
        a = self.ask("show me")
        self.assertIn(f"1 of {n}: Catch me up", a.text)
        self.assertEqual(self.s.tour, 0)
        self.assertEqual([c[1] for c in a.choices], ["next", "stop"])
        self.assertEqual(self.run_.asked, [playbook.load("catchup").examples[0]["question"]])

        a = self.ask("next")  # due, then its follow-up, from followup.md
        self.assertIn(f"2 of {n}", a.text)
        fu = playbook.load("followup").examples
        self.assertEqual(self.run_.asked[-2:], [fu[0]["question"], fu[2]["question"]])

        a = self.ask("next")  # person, with the newest sender who asked something
        self.assertIn('Example: "What did Felix ask me?"', a.text)
        self.assertIn("ANSWER to What did Felix ask me?", a.text)

        before = len(self.run_.asked)
        a = self.ask("next")  # remember: shown, never run
        self.assertIn("Remember that my lab is Tuesdays at 2.", a.text)
        self.assertNotIn("Remember that my lab is Tuesdays at 2.", self.run_.asked[before:])

        with mock.patch("reason.act.reset") as act_reset, mock.patch("reason.compose.reset") as comp_reset:
            self.ask("next")   # suggestion + draft
            a = self.ask("next")  # set me up, with the nearest coursework due item
            self.assertTrue(act_reset.called and comp_reset.called)  # nothing left waiting for a yes
        self.assertIn('Example: "Set me up for Problem set 7"', a.text)

        self.ask("next"); a = self.ask("next")
        self.assertIn(f"{n} of {n}", a.text)
        self.assertEqual(a.choices, [["Done", "stop"]])
        a = self.ask("stop")
        self.assertIsNone(self.s.tour)
        self.assertIn("Tour ended", a.text)

    def test_back_skip_and_other_questions(self):
        self.ask("show me"); self.ask("next")
        self.assertEqual(self.s.tour, 1)
        self.assertIsNone(self.ask("what did Hugo ask me?"))  # answered as usual; the tour waits
        self.assertEqual(self.s.tour, 1)
        self.ask("skip")
        self.assertEqual(self.s.tour, 2)
        a = self.ask("back")
        self.assertEqual(self.s.tour, 1)
        self.assertIn("2 of", a.text)

    def test_next_without_a_tour(self):
        a = self.ask("next")
        self.assertIn("There's no tour going on", a.text)
        self.assertIsNone(self.s.tour)

    def test_resume_from_saved_chat(self):
        self.ask("show me"); self.ask("next"); self.ask("next")
        s2 = Session.from_dict(self.s.to_dict())
        self.assertEqual(s2.tour, 2)
        a = tour.handle("next", SUN, self.root, session=s2, run=self.run_)
        self.assertIn("4 of", a.text)


class EmptyBank(Base):
    entries = []

    def test_skips_steps_without_data(self):
        a = self.ask("show me")
        self.assertIn("Skipping \"Catch me up\"", a.text)
        self.assertIn("Skipping \"What's due\"", a.text)
        self.assertIn("Skipping \"What someone asked you\"", a.text)
        self.assertIn("4 of", a.text)  # remember needs no data
        self.assertEqual(self.s.tour, 3)
        a = self.ask("next")  # suggest and setup have nothing either: on to talking
        self.assertIn("Skipping \"A suggested task\"", a.text)
        self.assertIn("Skipping \"Set you up to work\"", a.text)
        self.assertIn("7 of", a.text)

    def test_overview_still_works(self):
        a = self.ask("What's Flux?")
        qs = [c[1] for c in a.choices]
        self.assertNotIn("What did Felix ask me?", qs)  # no staged names on an empty bank
        self.assertNotIn("Felix", a.text)
        self.assertIn("Catch me up", qs)


class Hook(Base):
    def test_answer_routes_to_the_tour(self):
        events = lambda a, b: []
        a = answer("What's Flux?", today=SUN, root=self.root, session=self.s, _events=events)
        self.assertEqual(a.route, "about")
        self.assertTrue(a.choices)
        a = answer("show me", today=SUN, root=self.root, session=self.s, _events=events)
        self.assertEqual((a.route, self.s.tour), ("about", 0))
        self.assertIn("Today on your calendar", a.text)  # the real catch-up ran
        a = answer("next", today=SUN, root=self.root, session=self.s, _events=events)
        self.assertEqual(self.s.tour, 1)
        self.assertIn("Reply with your vote", a.text)  # the real due route: Hugo's, Mon Nov 16
        a = answer("stop", today=SUN, root=self.root, session=self.s, _events=events)
        self.assertIsNone(self.s.tour)

    def test_playbook_steps(self):
        self.assertEqual(len(playbook.load("about").steps), STEPS["about"])


if __name__ == "__main__":
    unittest.main()
