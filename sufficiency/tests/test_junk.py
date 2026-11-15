"""Bot-check and error pages never become answers (partner test report, problem 7)."""
import unittest
from unittest import mock

import importlib
G = importlib.import_module("sufficiency.gather")
from sufficiency.judge import Verdict
from sufficiency.junk import blocked_page, looks_blocked

REDDIT = "Prove your humanity\nWe've had a lot of requests from your network. Continue"


class Junk(unittest.TestCase):
    def test_phrases(self):
        self.assertTrue(looks_blocked("Prove your humanity"))
        self.assertTrue(looks_blocked("Please   VERIFY you are human"))
        self.assertTrue(looks_blocked("Error 404 Not Found"))
        self.assertFalse(looks_blocked("Jomo Kenyatta became Kenya's first president."))
        self.assertFalse(looks_blocked(""))

    def test_long_article_mentioning_captcha_is_kept(self):
        self.assertTrue(blocked_page(REDDIT))
        self.assertFalse(blocked_page("A CAPTCHA is a test. " + "History of the test. " * 300))


class GatherSkipsWalls(unittest.TestCase):
    def setUp(self):
        def fake_judge(question, text, url=None, today=None):
            # the model "answers" with whatever the page's first line is
            first = text.strip().splitlines()[0]
            return Verdict(True, first, first, "answered", url)
        p = mock.patch.object(G, "judge", side_effect=fake_judge)
        self.judge = p.start()
        self.addCleanup(p.stop)
        self.search = lambda q: [{"title": "a", "url": "https://blocked.example/"},
                                 {"title": "b", "url": "https://reddit.example/"},
                                 {"title": "c", "url": "https://good.example/"}]

    def test_blocked_status_and_wall_page_never_judged(self):
        pages = {"https://blocked.example/": ("BLOCKED", "Are you a robot?"),
                 "https://reddit.example/": ("OK", REDDIT),
                 "https://good.example/": ("OK", "Lena asked about the cabin trip.")}
        with mock.patch.object(G, "rephrase", return_value=None):
            r = G.gather("What did Elena ask me?", self.search, pages.__getitem__)
        self.assertTrue(r.found)
        self.assertEqual(r.source.url, "https://good.example/")
        self.assertEqual(self.judge.call_count, 1)  # only the good page

    def test_wall_answer_on_long_page_refused(self):
        long_wall = "Prove your humanity\n" + "Some page furniture text. " * 200
        pages = {"https://blocked.example/": ("ERR", ""),
                 "https://reddit.example/": ("OK", long_wall),
                 "https://good.example/": ("LOGIN", "")}
        with mock.patch.object(G, "rephrase", return_value=None):
            r = G.gather("What did everyone ask me?", self.search, pages.__getitem__)
        self.assertFalse(r.found)
        self.assertEqual([v.reason for v in r.verdicts], ["blocked_page"])
        self.assertIn("2 unreadable", r.message)


if __name__ == "__main__":
    unittest.main()
