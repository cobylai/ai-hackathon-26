"""Saved chats (reason/chats.py) and the window's /chats endpoints. No model, no network."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from http.server import HTTPServer
from pathlib import Path
from unittest import mock

from bank import store
from reason import Answer, answer, chats
from reason.session import Session
from reason.tests.test_reason import ENTRIES
from reason.tests.test_session import CANVAS, SAT, no_model


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "chats"

    def tearDown(self):
        self.tmp.cleanup()

    def chat(self, *qs):
        s = Session()
        for q in qs:
            s.record(q, Answer(f"answer to {q}", "due", ["/x.md"], 0.1))
        return s

    def test_empty_chat_is_not_written(self):
        self.assertIsNone(chats.save(Session(), self.root))
        self.assertEqual(chats.listing(self.root), [])

    def test_save_load_delete(self):
        s = self.chat("what's due tomorrow", "and Friday?")
        p = chats.save(s, self.root)
        self.assertEqual(p, self.root / f"{s.id}.json")
        self.assertFalse(list(self.root.glob("*.tmp")))
        s2 = chats.load(s.id, self.root)
        self.assertEqual(s2.title, "what's due tomorrow")
        self.assertEqual([t["question"] for t in s2.turns], ["what's due tomorrow", "and Friday?"])
        self.assertEqual(chats.read(s.id, self.root)["turns"][1]["text"], "answer to and Friday?")
        self.assertTrue(chats.delete(s.id, self.root))
        self.assertFalse(p.exists())
        self.assertFalse(chats.delete(s.id, self.root))

    def test_listing_newest_first(self):
        a, b = self.chat("first chat"), self.chat("second chat")
        a.turns[-1]["at"], b.turns[-1]["at"] = "2026-11-15T09:00:00", "2026-11-14T09:00:00"
        chats.save(a, self.root), chats.save(b, self.root)
        (self.root / "junk.json").write_text("{not json")
        got = chats.listing(self.root)
        self.assertEqual([c["title"] for c in got], ["first chat", "second chat"])
        self.assertEqual(got[0]["turns"], 1)

    def test_bad_ids_are_refused(self):
        for bad in ("../x", "a/b", "", "XYZ"):
            with self.assertRaises(ValueError):
                chats.load(bad, self.root)

    def test_folder_is_outside_the_repo(self):
        clean = {k: v for k, v in os.environ.items() if k not in ("FLUX_CHATS_DIR", "MUSE_CHATS_DIR")}
        with mock.patch.dict(os.environ, {**clean, "FLUX_BANK_DIR": "/tmp/somewhere/flux-demo-bank"}, clear=True):
            self.assertEqual(chats.folder(), Path("/tmp/somewhere").resolve() / "flux-demo-bank-chats")
        with mock.patch.dict(os.environ, {**clean, "FLUX_BANK_DIR": str(chats.REPO / "data" / "bank")}, clear=True):
            self.assertEqual(chats.folder(), Path.home() / "flux-chats")  # computed only, nothing written
        with mock.patch.dict(os.environ, {"FLUX_CHATS_DIR": "/tmp/x-chats"}):
            self.assertEqual(chats.folder(), Path("/tmp/x-chats"))

    def test_saved_turn_keeps_the_words_said(self):
        tmp = Path(self.tmp.name) / "bank"
        for e in ENTRIES + [CANVAS]:
            store.write_entry(dict(e), tmp)
        s = Session()
        with mock.patch("llm.client.complete", no_model), mock.patch("llm.client.complete_json", no_model):
            answer("what did Emily ask me", SAT, root=tmp, session=s)
            answer("and Will?", SAT, root=tmp, session=s)
        self.assertEqual(s.turns[1]["question"], "and Will?")
        self.assertIn("Will", s.turns[1]["text"])


class NeverHome(unittest.TestCase):
    """reason/tests/__init__.py points the chats folder and the bank at a temp dir."""

    def test_folders_are_temporary(self):
        tmp = Path(tempfile.gettempdir()).resolve()
        for p in (chats.folder(), store.bank_dir()):
            p = p.resolve()
            self.assertIn(tmp, p.parents, p)
            self.assertNotIn(Path.home() / "flux-chats", [p, *p.parents])

    def test_a_handler_without_chats_root_saves_in_the_temp_folder(self):
        from reason.web import make_handler
        s = Session()
        srv = HTTPServer(("127.0.0.1", 0), make_handler(
            answer_fn=lambda q, today=None: (s.record(q, Answer("ok", "due")), Answer("ok", "due"))[1],
            online_fn=lambda: False, count_fn=lambda: 0, session=s))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"http://127.0.0.1:{srv.server_address[1]}/ask", data=b'{"question": "x"}', method="POST")).read()
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertTrue((chats.folder() / f"{s.id}.json").exists())
        chats.delete(s.id)


class Window(unittest.TestCase):
    """The window keeps one open chat; new / open / delete swap it. Answers are saved."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "chats"
        self.bank = Path(self.tmp.name) / "bank"
        for e in ENTRIES + [CANVAS]:
            store.write_entry(dict(e), self.bank)
        self.patches = [mock.patch("llm.client.complete", no_model),
                        mock.patch("llm.client.complete_json", no_model),
                        mock.patch("reason.web._answer", self.real_answer),
                        mock.patch("reason.answer._bank", lambda *a: None)]  # the bank judge is a model call
        for p in self.patches:
            p.start()
        from reason.web import make_handler
        self.srv = HTTPServer(("127.0.0.1", 0), make_handler(
            today="2026-11-14", online_fn=lambda: False, count_fn=lambda: 0, chats_root=self.root))
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def real_answer(self, q, today=None, session=None):
        return answer(q, SAT, root=self.bank, session=session, _online=lambda: False,
                      _now=datetime(2026, 11, 14, 8))

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def req(self, path, body=None, method=None):
        data = None if body is None and method != "POST" else json.dumps(body or {}).encode()
        r = urllib.request.Request(self.base + path, data=data, method=method or ("POST" if data else "GET"))
        with urllib.request.urlopen(r) as resp:
            return json.loads(resp.read())

    def ask(self, q):
        return self.req("/ask", {"question": q})

    def test_saved_reopened_and_deleted(self):
        self.assertEqual(self.req("/chats")["chats"], [])
        self.ask("what is due Monday")
        self.ask("the first one")
        listing = self.req("/chats")
        first = listing["current"]
        self.assertEqual([c["title"] for c in listing["chats"]], ["what is due Monday"])
        self.assertTrue((self.root / f"{first}.json").exists())

        new = self.req("/chats/new", method="POST")["current"]
        self.assertNotEqual(new, first)
        self.assertNotEqual(self.ask("who sent that?")["route"], "followup")  # a new chat has no rows

        saved = self.req(f"/chats/{first}/open", method="POST")
        self.assertEqual([t["question"] for t in saved["turns"]], ["what is due Monday", "the first one"])
        self.assertIn("Submit reading quiz", saved["turns"][1]["text"])
        r = self.ask("who sent that?")  # follow-ups go on from where the chat left off
        self.assertEqual(r["route"], "followup")
        self.assertIn("Canvas", r["text"])
        self.assertEqual(len(self.req(f"/chats/{first}")["turns"]), 3)

        r = self.req(f"/chats/{first}/delete", method="POST")
        self.assertNotEqual(r["current"], first)  # deleting the open chat starts a new one
        self.assertFalse((self.root / f"{first}.json").exists())
        self.assertNotIn(first, [c["id"] for c in self.req("/chats")["chats"]])

    def test_unknown_chat(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.req("/chats/abcdef123456/open", method="POST")
        self.assertEqual(e.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError):
            self.req("/chats/..%2Fetc/open", method="POST")

    def test_survives_a_restart(self):
        self.ask("what is due Monday")
        first = self.req("/chats")["current"]
        self.srv.shutdown()
        self.srv.server_close()
        from reason.web import make_handler  # a new server: same folder, a new open chat
        self.srv = HTTPServer(("127.0.0.1", 0), make_handler(
            today="2026-11-14", online_fn=lambda: False, count_fn=lambda: 0, chats_root=self.root))
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        listing = self.req("/chats")
        self.assertNotEqual(listing["current"], first)
        self.assertEqual([c["id"] for c in listing["chats"]], [first])
        self.req(f"/chats/{first}/open", method="POST")
        self.assertIn("Due Tue Nov 17", self.ask("and Tuesday?")["text"])

    def test_page_has_chat_hooks(self):
        from reason.web import PAGE
        self.assertIn('<nav id="chats" aria-label="Chats">', PAGE)
        for hook in ("window.fluxChats", "'newchat'", "/chats/", "chdel"):
            self.assertIn(hook, PAGE)


if __name__ == "__main__":
    unittest.main()
