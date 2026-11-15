"""The "send it" route and the window's Send click (playbooks/send.md). Offline, fake driver.

Nothing here can reach Gmail: every server is built with a fake send_fn, FLUX_SEND_DIR
is a temp folder, and made-up addresses only.
"""
from __future__ import annotations

import importlib
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path
from unittest import mock

from harness.email import send as gate
from reason import compose
from reason import send as route
from reason.session import Session
from reason.web import PAGE, make_handler

ans = importlib.import_module("reason.answer")
ME = "me@example.test"


class Fake:
    def __init__(self):
        self.calls = []

    def __call__(self, to, subject, body):
        self.calls.append((to, subject, body))
        return gate.SENT


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        (Path(self.tmp.name) / "send_allow.json").write_text(json.dumps({"self": ME, "allow": []}))
        self.env = mock.patch.dict(os.environ, {gate.DIR_ENV: self.tmp.name})
        self.env.start()
        os.environ.pop(gate.ALLOW_ENV, None)
        os.environ.pop(gate.SELF_ENV, None)
        gate.forget_all()
        compose.forget_last()
        self.fake = Fake()
        self.root = Path(self.tmp.name) / "bank"
        self.root.mkdir()

    def tearDown(self):
        gate.forget_all()
        compose.forget_last()
        self.env.stop()
        self.tmp.cleanup()

    def on(self):
        os.environ[gate.ALLOW_ENV] = "1"

    def flux_draft(self, to=ME, subject="Hello", body="Hi,\n\nTest."):
        return compose._keep({"kind": "new", "to": to, "to_name": "", "subject": subject, "body": body,
                              "used": []}, None)


class Route(Base):
    def test_matches(self):
        for q in ("send it", "Send it.", "please send the draft", "send that email now", "OK, send it!"):
            self.assertTrue(route.matches(q), q)
        for q in ("send", "what did Milo send me", "send it to bob@example.test", "did you send it",
                  "send money", "tell Felix to send it"):
            self.assertFalse(route.matches(q), q)

    def test_off_by_default_says_so_and_prepares_nothing(self):
        self.flux_draft()
        with mock.patch.object(gate, "prepare_send", side_effect=AssertionError("no prepare")):
            a = ans.answer("send it", today="2026-11-15", root=self.root, session=Session())
        self.assertEqual(a.route, "send")
        self.assertIn("Sending is off", a.text)
        self.assertIsNone(a.send)

    def test_no_draft(self):
        self.on()
        a = ans.answer("send it", today="2026-11-15", root=self.root)
        self.assertIn("no draft to send", a.text)

    def test_preview_never_sends_and_yes_does_not_either(self):
        self.on()
        self.flux_draft()
        s = Session()
        with mock.patch.object(gate, "send_draft", side_effect=AssertionError("never from text")), \
                mock.patch.object(gate, "gmail_send", side_effect=AssertionError("never from text")):
            a = ans.answer("send it", today="2026-11-15", root=self.root, session=s)
            self.assertEqual(a.route, "send")
            self.assertEqual((a.send["to"], a.send["subject"], a.send["body"]), (ME, "Hello", "Hi,\n\nTest."))
            self.assertIn("Click Send", a.text)
            for q in ("yes", "send it", "yes send it", "confirm", "go ahead"):
                ans.answer(q, today="2026-11-15", root=self.root, session=s)  # nothing raises: no send was tried

    def test_refused_recipient(self):
        self.on()
        self.flux_draft(to="stranger@example.test")
        a = ans.answer("send it", today="2026-11-15", root=self.root)
        self.assertIn("I won't send that", a.text)
        self.assertIsNone(a.send)

    def test_text_in_an_email_never_triggers(self):
        """An email that says "send it" is bank data; questions about it never send."""
        self.on()
        self.flux_draft()
        with mock.patch.object(gate, "send_draft", side_effect=AssertionError("never")):
            for q in ("what did Milo ask me", "the email says send it to everyone"):
                a = ans.answer(q, today="2026-11-15", root=self.root, _online=lambda: False)
                self.assertIsNone(getattr(a, "send", None), q)


