"""Follow-ups (reason/session.py, playbooks/followup.md) and spoken answers (reason/speak.py).

No model server, no network: every model call fails the test.
"""
from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
import urllib.request
from contextlib import redirect_stdout
from datetime import date, datetime
from http.server import HTTPServer
from pathlib import Path
from unittest import mock

from bank import store
from reason import Answer, answer
from reason import act
from reason.session import Session, resolve
from reason.speak import Speaker, speakable
from reason.tests.test_reason import ENTRIES, E

SAT = date(2026, 11, 14)
CANVAS = E("c00000000001", "course", "INFO 3361 Data Stories", None, "2026-11-13", "Reading Quiz",
           "A quiz on color and scale.", ask="Submit reading quiz", kind="canvas",
           source="file:///tmp/canvas/50021.html",
           deadlines=[{"phrase": "Monday 9am", "date": "2026-11-16", "time": "09:00"}])


def no_model(*a, **k):
    raise AssertionError("no model call in a follow-up")


class FakeCal:
    def __call__(self, start, end):
        d = datetime(2026, 11, 20, 14) if start <= date(2026, 11, 20) <= end else None
        return [{"title": "Office hours", "start": d, "end": d.replace(hour=15),
                 "location": "Upson 225", "all_day": False}] if d else []


class Followups(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for e in ENTRIES + [CANVAS]:
            store.write_entry(dict(e), self.root)
        self.s = Session()
        act.reset()
        self.patches = [mock.patch("llm.client.complete", no_model),
                        mock.patch("llm.client.complete_json", no_model)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        act.reset()
        self.tmp.cleanup()

    def ask(self, q):
        return answer(q, SAT, root=self.root, session=self.s, _events=FakeCal(),
                      _now=datetime(2026, 11, 14, 8), _online=lambda: False)

    def test_new_date_reruns_due(self):
        self.assertEqual(self.ask("what is due Monday").route, "due")
        a = self.ask("and Tuesday?")
        self.assertEqual(a.route, "due")
        self.assertIn("Due Tue Nov 17", a.text)
        self.assertIn("Emily", a.text)
        a = self.ask("- What about next week?")  # voice puts a dash first
        self.assertIn("Due next week", a.text)

    def test_new_date_reruns_calendar(self):
        self.assertEqual(self.ask("what's on my calendar tomorrow").route, "calendar")
        a = self.ask("what about Friday?")
        self.assertEqual(a.route, "calendar")
        self.assertIn("Office hours", a.text)
        a = self.ask("when is it on?")
        self.assertEqual(a.route, "followup")
        self.assertIn("It's on Fri Nov 20 2pm", a.text)
        a = self.ask("who sent that?")
        self.assertIn("event on your calendar", a.text)

    def test_new_name_reruns_person(self):
        self.assertEqual(self.ask("what did Emily ask me").route, "person")
        a = self.ask("and Will?")
        self.assertEqual(a.route, "person")
        self.assertIn("Reply to Will if you can come", a.text)
        a = self.ask("and Priya?")
        self.assertEqual(a.text, "I have nothing from Priya.")

    def test_rows(self):
        a = self.ask("what is due Monday")
        self.assertEqual(len(a.rows), 2)
        self.assertIn("Which one?", self.ask("who sent that?").text)
        a = self.ask("the second one")
        self.assertEqual(a.route, "followup")
        self.assertIn("Submit your final notebook", a.text)
        self.assertIn("Source: Prof. Daniel Reyes, Nov 12", a.text)
        self.assertIn("Prof. Daniel Reyes sent it on Nov 12", self.ask("who sent that?").text)
        self.assertIn("Due Mon Nov 16 11:59pm", self.ask("when is it due?").text)
        self.assertIn("only listed 2", self.ask("the fifth one").text)
        self.assertIn("Canvas", self.ask("who sent the first one?").text)

    def test_open_it_goes_through_act(self):
        self.ask("what is due Monday")
        self.ask("the first one")
        a = self.ask("open it")
        self.assertEqual(a.route, "act")
        self.assertIn("I'll open this page", a.text)
        self.assertTrue(act.waiting())
        self.assertIn("Cancelled", self.ask("no").text)
        a = self.ask("open the second one")  # mail: Apple Mail first (playbooks/open.md), held for a yes
        self.assertIn("in Mail", a.text)
        self.assertTrue(act.waiting())
        self.assertIn("Cancelled", self.ask("no").text)

    def test_not_followups(self):
        self.ask("what is due Monday")
        for q in ("what is the capital of Peru", "and the weather?", "open the calendar",
                  "who is Emily?", "remember that my lab is Tuesdays"):
            self.assertIsNone(resolve(q, self.s, SAT, self.root), q)
        self.assertEqual(self.ask("open the calendar").route, "act")  # the act route's own preview

    def test_saved_and_loaded(self):
        self.ask("what's on my calendar next week")
        self.ask("what is due Monday")
        self.ask("the first one")
        d = json.loads(json.dumps(self.s.to_dict()))  # plain JSON
        self.assertEqual(d["title"], "what's on my calendar next week")
        self.assertEqual([t["route"] for t in d["turns"]], ["calendar", "due", "followup"])
        self.assertIn("Submit", d["turns"][2]["text"])
        self.assertTrue(d["id"] and d["started"])
        s2 = Session.from_dict(d)
        a = answer("who sent that?", SAT, root=self.root, session=s2)
        self.assertIn("Canvas", a.text)  # follow-ups go on from where it left off
        s3 = Session.from_dict(json.loads(json.dumps(Session.from_dict(d).to_dict())))
        self.assertEqual(s3.turns, d["turns"])

    def test_calendar_rows_survive_json(self):
        self.ask("what's on my calendar next week")
        s2 = Session.from_dict(json.loads(json.dumps(self.s.to_dict())))
        a = answer("when is it on?", SAT, root=self.root, session=s2)
        self.assertIn("It's on Fri Nov 20 2pm", a.text)

    @mock.patch("reason.answer._bank", lambda *a: None)  # the bank judge is a model call
    def test_unrelated_answer_ends_the_rows(self):
        self.ask("what is due Monday")
        self.assertEqual(self.ask("is the gym open on thanksgiving").route, "offline")
        self.assertIsNone(resolve("the first one", self.s, SAT, self.root))
        self.assertIsNone(resolve("and tomorrow?", self.s, SAT, self.root))

    @mock.patch("reason.answer._bank", lambda *a: None)
    def test_no_session_no_followups(self):
        a = answer("and Tuesday?", SAT, root=self.root, _online=lambda: False)
        self.assertEqual(a.route, "offline")

    def test_nothing_written(self):
        before = sorted(p.name for p in self.root.rglob("*"))
        self.ask("what is due Monday")
        self.ask("and Tuesday?")
        self.ask("the first one")
        self.assertEqual(sorted(p.name for p in self.root.rglob("*")), before)


class FakeProc:
    def __init__(self, *a, **k):
        self.args, self.stdin, self.alive = a[0], io.BytesIO(), True
        self.stdin.close = lambda: None
        FakeProc.made.append(self)

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.alive = False

    def wait(self, timeout=None):
        return 0


class Speaking(unittest.TestCase):
    def setUp(self):
        FakeProc.made = []

    def test_speakable_drops_source(self):
        text = "Due Mon Nov 16:\n- 9am  Submit reading quiz (INFO 3361, Nov 15)\n    A quiz.\nSource: x, Nov 1"
        out = speakable(text)
        self.assertNotIn("Source", out)
        self.assertIn("9am, Submit reading quiz", out)
        self.assertTrue(out.startswith("Due Mon Nov 16:"))

    def test_speak_then_stop(self):
        sp = Speaker(cmd="say", popen=FakeProc)
        self.assertTrue(sp.speak("Hello.\nSource: me"))
        self.assertEqual(FakeProc.made[0].args, ["say", "-f", "-"])
        self.assertEqual(FakeProc.made[0].stdin.getvalue(), b"Hello.")
        sp.speak("Again.")  # a new answer cuts off the old one
        self.assertFalse(FakeProc.made[0].alive)
        sp.stop()
        self.assertFalse(sp.speaking())
        self.assertFalse(sp.speak("Source: only"))

    def test_window_speaks_when_asked_and_talk_stops_it(self):
        sp = mock.Mock()
        talk = mock.Mock()
        srv = HTTPServer(("127.0.0.1", 0), make := __import__("reason.web", fromlist=["x"]).make_handler(
            answer_fn=lambda q, today=None: Answer("Hi.\nSource: x", "due"), online_fn=lambda: False,
            count_fn=lambda: 0, talk=talk, speaker=sp))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def post(path, body=None):
            req = urllib.request.Request(base + path, data=json.dumps(body or {}).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read())
        try:
            post("/ask", {"question": "x"})
            sp.speak.assert_not_called()
            post("/ask", {"question": "x", "speak": True})
            sp.speak.assert_called_once_with("Hi.\nSource: x")
            sp.stop.reset_mock()
            post("/listen/start")
            sp.stop.assert_called()
            sp.stop.reset_mock()
            self.assertEqual(post("/speak/stop"), {"ok": True})
            sp.stop.assert_called()
        finally:
            srv.shutdown()

    def test_window_keeps_one_session(self):
        from reason import web
        seen = []
        with mock.patch.object(web, "_answer", lambda q, today=None, session=None: seen.append(session) or Answer("ok", "due")):
            h = web.make_handler(online_fn=lambda: False, count_fn=lambda: 0)
            srv = HTTPServer(("127.0.0.1", 0), h)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            try:
                for _ in range(2):
                    urllib.request.urlopen(urllib.request.Request(
                        base + "/ask", data=b'{"question": "x"}', method="POST")).read()
            finally:
                srv.shutdown()
        self.assertIsInstance(seen[0], Session)
        self.assertIs(seen[0], seen[1])

    def test_page_has_speak_switch(self):
        from reason.web import PAGE
        self.assertIn('id="speak"', PAGE)
        self.assertIn("speak: speakOn", PAGE)

    def test_chat_loop_speak_flag_and_talk_stops_it(self):
        from reason import __main__ as loop

        class V:
            def listen(self, wait_for_stop):
                return "what is due Monday"

            def close(self):
                pass
        sp = mock.Mock()
        inputs = iter(["what is due Monday", "", "quit"])
        with mock.patch("reason.__main__.start_voice", return_value=(V(), None)), \
             mock.patch("reason.__main__.Speaker", return_value=sp), \
             mock.patch("reason.__main__.answer", lambda q, today=None, session=None: Answer("Hi.", "due")), \
             mock.patch("builtins.input", lambda *a: next(inputs)), \
             redirect_stdout(io.StringIO()):
            loop.main(["--speak"])
        self.assertEqual(sp.speak.call_count, 2)
        self.assertGreaterEqual(sp.stop.call_count, 3)  # before each ask, on talk, on quit
        loop.SPEAKER = None


if __name__ == "__main__":
    unittest.main()
