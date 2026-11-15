"""remember / forget / about_me / people routes. No model (a model call fails the test), no network."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import bank
from bank import people, store
from reason import answer, route

DAY = date(2026, 11, 14)


def email(id_, name, sent, subject, deadlines=None):
    return {"id": id_, "kind": "email", "folder": "person", "source": f"t:{id_}", "sender_name": name,
            "sender_address": f"{name.split()[0].lower()}@x.example", "sent_date": sent, "subject": subject,
            "ask": "Do the thing.", "deadlines": deadlines or [], "course": None, "topic": None,
            "ingested_at": "2026-11-14T00:00:00", "body": f"About {subject}."}


def no_model(*a, **k):
    raise AssertionError("model called")


@mock.patch("llm.client.complete_json", no_model)
@mock.patch("llm.client.complete", no_model)
@mock.patch("llm.client.chat", no_model)
class Routes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        store.write_entry(email("p00000000001", "Felix Ambrose", "2026-11-13", "Pay your share",
                                [{"phrase": "Monday", "date": "2026-11-16", "time": None}]), self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def ask(self, q):
        return answer(q, today=DAY, root=self.root, _online=lambda: False)

    def test_remember_list_forget(self):
        a = self.ask("Remember that my lab is Tuesdays at 2.")
        self.assertEqual((a.route, a.text), ("remember", "Got it. I'll remember: my lab is Tuesdays at 2."))
        self.assertEqual(self.ask("remember that my lab is Tuesdays at 2").text,
                         "I already have that: my lab is Tuesdays at 2.")
        a = self.ask("What do you know about me?")
        self.assertEqual((a.route, a.text), ("about_me", "Here's what you've told me:\n"
                                             "- Nov 14  my lab is Tuesdays at 2\nSource: your notes"))
        a = self.ask("Forget that my lab is Tuesdays at 2")
        self.assertEqual((a.route, a.text), ("forget", "Forgotten: my lab is Tuesdays at 2."))
        self.assertEqual(self.ask("what do you know about me").text,
                         'Nothing yet. Say "remember that …" to tell me something.')

    def test_spoken_forms(self):
        for q in ("- Remember that I'm vegetarian.", "Flux, remember I'm vegetarian",
                  "please remember I'm vegetarian", "Don't forget that I'm vegetarian"):
            self.assertEqual(route.remember_text(q), "I'm vegetarian", q)

    def test_remember_beats_due(self):
        a = self.ask("Remember the essay is due Monday")
        self.assertEqual(a.route, "remember")
        self.assertEqual(bank.notes(root=self.root)[0]["body"], "the essay is due Monday")

    def test_not_a_remember(self):
        for q in ("do you remember my lab time", "Remember that thing Felix said?", "I remember nothing"):
            self.assertIsNone(route.remember_text(q), q)
        self.assertEqual(self.ask("Remember").text, "What should I remember?")

    def test_forget_forms(self):
        self.assertEqual(route.forget_text("forget that"), "")
        self.assertEqual(route.forget_text("Forget it."), "")
        self.assertEqual(route.forget_text("forget about the lab"), "the lab")
        self.assertIsNone(route.forget_text("don't forget the lab"))
        self.assertIsNone(route.forget_text("I always forget the lab"))

    def test_forget_tie_and_none(self):
        bank.remember("my lab is Tuesdays", root=self.root)
        bank.remember("my lab partner is Sam", root=self.root)
        a = self.ask("forget my lab")
        self.assertEqual(a.route, "forget")
        self.assertTrue(a.text.startswith("Which one?"))
        self.assertIn("my lab partner is Sam", a.text)
        self.assertEqual(len(bank.notes(root=self.root)), 2)
        self.assertEqual(self.ask("forget my bike code").text, "I don't have a note like that.")

    def test_note_source_label_in_bank_route(self):
        from importlib import import_module
        e = bank.remember("my lab is Tuesdays at 2", today=DAY, root=self.root)["entry"]
        self.assertEqual(import_module("reason.answer").source_label(e), "your note, Nov 14")

    def test_who_is_sender(self):
        a = self.ask("Who is Felix?")
        self.assertEqual(a.route, "people")
        self.assertEqual(a.text, "Felix Ambrose\nI don't know how you know them yet.\n"
                                 "Newest emails from them (1 of 1):\n- Nov 13  Pay your share\n"
                                 "Source: Felix Ambrose, Nov 13")

    def test_who_is_with_page(self):
        people.set_relation("Felix Ambrose", "cabin trip organizer", root=self.root)
        people.set_fact("Felix Ambrose", "collects the cabin money", root=self.root)
        a = self.ask("what do you know about Felix Ambrose")
        self.assertIn("How you know them: cabin trip organizer", a.text)
        self.assertIn("What I know about them:\n- collects the cabin money", a.text)
        self.assertIn("Source: people page for Felix Ambrose; Felix Ambrose, Nov 13", a.text)

    @mock.patch("reason.think._think", return_value=("I don't know.", False))
    def test_who_is_unknown_falls_through(self, _think):
        self.assertEqual(self.ask("Who is Zelda?").route, "general")
        a = self.ask("who is waiting on me")  # about the user, nothing saved
        self.assertEqual((a.route, a.text), ("reason", "I have nothing saved about that."))

    def test_person_route_unchanged(self):
        self.assertEqual(self.ask("What did Felix ask me?").route, "person")


if __name__ == "__main__":
    unittest.main()
