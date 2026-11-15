import base64
import unittest
from unittest import mock

from sufficiency import websearch as W


class TestWebsearch(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
