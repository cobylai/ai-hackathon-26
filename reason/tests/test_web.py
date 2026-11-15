"""Chat window server: page, /status and /ask, with answer() stubbed. No model, no network."""
from __future__ import annotations

import json
import re
import threading
import unittest
import urllib.request
from unittest import mock
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
            today="2026-11-14", answer_fn=fake_answer, online_fn=lambda: False, count_fn=lambda: 17,
            model_fn=lambda: True,
            entries_fn=lambda: [
                {"sent_date": "2026-11-12", "sender_name": "Ann Old", "subject": "old", "body": "older one"},
                {"sent_date": "2026-11-14", "sender_name": "Bo New", "folder": "person", "id": "abc123def456", "subject": "Phone bill", "body": "Bill $42.18.",
                 "ask": "Pay it", "deadlines": [{"phrase": "Thursday", "date": "2026-11-19", "time": None}]}]))
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
        self.assertEqual(json.loads(self.get("/status")),
                         {"online": False, "items": 17, "voice": False, "voice_why": None,
                          "model": True})

    def test_status_line_says_when_the_model_is_down(self):
        self.assertIn("model down", PAGE)
        self.assertIn("r.model !== false", PAGE)

    def test_bank_list(self):
        rows = json.loads(self.get("/bank"))
        self.assertEqual([r["subject"] for r in rows], ["Phone bill", "old"])  # newest first
        self.assertEqual(rows[0], {"date": "2026-11-14", "sender": "Bo New", "subject": "Phone bill",
                                   "summary": "Bill $42.18.", "ask": "Pay it",
                                   "deadlines": "Thursday (2026-11-19)", "folder": "person",
                                   "id": "abc123def456"})
        self.assertEqual((rows[1]["folder"], rows[1]["id"]), ("", ""))  # older entries without them still list

    def test_page_hooks(self):
        html = self.get("/")
        for hook in ('id="send"', 'id="status"', "window.fluxTalk", "window.fluxFocus", "r.pending"):
            self.assertIn(hook, html)

    def test_listen_without_voice(self):
        req = urllib.request.Request(self.base + "/listen/start", data=b"", method="POST")
        with urllib.request.urlopen(req) as r:
            self.assertIn("voice is unavailable", json.loads(r.read())["error"])


    def test_ask(self):
        req = urllib.request.Request(self.base + "/ask", data=json.dumps({"question": "what is due Monday"}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            got = json.loads(r.read())
        self.assertEqual(got["route"], "due")
        self.assertIn("Prof. Lena Ortiz", got["text"])
        self.assertIn(("what is due Monday", "2026-11-14"), self.seen)
        self.assertFalse(got["pending"])
        self.assertIsNone(got["choices"])

    def test_discover_button_and_choices(self):
        self.assertIn('id="discover"', PAGE)
        self.assertIn("ask('discover'", PAGE)
        with mock.patch("discover.waiting", return_value=True):
            srv = HTTPServer(("127.0.0.1", 0), make_handler(
                today="2026-11-14", answer_fn=lambda q, today=None: Answer("Question 1 of 2: ...", "discover"),
                online_fn=lambda: False, count_fn=lambda: 0, entries_fn=lambda: []))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{srv.server_port}/ask",
                                             data=b'{"question": "discover"}', method="POST",
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req) as r:
                    got = json.loads(r.read())
            finally:
                srv.shutdown()
                srv.server_close()
        self.assertTrue(got["pending"])
        self.assertEqual([w for _, w in got["choices"]], ["yes", "no", "skip", "stop"])



class FakeVoice:
    def __init__(self):
        self.calls = []

    def listen(self, wait_for_stop=input):
        self.calls.append("start")
        wait_for_stop()
        self.calls.append("stop")
        return "what is due Monday"

    def close(self):
        self.calls.append("close")


class Talk(unittest.TestCase):
    def test_hold_to_talk(self):
        from reason.speech import HoldToTalk
        v = FakeVoice()
        t = HoldToTalk(v)
        t.start()
        self.assertEqual(v.calls, ["start"])  # recording, waiting for release
        self.assertEqual(t.stop(), {"text": "what is due Monday"})
        self.assertEqual(v.calls, ["start", "stop"])

    def test_chat_loop_spoken_question(self):
        import io
        from contextlib import redirect_stdout
        from reason import __main__ as loop
        v = FakeVoice()
        inputs = iter(["", "", "quit"])  # empty line = talk, Enter = stop, quit
        asked = []
        with mock.patch("reason.__main__.start_voice", return_value=(v, None)), \
             mock.patch("builtins.input", lambda *a: next(inputs)), \
             mock.patch("reason.__main__.ask", lambda q, today: asked.append(q)), \
             redirect_stdout(io.StringIO()) as out:
            loop.main([])
        self.assertEqual(asked, ["what is due Monday"])
        self.assertIn("you (spoken)> what is due Monday", out.getvalue())

    def test_chat_loop_without_voice(self):
        import io
        from contextlib import redirect_stdout
        from reason import __main__ as loop
        inputs = iter(["", "what is due Monday", "quit"])
        asked = []
        with mock.patch("reason.__main__.start_voice", return_value=(None, "no key")), \
             mock.patch("builtins.input", lambda *a: next(inputs)), \
             mock.patch("reason.__main__.ask", lambda q, today: asked.append(q)), \
             redirect_stdout(io.StringIO()) as out:
            loop.main([])
        self.assertEqual(asked, ["what is due Monday"])
        self.assertIn("Voice is unavailable (no key)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
