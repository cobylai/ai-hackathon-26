"""Test report problem 8: chit-chat, misheard names, "everyone", the web gate. No model, no network."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from bank import store
from reason import answer, route

DAY = date(2026, 11, 15)


def email(id_, name, sent, subject, ask, deadline=None):
    return {"id": id_, "kind": "email", "folder": "person", "source": f"t:{id_}", "sender_name": name,
            "sender_address": f"{name.split()[0].lower()}@x.example", "sent_date": sent, "subject": subject,
            "ask": ask, "deadlines": [{"phrase": "x", "date": deadline, "time": None}] if deadline else [],
            "course": None, "topic": None, "ingested_at": "2026-11-14T00:00:00", "body": f"About {subject}."}


def no_model(*a, **k):
    raise AssertionError("model called")


def no_web(*a, **k):
    raise AssertionError("web route reached")


@mock.patch("llm.client.complete_json", no_model)
@mock.patch("llm.client.complete", no_model)
@mock.patch("llm.client.chat", no_model)
@mock.patch("reason.answer._web", no_web)
class Problem8(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for e in (email("r00000000001", "Lena Marsh", "2026-11-15", "Lab report format", "Send me your outline."),
                  email("r00000000002", "Felix Ambrose", "2026-11-14", "Cabin", "Send your $35 share.", "2026-11-20"),
                  email("r00000000003", "Hugo Sato", "2026-11-10", "Old vote", "Vote by Friday.", "2026-11-13"),
                  email("r00000000004", "Milo Fenn", "2026-11-13", "Playlist", None)):
            store.write_entry(e, self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def ask(self, q):
        return answer(q, today=DAY, root=self.root, _online=lambda: True)

    def test_chat_never_reaches_the_web(self):
        # brief Y: small talk is a short general answer (thinking off), never the web or the bank
        calls = []

        def fake(msgs, thinking=True, max_tokens=0):
            calls.append((thinking, max_tokens, msgs[-1]["content"]))
            return "Hi! I hear you fine.", False
        with mock.patch("reason.think._think", fake), \
                mock.patch("reason.answer._bank", side_effect=AssertionError("no bank for small talk")):
            for q in ("Hey, can you hear me okay? Hope you're doing well.", "Hi", "hello flux",
                      "Is this working?", "Thanks so much!", "testing testing"):
                a = self.ask(q)
                self.assertEqual(a.route, "general", q)
                self.assertTrue(a.text.endswith("From general knowledge, not from your mail or the web."), q)
        self.assertTrue(all(not t and "one or two sentences" in c for t, _, c in calls))
        for q in ("Who are you?", "What can you do?", "who made you"):
            a = self.ask(q)
            self.assertEqual(a.route, "chat", q)
            self.assertTrue(a.text.startswith("I'm Flux"), q)

    def test_a_question_about_my_week_is_a_catch_up_not_a_web_search(self):
        for q in ("What does this week look like?", "how does my week look", "What's my week?", "what does tomorrow look like"):
            self.assertEqual(self.ask(q).route, "catchup", q)

    def test_questions_about_the_user_never_reach_the_web(self):
        for q in ("What am I?", "Who am I?"):
            a = self.ask(q)
            self.assertEqual(a.route, "about_me", q)

    def test_not_chat(self):
        for q in ("Hey, what's due tomorrow?", "hi, how much is my share", "hey Felix asked me something",
                  "thanks for the review session room"):
            self.assertFalse(route.is_chat(q), q)
        self.assertEqual(self.ask("Hey, what's due tomorrow?").route, "due")

    def test_misheard_name(self):
        a = self.ask("Elena asked me")
        self.assertEqual(a.route, "person")
        self.assertTrue(a.text.startswith('(I heard "Elena" and took it as Lena Marsh.)\nFrom Lena Marsh:'))
        self.assertIn("outline", a.text)

    def test_near_name_rules(self):
        self.assertTrue(route.near_name("elena", "lena"))
        self.assertTrue(route.near_name("felixx", "felix"))
        self.assertTrue(route.near_name("hugoo", "hugo"))
        self.assertFalse(route.near_name("tim", "tom"))  # too short to guess
        self.assertFalse(route.near_name("zelda", "lena"))
        self.assertFalse(route.near_name("lena", "lena"))

    def test_two_close_senders_asks_which(self):
        store.write_entry(email("r00000000005", "Alana Price", "2026-11-12", "Notes", "Share notes."), self.root)
        store.write_entry(email("r00000000006", "Alani Moss", "2026-11-12", "Rides", "Pick a ride."), self.root)
        a = self.ask("Alano asked me")
        self.assertEqual(a.route, "person")
        self.assertEqual(a.text, 'I heard "Alano". Did you mean Alana Price or Alani Moss?')

    def test_unknown_name_still_nothing(self):
        self.assertEqual(self.ask("What did Zelda ask me?").text, "I have nothing from Zelda.")
        self.assertEqual(self.ask("What did Tim ask me?").text, "I have nothing from Tim.")

    def test_everyone(self):
        a = self.ask("What did everyone ask me?")
        self.assertEqual(a.route, "person")
        self.assertEqual(a.text, "Open asks from everyone (2):\n"
                                 "- Lena Marsh, Nov 15  Lab report format: Send me your outline.\n"
                                 "- Felix Ambrose, Nov 14  Cabin: Send your $35 share.\n"
                                 "Source: Lena Marsh, Nov 15; Felix Ambrose, Nov 14")
        self.assertTrue(route.is_everyone("did anyone want anything from me"))
        self.assertFalse(route.is_everyone("is everyone coming to the cabin"))

    def test_web_gate(self):
        self.assertTrue(route.web_ok("When did the Berlin Wall fall?"))
        self.assertTrue(route.web_ok("who wrote Frankenstein"))
        self.assertTrue(route.web_ok("Flux, what is the capital of Peru"))
        self.assertFalse(route.web_ok("Elena asked me"))
        self.assertFalse(route.web_ok("purple elephants dancing"))
        self.assertFalse(route.web_ok("What's my favorite color?"))
        with mock.patch("reason.think._think", return_value=("I'm not sure what you mean.", False)):
            a = self.ask("What's my favorite color?")  # about the user, nothing saved
            self.assertEqual((a.route, a.text), ("reason", "I have nothing saved about that."))
            a = self.ask("purple elephants dancing")  # never the web (_web raises here)
            self.assertEqual(a.route, "general")


if __name__ == "__main__":
    unittest.main()
