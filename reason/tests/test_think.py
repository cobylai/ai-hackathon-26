"""Brief Y: the general and reason routes, the kind check and the fact check. Model stubbed."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import bank
from bank import store
from reason import answer, think

DAY = date(2026, 11, 15)  # a Sunday
LABEL = "From general knowledge, not from your mail or the web."


def email(id_, name, sent, subject, ask, deadline=None, time=None, body=None):
    return {"id": id_, "kind": "email", "folder": "person", "source": f"t:{id_}", "sender_name": name,
            "sender_address": f"{name.split()[0].lower()}@x.example", "sent_date": sent, "subject": subject,
            "ask": ask, "deadlines": [{"phrase": "x", "date": deadline, "time": time}] if deadline else [],
            "course": None, "topic": None, "ingested_at": "2026-11-14T00:00:00",
            "body": body or f"About {subject}."}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for e in (email("y00000000001", "Felix Ambrose", "2026-11-15", "Pay your share for the cabin",
                        "Send me your $35 share.", "2026-11-20", "17:00", "Felix needs $35 by Friday 5pm."),
                  email("y00000000002", "Lena Marsh", "2026-11-15", "Lab report format",
                        "Send me your outline.", "2026-11-17", "12:00")):
            store.write_entry(e, self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def ask(self, q, **k):
        k.setdefault("_online", lambda: False)
        k.setdefault("_events", lambda s, e: [])
        return answer(q, today=DAY, root=self.root, **k)


class Kind(Base):
    def kind(self, q):
        from reason.answer import _senders
        return "b" if think.about_user(q, _senders(self.root), self.root) else "c"

    def test_about_the_user(self):
        for q in ("What should I work on first?", "what's my blood type", "Is the cabin trip still on?",
                  "How much is Felix owed?", "When is my next exam", "what's on for CS 3110",
                  "tell me about my week"):
            self.assertEqual(self.kind(q), "b", q)

    def test_general(self):
        for q in ("How do I cook rice?", "Why is the sky blue?", "tell me a joke", "What is the capital of Peru?",
                  "Can you tell me who wrote Frankenstein?", "write a haiku about rain"):
            self.assertEqual(self.kind(q), "c", q)


class FactCheck(unittest.TestCase):
    FACTS = ("[1] From: Felix Ambrose\nDate: 2026-11-15\nSubject: Pay your share\nAsk: Send me your $35 share.\n"
             "Deadlines: x (2026-11-20 17:00)\n\n[2] Due Tuesday Nov 17 (2026-11-17) noon (12:00): outline")

    def bad(self, text, q="what first?"):
        return think.unsupported(text, self.FACTS, q, DAY)

    def test_supported(self):
        self.assertEqual(self.bad("Pay Felix the $35 by Friday Nov 20 at 5pm, then send the outline by noon Tuesday."), [])
        self.assertEqual(self.bad("Start with the outline."), [])

    def test_made_up_things_are_caught(self):
        self.assertEqual(self.bad("Pay Felix $40 by Nov 21 at 3pm."), ["Nov 21", "3pm", "$40"])
        self.assertEqual(self.bad("Then ask Priya for help on Wednesday."), ["Wednesday", "Priya"])
        self.assertEqual(self.bad("Study for MATH 2940 too."), ["MATH 2940"])

    def test_sentence_starts_and_markdown_are_not_names(self):
        self.assertEqual(self.bad("First, pay Felix.\n- Then the outline.\n**Focus** on that."), [])


class Reason(Base):
    def test_nothing_saved_never_calls_the_model(self):
        with mock.patch("reason.think._think", side_effect=AssertionError("model called")), \
                mock.patch("reason.answer._bank", lambda *a: None):
            a = self.ask("what's my blood type?")
        self.assertEqual((a.route, a.text, a.sources), ("reason", "I have nothing saved about that.", []))

    def test_planning_answer_checked_with_sources(self):
        reply = ('{"answer": "Send Lena the outline first: it is due Tuesday Nov 17 at noon. '
                 'Then pay Felix $35 by Friday 5pm.", "used": [2, 1]}')
        seen = {}

        def fake(msgs, thinking=True, max_tokens=0):
            seen["prompt"], seen["thinking"] = msgs[-1]["content"], thinking
            return reply, False
        with mock.patch("reason.think._think", fake), mock.patch("reason.answer._bank", lambda *a: None):
            a = self.ask("What should I work on first this week?")
        self.assertEqual(a.route, "reason")
        self.assertTrue(seen["thinking"])
        self.assertIn("Due Tuesday Nov 17 (2026-11-17) noon (12:00)", seen["prompt"])  # due list added
        self.assertIn("Lena Marsh, Nov 15", a.text.split("Source: ")[1])
        self.assertIn("Felix Ambrose, Nov 15", a.text.split("Source: ")[1])
        self.assertEqual(len(a.sources), 2)

    def test_retry_once_then_list_what_it_has(self):
        replies = iter(['{"answer": "Pay Felix $40 by Nov 21.", "used": [1]}',
                        '{"answer": "Ask Priya on Monday.", "used": [1]}'])
        calls = []

        def fake(msgs, thinking=True, max_tokens=0):
            calls.append((thinking, msgs[-1]["content"]))
            return next(replies), False
        with mock.patch("reason.think._think", fake), mock.patch("reason.answer._bank", lambda *a: None):
            a = self.ask("What should I do about the cabin money?")
        self.assertEqual([c[0] for c in calls], [True, False])  # retry has thinking off
        self.assertIn("Nov 21", calls[1][1])  # the retry names what was wrong
        self.assertTrue(a.text.startswith("I couldn't give an answer I could check"))
        self.assertIn("Pay your share for the cabin", a.text)
        self.assertNotIn("$40", a.text)
        self.assertIn("Source:", a.text)

    def test_retry_that_passes_is_shown(self):
        replies = iter(['{"answer": "Pay Felix $40.", "used": [1]}', '{"answer": "Pay Felix $35.", "used": [1]}'])
        with mock.patch("reason.think._think", lambda *a, **k: (next(replies), False)), \
                mock.patch("reason.answer._bank", lambda *a: None):
            a = self.ask("What should I do about the cabin money?")
        self.assertTrue(a.text.startswith("Pay Felix $35."))

    def test_person_guard_still_first(self):
        with mock.patch("reason.think._think", side_effect=AssertionError("model called")):
            self.assertEqual(self.ask("What did Priya ask me?").text, "I have nothing from Priya.")


class General(Base):
    def test_offline_general_is_labelled(self):
        with mock.patch("reason.think._think", return_value=("Rayleigh scattering.", False)):
            a = self.ask("Why is the sky blue?")
        self.assertEqual((a.route, a.text), ("general", "Rayleigh scattering.\n" + LABEL))
        self.assertEqual(a.sources, [])

    def test_volatile_offline_says_it_cannot_check(self):
        with mock.patch("reason.think._think", return_value=("Usually cold in November.", False)):
            a = self.ask("What's the weather in Ithaca today?")
        self.assertEqual(a.text.split("\n")[0], "I can't check that right now, so this may be out of date.")
        self.assertTrue(a.text.endswith(LABEL))

    def test_cut_short(self):
        with mock.patch("reason.think._think", return_value=("Short answer.", True)):
            a = self.ask("Explain quantum computing")
        self.assertIn("(I was cut short, so this is brief.)", a.text)

    def test_online_lookup_tries_the_web_first(self):
        web = SimpleNamespace(route="web", text="Lima\nSource: https://x.org", sources=["https://x.org"])
        with mock.patch("reason.think._think", side_effect=AssertionError("model called")), \
                mock.patch("reason.answer._web", return_value=web):
            a = self.ask("What is the capital of Peru?", _online=lambda: True)
        self.assertIs(a, web)

    def test_explanations_skip_bank_and_web(self):
        with mock.patch("reason.think._think", return_value=("Boil water.", False)), \
                mock.patch("reason.answer._bank", side_effect=AssertionError("bank")), \
                mock.patch("reason.answer._web", side_effect=AssertionError("web")):
            a = self.ask("How do I cook rice?", _online=lambda: True)
        self.assertEqual(a.route, "general")

    def test_conversation_context(self):
        from reason.session import Session
        s = Session()
        s.turns = [{"question": "Who wrote Frankenstein?", "text": "Mary Shelley."}]
        seen = {}

        def fake(msgs, thinking=True, max_tokens=0):
            seen["msgs"] = msgs
            return "1818.", False
        with mock.patch("reason.think._think", fake):
            self.ask("when was it published?", session=s)
        self.assertEqual([m["role"] for m in seen["msgs"]], ["system", "user", "assistant", "user"])
        self.assertEqual(seen["msgs"][1]["content"], "Who wrote Frankenstein?")


class CutShort(unittest.TestCase):
    def test_ran_out_inside_thinking_gets_a_short_answer(self):
        replies = [SimpleNamespace(text="thinking thinking", reasoning=None, finish_reason="length"),
                   SimpleNamespace(text="Brief.", reasoning=None, finish_reason="stop")]
        with mock.patch("llm.client.chat", side_effect=replies) as chat:
            text, cut = think._think([{"role": "user", "content": "q"}])
        self.assertEqual((text, cut), ("Brief.", True))
        self.assertEqual(chat.call_args_list[0].kwargs["max_tokens"], think.THINK_TOKENS)
        self.assertFalse(chat.call_args_list[1].kwargs["thinking"])


if __name__ == "__main__":
    unittest.main()