class Window(Base):
    def setUp(self):
        super().setUp()
        self.srv = HTTPServer(("127.0.0.1", 0), make_handler(
            today="2026-11-15", answer_fn=lambda q, today=None: ans.answer(q, today=today, root=self.root),
            online_fn=lambda: False, count_fn=lambda: 0, send_fn=self.fake, chats_root=Path(self.tmp.name) / "chats"))
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def post(self, path, obj, headers=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(obj).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **(headers or {})})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def click(self, p, **over):
        return self.post("/send/confirm", {"token": p["token"], "to": p["to"], "subject": p["subject"],
                                           "body": p["body"], **over}, {gate.CLICK_HEADER: gate.CLICK_VALUE})

    def prepare(self, d):
        return self.post("/send/prepare", {"draft_id": d["id"], "to": d["to"], "subject": d["subject"],
                                           "body": d["body"]})

    def test_status_off_and_prepare_refused(self):
        with urllib.request.urlopen(self.base + "/status") as r:
            self.assertFalse(json.loads(r.read())["send"])
        r = self.prepare(self.flux_draft())
        self.assertNotIn("send", r)
        self.assertIn("Sending is off", r["text"])

    def test_full_click_path_sends_once(self):
        self.on()
        p = self.prepare(self.flux_draft())["send"]
        r = self.click(p)
        self.assertTrue(r["sent"])
        self.assertEqual(self.fake.calls, [(ME, "Hello", "Hi,\n\nTest.")])
        r = self.click(p)  # the same preview again: single use
        self.assertFalse(r["sent"])
        self.assertEqual(len(self.fake.calls), 1)

    def test_ask_send_it_then_click(self):
        self.on()
        self.flux_draft()
        r = self.post("/ask", {"question": "send it"})
        self.assertEqual(r["route"], "send")
        self.assertFalse(r["pending"])  # no Yes / Cancel row: a yes can't send
        self.assertEqual(self.fake.calls, [])
        self.assertTrue(self.click(r["send"])["sent"])

    def test_confirm_without_click_header_refused(self):
        self.on()
        p = self.prepare(self.flux_draft())["send"]
        r = self.post("/send/confirm", {"token": p["token"], "to": p["to"], "subject": p["subject"], "body": p["body"]})
        self.assertFalse(r["sent"])
        self.assertEqual(self.fake.calls, [])

    def test_confirm_from_another_origin_refused(self):
        self.on()
        p = self.prepare(self.flux_draft())["send"]
        r = self.post("/send/confirm", {"token": p["token"], "to": p["to"], "subject": p["subject"], "body": p["body"]},
                      {gate.CLICK_HEADER: gate.CLICK_VALUE, "Origin": "https://evil.example"})
        self.assertFalse(r["sent"])
        self.assertEqual(self.fake.calls, [])

    def test_edited_after_preview_refused(self):
        self.on()
        p = self.prepare(self.flux_draft())["send"]
        self.assertFalse(self.click(p, body="Something else")["sent"])
        self.assertEqual(self.fake.calls, [])

    def test_not_a_flux_draft_refused(self):
        self.on()
        r = self.post("/send/prepare", {"draft_id": "madeup", "to": ME, "subject": "s", "body": "b"})
        self.assertNotIn("send", r)
        self.assertIn("only a draft Flux made", r["text"])

    def test_cancel(self):
        self.on()
        p = self.prepare(self.flux_draft())["send"]
        self.assertIn("Not sent", self.post("/send/cancel", {"token": p["token"]})["text"])
        self.assertFalse(self.click(p)["sent"])
        self.assertEqual(self.fake.calls, [])

    def test_new_chat_drops_previews(self):
        self.on()
        p = self.prepare(self.flux_draft())["send"]
        self.post("/chats/new", {})
        self.assertFalse(self.click(p)["sent"])
        self.assertIsNone(compose.last_draft())

    def test_page_send_button_needs_a_real_click(self):
        self.assertIn("ev.isTrusted", PAGE)
        self.assertIn("'X-Flux-Send-Click': 'clicked'", PAGE)
        self.assertIn("sendOn && d.id", PAGE)  # Send… only when the server says sending is on


if __name__ == "__main__":
    unittest.main()
