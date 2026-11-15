import base64
import unittest
from unittest import mock

from sufficiency import websearch as W


class TestWebsearch(unittest.TestCase):
    def setUp(self):
        # No network in unit tests: Wikipedia is faked unless a test sets it.
        p = mock.patch.object(W, "_wikipedia", return_value=[])
        self.wiki = p.start()
        self.addCleanup(p.stop)

    def test_partner_results_win(self):
        rows = [{"title": "T", "url": "https://a.example/", "snippet": "s"}]
        with mock.patch.object(W, "_partner", return_value=(rows, "OK")), \
             mock.patch.object(W, "_bing") as bing:
            self.assertEqual(W.search("q"), rows)
            bing.assert_not_called()
        self.assertEqual(W.last_engine, "harness")

    def test_blocked_falls_back_to_bing(self):
        hit = [{"title": "B", "url": "https://b.example/", "snippet": ""}]
        with mock.patch.object(W, "_partner", return_value=([], "BLOCKED")), \
             mock.patch.object(W, "_bing", return_value=hit) as bing:
            self.assertEqual(W.search("q"), hit)
            bing.assert_called_once_with("q")
        self.assertEqual(W.last_engine, "bing (harness said BLOCKED)")

    def test_partner_crash_falls_back_to_bing(self):
        with mock.patch.object(W, "_partner", side_effect=RuntimeError("no browser")), \
             mock.patch.object(W, "_bing", return_value=[]):
            self.assertEqual(W.search("q"), [])

    def test_unwrap_bing_links(self):
        t = "https://example.org/a?b=1"
        enc = base64.urlsafe_b64encode(t.encode()).decode().rstrip("=")
        self.assertEqual(W._unwrap(f"https://www.bing.com/ck/a?!&p=x&u=a1{enc}&ntb=1"), t)
        self.assertEqual(W._unwrap("https://plain.example/"), "https://plain.example/")

    def test_relevant(self):
        q = "Who was the first president of Kenya?"
        self.assertTrue(W.relevant(q, {"title": "President of Kenya - Wikipedia", "url": "u"}))
        self.assertTrue(W.relevant(q, {"title": "List of presidents", "snippet": "Kenya's",
                                       "url": "u"}))
        self.assertFalse(W.relevant(q, {"title": "Koncerty, opera, balet Praha",
                                        "url": "https://www.visitprague.cz/cz/kultura/"}))
        # one shared word out of three is not enough
        self.assertFalse(W.relevant("speed of light per second",
                                    {"title": "Speedtest by Ookla", "url": "https://speedtest.net/"}))
        self.assertTrue(W.relevant("??", {"title": "anything", "url": "u"}))

    def test_off_topic_hits_dropped_and_wikipedia_added(self):
        junk = [{"title": "Kalender - visitprague.cz", "url": f"https://visitprague.cz/{i}",
                 "snippet": "Koncerty"} for i in range(10)]
        wiki = [{"title": "President of Kenya", "url": "https://en.wikipedia.org/wiki/President_of_Kenya",
                 "snippet": "The president of the Republic of Kenya"}]
        self.wiki.return_value = wiki
        with mock.patch.object(W, "_partner", return_value=([], "BLOCKED")), \
             mock.patch.object(W, "_bing", return_value=junk):
            self.assertEqual(W.search("first president of Kenya"), wiki)
        self.assertIn("10 off-topic dropped, + wikipedia", W.last_engine)

    def test_enough_good_hits_skip_wikipedia(self):
        good = [{"title": f"Frankenstein novel {i}", "url": f"https://x.example/{i}", "snippet": ""}
                for i in range(3)]
        with mock.patch.object(W, "_partner", return_value=([], "BLOCKED")), \
             mock.patch.object(W, "_bing", return_value=good):
            self.assertEqual(W.search("Who wrote Frankenstein?"), good)
        self.wiki.assert_not_called()

    def test_few_good_hits_keep_them_first_then_wikipedia_no_dupes(self):
        good = [{"title": "Speed of light", "url": "https://en.wikipedia.org/wiki/Speed_of_light",
                 "snippet": ""}]
        self.wiki.return_value = [dict(good[0]),
                                  {"title": "Speed of light (film)", "url": "https://w/2", "snippet": ""}]
        with mock.patch.object(W, "_partner", return_value=([], "BLOCKED")), \
             mock.patch.object(W, "_bing", return_value=good):
            got = W.search("speed of light")
        self.assertEqual([r["url"] for r in got], [good[0]["url"], "https://w/2"])

    def test_bing_crash_still_tries_wikipedia(self):
        with mock.patch.object(W, "_partner", return_value=([], "BLOCKED")), \
             mock.patch.object(W, "_bing", side_effect=RuntimeError("no browser")):
            self.assertEqual(W.search("first president of Kenya"), [])
        self.wiki.assert_called_once()


class TestWikipedia(unittest.TestCase):
    def test_parses_api_reply(self):
        import io, json
        body = json.dumps({"query": {"search": [
            {"title": "Mary Shelley", "snippet": "<span class=\"searchmatch\">Mary</span> &amp; Percy"},
            {"title": ""}]}}).encode()
        with mock.patch("urllib.request.urlopen", return_value=io.BytesIO(body)):
            got = W._wikipedia("Mary Shelley")
        self.assertEqual(got, [{"title": "Mary Shelley", "url": "https://en.wikipedia.org/wiki/Mary_Shelley",
                                "snippet": "Mary & Percy"}])

    def test_network_error_gives_empty(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            self.assertEqual(W._wikipedia("x"), [])


if __name__ == "__main__":
    unittest.main()
