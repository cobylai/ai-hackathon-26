"""No server needed: llm.client is stubbed."""
import unittest
from datetime import date
from unittest import mock

from llm import client
import importlib
J = importlib.import_module("sufficiency.judge")  # the package exports a function of the same name
from sufficiency import prompts

PAGE = ("Recreation Center Hours - Thanksgiving Break\nWed Nov 25: 6am-6pm\n"
        "Thu Nov 26 (Thanksgiving): CLOSED\nFri Nov 27: 10am-4pm")


class QuoteCheck(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(J.quote_in_page("Thu Nov 26 (Thanksgiving): CLOSED", PAGE))

    def test_case_and_whitespace(self):
        self.assertTrue(J.quote_in_page("thu   nov 26\n(thanksgiving):  closed", PAGE))

    def test_curly_quotes_and_dashes(self):
        page = "Don't park in Lot B — it's \"reserved\" from 2am-6am."
        self.assertTrue(J.quote_in_page("Don’t park in Lot B - it’s “reserved”", page))

    def test_edge_punctuation(self):
        self.assertTrue(J.quote_in_page('"- Fri Nov 27: 10am-4pm."', PAGE))

    def test_made_up(self):
        self.assertFalse(J.quote_in_page("The gym is open 24 hours on Thanksgiving", PAGE))

    def test_empty(self):
        self.assertFalse(J.quote_in_page("", PAGE))
        self.assertFalse(J.quote_in_page("   ", PAGE))

    def test_ellipsis_pieces(self):
        self.assertTrue(J.quote_in_page("Wed Nov 25: 6am-6pm ... Fri Nov 27: 10am-4pm", PAGE))
        self.assertFalse(J.quote_in_page("Wed Nov 25: 6am-6pm ... Sat Nov 28: 24 hours", PAGE))

    def test_all_short_pieces_fail(self):
        # every piece under 8 chars: nothing to check, so it must not pass
        self.assertFalse(J.quote_in_page("Thu ... CLOSED ... Fri", PAGE))
        self.assertFalse(J.quote_in_page("CLOSED", PAGE))


def stub_json(*replies):
    it = iter(replies)
    def f(*a, **k):
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r
    return mock.patch.object(client, "complete_json", side_effect=f)


class Judge(unittest.TestCase):
    def test_good_quote(self):
        with stub_json({"answer": "No, it is closed", "quote": "Thu Nov 26 (Thanksgiving): CLOSED"}):
            v = J.judge("Is the gym open on Thanksgiving?", PAGE, url="u")
        self.assertTrue(v.enough)
        self.assertEqual(v.reason, "answered")
        self.assertEqual(v.evidence, "Thu Nov 26 (Thanksgiving): CLOSED")
        self.assertEqual(v.url, "u")

    def test_bad_quote(self):
        with stub_json({"answer": "Yes", "quote": "Open 8am-8pm on Thanksgiving"}):
            v = J.judge("Is the gym open on Thanksgiving?", PAGE)
        self.assertFalse(v.enough)
        self.assertEqual(v.reason, "quote_not_in_page")
        self.assertIsNone(v.evidence)

    def test_list_of_quotes(self):
        with stub_json({"answer": "Wed 6am-6pm, Thu closed",
                        "quote": ["Wed Nov 25: 6am-6pm", "Thu Nov 26 (Thanksgiving): CLOSED"]}):
            v = J.judge("Gym hours Wed and Thu?", PAGE)
        self.assertTrue(v.enough)
        with stub_json({"answer": "x", "quote": ["Wed Nov 25: 6am-6pm", "Sat Nov 28: open all night"]}):
            self.assertEqual(J.judge("q", PAGE).reason, "quote_not_in_page")

    def test_null(self):
        with stub_json({"answer": None, "quote": None}):
            v = J.judge("q", PAGE)
        self.assertEqual((v.enough, v.reason), (False, "no_answer"))

    def test_string_null(self):
        with stub_json({"answer": "null", "quote": "Thu Nov 26 (Thanksgiving): CLOSED"}):
            self.assertEqual(J.judge("q", PAGE).reason, "no_answer")

    def test_bad_json(self):
        with stub_json(client.JSONReplyError("x")):
            v = J.judge("q", PAGE)
        self.assertEqual((v.enough, v.reason), (False, "bad_json"))

    def test_sends_today_and_sampling(self):
        with stub_json({"answer": None, "quote": None}) as m:
            J.judge("q", PAGE, today=date(2026, 11, 13))
        args, kw = m.call_args
        self.assertIn("Today is Friday, 13 November 2026.", args[0])
        self.assertEqual(kw["sampling"], prompts.JUDGE_SAMPLING)


class CheckCall(unittest.TestCase):
    def run_with(self, check_text):
        good = {"answer": "No, it is closed", "quote": "Thu Nov 26 (Thanksgiving): CLOSED"}
        with mock.patch.object(prompts, "CHECK_ANSWER", True), stub_json(good), \
                mock.patch.object(client, "chat",
                                  return_value=client.Reply(text=check_text)) as ch:
            v = J.judge("Is the gym open on Thanksgiving?", PAGE, today="Friday")
        return v, ch

    def test_yes_keeps(self):
        v, ch = self.run_with("A")
        self.assertTrue(v.enough)
        self.assertIn("PROPOSED ANSWER: No, it is closed", ch.call_args[0][0][-1]["content"])

    def test_no_rejects(self):
        v, _ = self.run_with("B")
        self.assertEqual((v.enough, v.reason, v.evidence), (False, "not_this_question", None))

    def test_off_by_default_no_call(self):
        good = {"answer": "closed", "quote": "Thu Nov 26 (Thanksgiving): CLOSED"}
        with stub_json(good), mock.patch.object(client, "chat") as ch:
            self.assertTrue(J.judge("q", PAGE).enough)
        ch.assert_not_called()


class PromptVariants(unittest.TestCase):
    def test_pointer_rule_switch(self):
        self.assertNotIn("is not an answer", prompts.judge_prompt("q", "p", None, "t"))
        with mock.patch.object(prompts, "USE_POINTER_RULE", True):
            self.assertIn("is not an answer", prompts.judge_prompt("q", "p", None, "t"))


class Chunking(unittest.TestCase):
    def test_stops_at_first_enough_chunk(self):
        sections = [f"Section {i}\n" + ("Filler sentence about nothing much. " * 40) for i in range(6)]
        sections[4] += "\nGuests: each resident gets six guest passes per semester."
        page = "\n\n".join(sections)
        replies = [{"answer": None, "quote": None}] * 20
        with mock.patch.object(J, "PAGE_BUDGET", 400):
            from llm import tokens
            n = len(tokens.split_to_budget(page, 400))
            self.assertGreater(n, 3)
            calls = []
            def f(prompt, **k):
                calls.append(prompt)
                if "six guest passes" in prompt:
                    return {"answer": "6", "quote": "each resident gets six guest passes per semester"}
                return {"answer": None, "quote": None}
            with mock.patch.object(client, "complete_json", side_effect=f):
                v = J.judge("How many guest passes?", page)
        self.assertTrue(v.enough)
        self.assertEqual(v.chunks, n)
        self.assertEqual(len(calls), v.chunk + 1)   # stopped there
        self.assertLess(v.chunk + 1, n)
        self.assertIn("six guest passes", calls[-1])

    def test_short_page_one_chunk(self):
        with stub_json({"answer": None, "quote": None}) as m:
            v = J.judge("q", PAGE)
        self.assertEqual((v.chunks, m.call_count), (1, 1))


if __name__ == "__main__":
    unittest.main()
