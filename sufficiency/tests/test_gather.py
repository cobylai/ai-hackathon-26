"""Gather loop and rephrase against stub search/open and a stubbed client."""
import unittest
from unittest import mock

from llm import client
import importlib
G = importlib.import_module("sufficiency.gather")
R = importlib.import_module("sufficiency.rephrase")
from sufficiency.judge import Verdict

PAGES = {
    "https://ads.example.com": {"title": "Deals", "text": "TOP 10 DEALS!!! Advertisement."},
    "https://rec.example.edu/about": {"title": "Rec Center", "text": "About the Rec Center. Hours vary."},
    "https://rec.example.edu/hours": {"title": "Rec Hours",
                                      "text": "Thu Nov 26 (Thanksgiving): CLOSED"},
}


def fake_judge(question, text, url=None, today=None):
    ok = "CLOSED" in text
    return Verdict(ok, "Closed" if ok else None, "Thu Nov 26 (Thanksgiving): CLOSED" if ok else None,
                   "answered" if ok else "no_answer", url)


class Gather(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(G, "judge", side_effect=fake_judge)
        self.judge = p.start()
        self.addCleanup(p.stop)

    def opener(self, url):
        return PAGES[url]

    def test_found_first_query(self):
        search = lambda q: [{"title": "Rec hours", "url": "https://rec.example.edu/hours", "snippet": ""}]
        r = G.gather("Is the gym open on Thanksgiving?", search, self.opener)
        self.assertTrue(r.found)
        self.assertEqual(r.source.url, "https://rec.example.edu/hours")
        self.assertEqual(r.queries, ["Is the gym open on Thanksgiving?"])
        self.assertEqual(r.answer, "Closed")

    def test_found_after_rephrase(self):
        def search(q):
            if q == "Is the gym open on Thanksgiving?":
                return [{"title": "Deals", "url": "https://ads.example.com", "snippet": ""}]
            return [{"title": "Rec hours", "url": "https://rec.example.edu/hours", "snippet": ""}]
        with mock.patch.object(G, "rephrase", return_value="rec center thanksgiving hours") as rp:
            r = G.gather("Is the gym open on Thanksgiving?", search, self.opener)
        self.assertTrue(r.found)
        self.assertEqual(r.queries, ["Is the gym open on Thanksgiving?", "rec center thanksgiving hours"])
        self.assertEqual(rp.call_count, 1)

    def test_gives_up_after_limit(self):
        search = lambda q: [{"title": "Deals", "url": "https://ads.example.com", "snippet": ""},
                            {"title": "Rec", "url": "https://rec.example.edu/about", "snippet": ""}]
        qs = iter(["q2", "q3", "q4"])
        with mock.patch.object(G, "rephrase", side_effect=lambda *a, **k: next(qs)) as rp:
            r = G.gather("Is the gym open on Thanksgiving?", search, self.opener, max_rephrases=2)
        self.assertFalse(r.found)
        self.assertIsNone(r.source)
        self.assertEqual(r.queries, ["Is the gym open on Thanksgiving?", "q2", "q3"])
        self.assertEqual(rp.call_count, 2)
        # same two urls every time: each opened once only
        self.assertEqual(r.opened, ["https://ads.example.com", "https://rec.example.edu/about"])
        self.assertEqual(self.judge.call_count, 2)
        self.assertIn("Not found after 3 search(es) and 2 page(s)", r.message)
        self.assertIn('"q3"', r.message)

    def test_gives_up_when_rephrase_none(self):
        search = lambda q: []
        with mock.patch.object(G, "rephrase", return_value=None):
            r = G.gather("q", search, self.opener)
        self.assertFalse(r.found)
        self.assertEqual(r.queries, ["q"])

    def test_open_failure_skipped(self):
        def opener(url):
            if "about" in url:
                raise TimeoutError("blocked")
            if "ads" in url:
                return {"title": "x", "text": "   "}
            return PAGES[url]
        search = lambda q: [{"title": "Rec about", "url": "https://rec.example.edu/about"},
                            {"title": "Deals", "url": "https://ads.example.com"},
                            {"title": "Rec hours", "url": "https://rec.example.edu/hours"}]
        r = G.gather("Is the gym open on Thanksgiving?", search, opener)
        self.assertTrue(r.found)
        self.assertEqual(len(r.opened), 3)
        self.assertEqual(self.judge.call_count, 1)

    def test_max_results_and_title_order(self):
        hits = [{"title": f"Deals {i}", "url": f"https://ads.example.com/{i}", "snippet": ""}
                for i in range(12)]
        hits.insert(5, {"title": "Gym Thanksgiving hours", "url": "https://rec.example.edu/hours"})
        opened = []
        def opener(url):
            opened.append(url)
            return PAGES.get(url, {"title": "", "text": "nothing"})
        r = G.gather("Is the gym open on Thanksgiving?", lambda q: hits, opener)
        self.assertTrue(r.found)
        self.assertEqual(opened[0], "https://rec.example.edu/hours")  # title match goes first

    def test_max_seconds(self):
        t = [0.0]
        def clock():
            return t[0]
        def opener(url):
            t[0] += 25.0          # each page costs 25 "seconds"
            return PAGES[url]
        search = lambda q: [{"title": "Deals", "url": "https://ads.example.com"},
                            {"title": "Rec", "url": "https://rec.example.edu/about"},
                            {"title": "Rec hours", "url": "https://rec.example.edu/hours"}]
        with mock.patch.object(G.time, "monotonic", side_effect=clock), \
                mock.patch.object(G, "rephrase") as rp:
            r = G.gather("Is the gym open on Thanksgiving?", search, opener, max_seconds=40)
        self.assertFalse(r.found)
        self.assertEqual(len(r.opened), 2)          # third page never opened
        rp.assert_not_called()
        self.assertTrue(r.message.startswith("Ran out of time (40s). Not found after 1 search(es)"))

    def test_no_time_limit(self):
        search = lambda q: [{"title": "Rec hours", "url": "https://rec.example.edu/hours"}]
        self.assertTrue(G.gather("q", search, self.opener, max_seconds=None).found)

    def test_adapter_shapes(self):
        self.assertEqual(G._hits([("T", "u", "s"), {"title": "A", "url": "v"}, {"title": "no url"}]),
                         [G.Hit("T", "u", "s"), G.Hit("A", "v", "")])
        self.assertEqual(G._page("plain"), G.Page("", "plain"))
        self.assertEqual(G._page({"title": "t", "text": "x"}), G.Page("t", "x"))
        self.assertEqual(G._page(None), G.Page("", ""))

    def test_adapter_partner_shapes(self):
        from harness.search.google import Result
        r = Result(title="T", url="https://a.example/x", domain="a.example", snippet="s")
        self.assertEqual(G._hits([r]), [G.Hit("T", "https://a.example/x", "s")])
        self.assertEqual(G._page(("OK", "body")), G.Page("", "body"))
        self.assertEqual(G._page(("BLOCKED", "bot check")), G.Page("", ""))


def stub_chat(*texts):
    it = iter(texts)
    return mock.patch.object(client, "chat", side_effect=lambda *a, **k: client.Reply(text=next(it)))


class Rephrase(unittest.TestCase):
    def test_new_query(self):
        with stub_chat('Query: "cornell rec center thanksgiving hours"'):
            self.assertEqual(R.rephrase("gym thanksgiving?", ["gym thanksgiving?"]),
                             "cornell rec center thanksgiving hours")

    def test_repeat_then_new(self):
        with stub_chat("Thanksgiving gym?", "rec center holiday schedule") as m:
            q = R.rephrase("gym thanksgiving?", ["gym thanksgiving?"])
        self.assertEqual(q, "rec center holiday schedule")
        self.assertEqual(m.call_count, 2)
        self.assertIn("repeats a query", m.call_args[0][0][-1]["content"])

    def test_two_repeats_none(self):
        with stub_chat("gym thanksgiving", "GYM  Thanksgiving?!"):
            self.assertIsNone(R.rephrase("gym thanksgiving?", ["gym thanksgiving?"]))

    def test_is_repeat(self):
        self.assertTrue(R.is_repeat("Gym, Thanksgiving", ["thanksgiving gym"]))
        self.assertTrue(R.is_repeat("", []))
        self.assertFalse(R.is_repeat("rec hours", ["gym thanksgiving"]))


if __name__ == "__main__":
    unittest.main()
