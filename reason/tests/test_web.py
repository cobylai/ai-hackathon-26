"""Chat window server: page, /status and /ask, with answer() stubbed. No model, no network."""
from __future__ import annotations

import json
import re
import threading
import unittest
import urllib.request
from http.server import HTTPServer

from reason import Answer
from reason.web import PAGE, make_handler


class Web(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seen = []

        def fake_answer(q, today=None):
            cls.seen.append((q, today))
            return Answer("Due Mon Nov 16:\n- Bring a calculator (Prof. Lena Ortiz, Nov 11)", "due",
                          ["/x.md"], 0.01)

        cls.srv = HTTPServer(("127.0.0.1", 0), make_handler(
            today="2026-11-14", answer_fn=fake_answer, online_fn=lambda: False, count_fn=lambda: 17))
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.read().decode()

    def test_page_loads_nothing_remote(self):
        html = self.get("/")
        self.assertIn('id="q"', html)
        self.assertIn('id="talk" disabled', html)
        self.assertEqual(re.findall(r"(?:src|href)\s*=\s*[\"']?(?:https?:)?//", PAGE), [])
        self.assertNotIn("@import", PAGE)

    def test_status(self):
        self.assertEqual(json.loads(self.get("/status")), {"online": False, "items": 17})

    def test_ask(self):
        req = urllib.request.Request(self.base + "/ask", data=json.dumps({"question": "what is due Monday"}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            got = json.loads(r.read())
        self.assertEqual(got["route"], "due")
        self.assertIn("Prof. Lena Ortiz", got["text"])
        self.assertIn(("what is due Monday", "2026-11-14"), self.seen)


if __name__ == "__main__":
    unittest.main()
