"""Acting route: parse, preview, yes/no, offline draft, allowlist, test account. Harness mocked.

No model server, no network, no browser, nothing opened.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from bank import store
from reason import act, answer
from reason.playbook import say
from reason.tests.test_reason import E

FELIX = E("b00000000001", "person", "Felix Wu", "felix.wu@example.com", "2026-11-13",
          "Study group Sunday?", "Felix asked if you can join the study group Sunday at 3pm.",
          ask="Tell Felix if you can come on Sunday.")
PAGE = E("b00000000002", "course", "Canvas", None, "2026-11-12", "HW 9 assignment",
         "Homework 9 covers sections 5.1 to 5.3.", kind="page",
         source="http://localhost:8800/courses/1/assignments/9")


class Act(unittest.TestCase):
    def setUp(self):
        act.reset()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for e in (FELIX, PAGE):
            store.write_entry(dict(e), self.root)
        self.calls = []
        self.deps = {
            "online": lambda: True,
            "open_app": lambda app: self.calls.append(("open_app", app)) or f"Opened {app}.",
            "open_page": lambda url: self.calls.append(("open_page", url)) or f"Opened {url}.",
            "save_draft": lambda to, s, b: self.calls.append(("draft", to, s, b)) or "Saved.",
            "write_reply": lambda gist, e: "Hi Felix,\nYes, I can come on Sunday.",
        }

    def tearDown(self):
        act.reset()
        self.tmp.cleanup()

    def h(self, q, **over):
        return act.handle(q, root=self.root, deps={**self.deps, **over})

    # ---- parse
    def test_parse(self):
        self.assertEqual(act.parse("draft a reply to Felix saying yes"),
                         {"kind": "draft", "name": "Felix", "gist": "yes"})
        self.assertEqual(act.parse("Write a reply to felix that I can't make it.")["gist"],
                         "I can't make it")
        self.assertEqual(act.parse("reply to Felix")["gist"], "")
        self.assertEqual(act.parse("Open my calendar."), {"kind": "open", "target": "calendar"})
        self.assertEqual(act.parse("open the assignment page")["target"], "assignment page")
        for q in ("what did Felix ask", "is the gym open on Thanksgiving", "what is due Monday",
                  "show me what's due", "when does the library open"):
            self.assertIsNone(act.parse(q), q)

    def test_not_an_action_is_none(self):
        self.assertIsNone(self.h("what did Felix ask"))

    # ---- open an app
    def test_open_app_waits_for_yes(self):
        a = self.h("open my calendar")
        self.assertEqual(a.route, "act")
        self.assertIn("I'll open Calendar.", a.text)
        self.assertIn(say("act", "ask_yes"), a.text)
        self.assertTrue(act.waiting())
        self.assertEqual(self.calls, [])
        a = self.h("Yes.")
        self.assertEqual(a.text, "Opened Calendar.")
        self.assertEqual(self.calls, [("open_app", "Calendar")])
        self.assertFalse(act.waiting())

    def test_open_app_works_offline(self):
        self.h("open calendar", online=lambda: False)
        self.h("yes", online=lambda: False)
        self.assertEqual(self.calls, [("open_app", "Calendar")])

    def test_no_cancels(self):
        self.h("open notes")
        self.assertEqual(self.h("no").text, say("act", "cancelled"))
        self.assertEqual(self.h("yes").text, say("act", "nothing_held"))
        self.assertEqual(self.calls, [])

    def test_other_input_drops_the_held_action(self):
        self.h("open notes")
        self.assertIsNone(self.h("what is due Monday"))
        self.assertEqual(self.h("yes").text, say("act", "nothing_held"))
        self.assertEqual(self.calls, [])

    def test_held_action_expires(self):
        self.h("open notes")
        with mock.patch("reason.act.time.monotonic", return_value=act._held.at + act.TTL + 1):
            self.assertEqual(self.h("yes").text, say("act", "nothing_held"))
        self.assertEqual(self.calls, [])

    def test_app_not_on_list_is_refused(self):
        a = self.h("open Terminal")
        self.assertIn("I can only open", a.text)
        self.assertFalse(act.waiting())

    def test_open_app_uses_partner_policy(self):
        with mock.patch("harness.computer.tools.direct.open_app", return_value=(True, "")) as op, \
             tempfile.TemporaryDirectory() as home, \
             mock.patch("harness.config.HOME_DIR", Path(home)):
            self.assertEqual(act.open_app("Calendar"), "Opened Calendar.")
            op.assert_called_once_with("Calendar")
            self.assertIn("I couldn't open Terminal", act.open_app("Terminal"))
            op.assert_called_once()
            self.assertIn("ALLOW\tCalendar\topen", (Path(home) / "actions.log").read_text())

    # ---- open a saved page
    def test_open_page(self):
        a = self.h("open the assignment page")
        self.assertIn(PAGE["source"], a.text)
        self.h("yes")
        self.assertEqual(self.calls, [("open_page", PAGE["source"])])

    def test_open_page_picks_canvas_due_soonest(self):
        def C(i, title, due):
            return E(f"c0000000000{i}", "course", "HIST 2140 Maps and Empires", None, "2026-11-10",
                     title, f"{title} for HIST 2140.", kind="canvas",
                     source=f"file:///tmp/canvas/hist2140/{i}.html",
                     deadlines=[{"phrase": due, "date": due, "time": "23:59"}])
        for e in (C(1, "Map essay", "2026-11-20"), C(2, "Reading response", "2026-11-17"),
                  C(3, "Old quiz", "2026-11-01")):
            store.write_entry(dict(e), self.root)
        a = act.handle("open the assignment page", today=date(2026, 11, 14), root=self.root, deps=self.deps)
        self.assertIn("Reading response", a.text)
        self.assertIn("file:///tmp/canvas/hist2140/2.html", a.text)
        a = act.handle("open the map essay assignment", today=date(2026, 11, 14), root=self.root,
                       deps=self.deps)
        self.assertIn("1.html", a.text)

    def test_open_page_none_saved(self):
        self.assertIn("don't have a saved link", self.h("open the syllabus page").text)

    def test_open_page_only_web_links(self):
        self.assertIn("only open web or file links", act.open_page("javascript:alert(1)"))

    # ---- draft a reply
    def test_draft_preview_then_yes(self):
        a = self.h("draft a reply to Felix saying yes")
        for part in ("felix.wu@example.com", "Subject: Re: Study group Sunday?",
                     "Yes, I can come on Sunday.", "It won't be sent", act.TEST_ACCOUNT):
            self.assertIn(part, a.text)
        self.assertEqual(self.calls, [])
        self.h("yep")
        self.assertEqual(self.calls, [("draft", "felix.wu@example.com", "Study group Sunday?",
                                       "Hi Felix,\nYes, I can come on Sunday.")])

    def test_draft_offline_says_it_needs_a_connection(self):
        a = self.h("draft a reply to Felix saying yes", online=lambda: False)
        self.assertEqual(a.text, say("act", "needs_net"))
        self.assertFalse(act.waiting())

    def test_draft_unknown_sender(self):
        a = self.h("draft a reply to Zed saying yes")
        self.assertIn("I have nothing from Zed", a.text)
        self.assertFalse(act.waiting())

    def test_draft_model_down(self):
        def boom(g, e):
            raise RuntimeError("server down")
        a = self.h("draft a reply to Felix saying yes", write_reply=boom)
        self.assertIn("Nothing was drafted", a.text)
        self.assertFalse(act.waiting())

    def _gmail(self, title, rows, reply_out="OK draft saved | to felix.wu@example.com"):
        page = SimpleNamespace(title=lambda: title)
        session = SimpleNamespace(start=lambda: SimpleNamespace(page=page))
        reply = mock.Mock(return_value=reply_out)
        patches = [mock.patch("harness.browser.session.get_session", return_value=session),
                   mock.patch("harness.email.status.signed_in", return_value=True),
                   mock.patch("harness.email.search.search"),
                   mock.patch("harness.email.search.last_rows", return_value=rows),
                   mock.patch("harness.email.draft.reply", reply)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return reply

    def row(self, n, subject):
        return SimpleNamespace(n=n, subject=subject)

    def test_save_draft_test_account_only(self):
        reply = self._gmail("Inbox - someone.real@gmail.com - Gmail", [self.row(1, "x")])
        out = act.save_draft("felix.wu@example.com", "Study group Sunday?", "Hi")
        self.assertIn("not ilovelocalai@gmail.com", out)
        reply.assert_not_called()

    def test_save_draft_picks_matching_thread(self):
        reply = self._gmail("Inbox (2) - ilovelocalai@gmail.com - Gmail",
                            [self.row(1, "Other"), self.row(2, "Re: Study group Sunday?")])
        out = act.save_draft("felix.wu@example.com", "Study group Sunday?", "Hi")
        reply.assert_called_once_with(2, "Hi")
        self.assertIn("It was not sent", out)
        self.assertNotIn("WARNING", out)

    def test_save_draft_warns_on_other_recipient(self):
        self._gmail("ilovelocalai@gmail.com - Gmail", [self.row(1, "Study group Sunday?")],
                    reply_out="OK draft saved | to someone@else.com")
        self.assertIn("WARNING", act.save_draft("felix.wu@example.com", "Study group Sunday?", "Hi"))

    def test_save_draft_reports_harness_error(self):
        self._gmail("ilovelocalai@gmail.com - Gmail", [self.row(1, "s")],
                    reply_out="ERR mail.google.com | draft did not save")
        self.assertIn("wasn't saved", act.save_draft("felix.wu@example.com", "s", "Hi"))

    # ---- wiring and safety
    def test_answer_routes_actions_first(self):
        # A typed "draft a reply to X" now opens the offline draft box (playbooks/compose.md,
        # brief W); it still comes before the person route, which would match "Felix".
        with mock.patch("reason.compose.write_reply", return_value="Hi Felix,\nYes."):
            a = answer("draft a reply to Felix saying yes", root=self.root)
        self.assertEqual(a.route, "compose")
        self.assertEqual(a.draft["to"], "felix.wu@example.com")

    def test_never_sends(self):
        src = Path(act.__file__).read_text()
        code = "\n".join(ln for ln in src.splitlines() if not ln.strip().startswith("#"))
        self.assertIsNone(re.search(r"\bsend\w*\s*\(|\.send\b|aria-label=.Send", code))


if __name__ == "__main__":
    unittest.main()
