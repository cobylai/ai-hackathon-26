"""Suggestions, free/busy, the draft box and the compose route (brief W). Calendar and model mocked.

No model server, no network, nothing opened or sent.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import unquote

import applecal
import bank
from bank import store
from reason import answer, compose, suggest
from reason.session import Session
from reason.tests.test_reason import E

TODAY = date(2026, 11, 15)
MILO = E("c00000000001", "person", "Milo Fenn", "mfenn@example.edu", "2026-11-14", "Band practice Thursday",
         "Milo asks if the student is free for band practice on Thursday.",
         ask="Are you free for band practice Thursday, November 19 at 7pm in Lincoln Hall 101?")
GRETA = E("c00000000002", "person", "Greta Lund", "glund@example.edu", "2026-11-14", "Book club meeting",
          "Greta wants to plan the book club.", ask="Can you meet Wednesday, November 18 at 2pm?")
IVY = E("c00000000003", "person", "Ivy Moss", "imoss@example.edu", "2026-11-14", "Garden plot",
        "Ivy wants to talk about the garden plot.", ask="Can we meet sometime soon about the garden plot?")
FELIX = E("c00000000004", "person", "Felix Ambrose", "fambrose@example.edu", "2026-11-13",
          "Pay your share for the cabin", "Felix asks for the $35 share for the cabin trip.",
          ask="Send Felix your $35 share for the cabin trip.",
          deadlines=[{"phrase": "by Monday", "date": "2026-11-16", "time": None}])
HW = E("c00000000005", "course", "MATH 2940", None, "2026-11-12", "HW 9", "Homework 9, sections 5.1 to 5.3.",
       kind="canvas", source="file:///tmp/canvas/hw9.html",
       deadlines=[{"phrase": "Nov 16", "date": "2026-11-16", "time": "23:59"}])
NINA1 = E("c00000000006", "person", "Nina Valdez", "nv@example.edu", "2026-11-12", "Poster", "Poster draft.",
          ask="Review my poster.")
NINA2 = E("c00000000007", "person", "Nina Brooks", "nb@example.edu", "2026-11-11", "Carpool", "Carpool.",
          ask="Tell me about the carpool.")

LAB = {"title": "Lab", "start": datetime(2026, 11, 18, 13, 30), "end": datetime(2026, 11, 18, 15, 30),
       "location": "", "all_day": False}


def cal(day_start, day_end):
    return [LAB] if day_start <= LAB["start"].date() <= day_end else []


def no_cal(*_):
    raise applecal.CalendarError("no permission")


def no_model(*a, **k):
    raise AssertionError("no model call expected")


class Base(unittest.TestCase):
    def setUp(self):
        suggest.reset()
        compose.reset()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for e in (MILO, GRETA, IVY, FELIX, HW, NINA1, NINA2):
            store.write_entry(dict(e), self.root)
        self.p = mock.patch("llm.client.complete", side_effect=no_model)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        compose.reset()
        self.tmp.cleanup()

    def entry(self, e):
        return next(x for x in store.all_entries(self.root) if x["id"] == e["id"])

    def ask(self, q, s=None, events=cal):
        return answer(q, today=TODAY, root=self.root, session=s, _events=events)


class FreeBusy(Base):
    def test_proposed_time(self):
        self.assertEqual(suggest.proposed(MILO), datetime(2026, 11, 19, 19, 0))
        self.assertEqual(suggest.proposed(GRETA), datetime(2026, 11, 18, 14, 0))
        self.assertIsNone(suggest.proposed(IVY))
        bare = dict(GRETA, ask="Can you meet Wednesday, November 18 at 3?")
        self.assertEqual(suggest.proposed(bare), datetime(2026, 11, 18, 15, 0))

    def test_free_busy_and_slot(self):
        m = suggest.meeting(MILO, cal)
        self.assertTrue(m["free"])
        self.assertEqual(m["when"], "Thursday, Nov 19 at 7pm")
        g = suggest.meeting(GRETA, cal)
        self.assertEqual((g["free"], g["clash"], g["slot"]), (False, "Lab", "3:30pm"))

    def test_unreadable_time_or_calendar_says_nothing(self):
        self.assertIsNone(suggest.meeting(IVY, cal))
        self.assertIsNone(suggest.meeting(MILO, no_cal))


class Suggestions(Base):
    def test_meeting_lines(self):
        a = self.ask("What did Milo ask me?")
        self.assertEqual([s["line"] for s in a.suggestions],
                         ["You're free Thursday, Nov 19 at 7pm. Draft a yes to Milo?",
                          'Add "Band practice Thursday" to your calendar: Thu Nov 19 7pm'])
        a = self.ask("What did Greta ask me?")
        self.assertIn("You have Lab then", a.suggestions[0]["line"])
        self.assertNotIn("calendar", " ".join(s["kind"] for s in a.suggestions))  # busy: no event

    def test_no_time_falls_back_to_reply_without_free_busy(self):
        for events in (cal, no_cal):
            a = self.ask("What did Ivy ask me?", events=events)
            self.assertEqual(a.suggestions[0]["line"], "Draft a reply to Ivy: Garden plot")
            s = self.ask("What did Milo ask me?", events=no_cal).suggestions[0]["line"]
            self.assertNotIn("free", s.lower())

    def test_due_gives_at_most_two_and_open(self):
        a = self.ask("What's due tomorrow?")
        self.assertEqual(len(a.suggestions), 2)
        self.assertEqual([s["kind"] for s in a.suggestions], ["open", "remind"])  # the soonest item's two
        self.assertEqual(a.suggestions[1]["line"], "Remind me: HW 9 (Mon Nov 16 9:59pm)")
        self.assertTrue(all("entry" not in s for s in suggest.public(a.suggestions)))

    def test_none_when_nothing_found_or_other_routes(self):
        self.assertEqual(self.ask("What's due on Nov 30?").suggestions, [])
        self.assertEqual(self.ask("remember my lab is Tuesdays").suggestions, [])
        self.assertEqual(self.ask("hi").suggestions, [])

    def test_dismissed_stays_gone_in_that_chat_only(self):
        s = Session()
        a = self.ask("What did Milo ask me?", s)
        self.assertTrue(suggest.dismiss(a.suggestions[0]["id"]))
        self.assertEqual(self.ask("What did Milo ask me?", s).suggestions, [])
        self.assertEqual(len(self.ask("What did Milo ask me?", Session()).suggestions), 2)

    def test_take_hides_it(self):
        s = Session()
        a = self.ask("What did Greta ask me?", s)
        got = suggest.take(a.suggestions[0]["id"])
        self.assertEqual(got["entry"]["id"], GRETA["id"])
        self.assertEqual(self.ask("What did Greta ask me?", s).suggestions, [])


    def test_remind_only_on_due_and_catchup(self):
        a = self.ask("What did Felix ask me?")
        self.assertEqual([s["kind"] for s in a.suggestions], ["reply"])
        a = self.ask("What's due Monday?")
        felix = [s for s in a.suggestions if s["entry"]["id"] == FELIX["id"]]
        self.assertTrue(all(s["kind"] in ("reply", "remind") for s in felix))

    def test_click_adds_through_computer(self):
        a = self.ask("What did Milo ask me?")
        cal_s = next(s for s in a.suggestions if s["kind"] == "calendar")
        with mock.patch("reason.computer.add_event") as add:
            out = suggest.run(suggest.take(cal_s["id"]))
        ev = add.call_args[0][0]
        self.assertEqual((ev["title"], ev["start"]), ("Band practice Thursday", datetime(2026, 11, 19, 19, 0)))
        self.assertEqual(ev["location"], "Lincoln Hall 101")
        self.assertEqual(out, 'Added "Band practice Thursday" to your calendar for Thu Nov 19 7pm.')
        a = self.ask("What's due tomorrow?")
        rem = next(s for s in a.suggestions if s["kind"] == "remind")
        with mock.patch("reason.computer.add_reminder", side_effect=RuntimeError("no Reminders access")):
            self.assertEqual(suggest.run(suggest.take(rem["id"])), "That didn't work: RuntimeError: no Reminders access")


class Drafts(Base):
    def test_templates_no_model(self):
        bank.remember("my name is Coby", today=TODAY, root=self.root)
        d = compose.reply_draft(self.entry(MILO), root=self.root, events_fn=cal)
        self.assertEqual(d["to"], "mfenn@example.edu")
        self.assertEqual(d["subject"], "Re: Band practice Thursday")
        self.assertEqual(d["body"], "Hi Milo,\n\nYes, Thursday, Nov 19 at 7pm works for me. See you then.\n\nCoby")
        d = compose.reply_draft(self.entry(GRETA), root=self.root, events_fn=cal)
        self.assertIn("I have Lab then. Would 3:30pm that day work instead?", d["body"])

    def test_busy_all_day_gives_reason_only(self):
        full = [{"title": "Lab", "start": datetime(2026, 11, 18, 8), "end": datetime(2026, 11, 18, 19),
                 "location": "", "all_day": False}]
        d = compose.reply_draft(self.entry(GRETA), root=self.root, events_fn=lambda *_: full)
        self.assertIn("Could we find another time?", d["body"])
        self.assertNotIn("\n\nCoby", d["body"])  # no name note: no sign-off

    def test_other_reply_uses_model(self):
        d = compose.reply_draft(self.entry(FELIX), "I'll pay Monday", root=self.root,
                                writer=lambda gist, e: f"Hi Felix,\n{gist}.")
        self.assertEqual(d["body"], "Hi Felix,\nI'll pay Monday.")
        self.assertEqual(d["used"], ["Felix Ambrose, Nov 13"])

    def test_mailto_is_plain_text(self):
        url = compose.mailto("a@b.edu", "Re: Band & practice", "Hi Milo,\n\nYes?")
        self.assertTrue(url.startswith("mailto:a@b.edu?subject="))
        self.assertNotIn("\n", url)
        self.assertIn("body=Hi%20Milo%2C%0A%0AYes%3F", url)
        self.assertEqual(unquote(url.split("subject=")[1].split("&")[0]), "Re: Band & practice")
        ran = []
        out = compose.open_in_mail("a@b.edu", "s", "b", runner=lambda u: ran.append(u) or SimpleNamespace(returncode=0))
        self.assertEqual(ran, [compose.mailto("a@b.edu", "s", "b")])
        self.assertIn("Nothing was sent", out)

    def test_never_sends(self):
        for mod in (compose, suggest):
            src = Path(mod.__file__).read_text()
            code = "\n".join(ln for ln in src.splitlines() if not ln.strip().startswith("#"))
            self.assertIsNone(re.search(r"\bsend\w*\s*\(|\.send\b|smtplib", code), mod.__name__)


class Compose(Base):
    def test_parse(self):
        self.assertEqual(compose.parse("Draft a reply to Milo"), {"reply": True, "name": "Milo", "gist": ""})
        self.assertEqual(compose.parse("write a reply to Felix saying I'll pay Monday.")["gist"], "I'll pay Monday")
        self.assertEqual(compose.parse("write an email to Felix about the cabin"),
                         {"reply": False, "name": "Felix", "gist": "the cabin"})
        self.assertEqual(compose.parse("draft an email about the study room"),
                         {"reply": False, "name": None, "gist": "the study room"})
        self.assertIsNone(compose.parse("draft a reply to Felix in Gmail"))
        for q in ("what did Felix ask", "remember to write an email", "yes", "open my calendar"):
            self.assertIsNone(compose.parse(q), q)

    def test_typed_reply_is_a_draft_box(self):
        a = self.ask("Draft a reply to Milo")
        self.assertEqual(a.route, "compose")
        self.assertIn("Yes, Thursday, Nov 19 at 7pm", a.draft["body"])
        self.assertIn("To: mfenn@example.edu", a.text)

    def test_unknown_reply_name(self):
        a = self.ask("Draft a reply to Priya")
        self.assertEqual(a.text, "I have nothing from Priya, so there's no email to reply to.")

    def test_who_then_more_then_draft(self):
        w = lambda topic, to, notes, greeting: {"subject": "Cabin money", "body": f"{greeting}\nAbout {topic}."}
        with mock.patch("reason.compose.write_new", side_effect=w):
            self.assertEqual(self.ask("write an email").text, "Who is this to?")
            self.assertEqual(self.ask("Felix").text, "What should it say?")
            a = self.ask("about the cabin trip money")
        self.assertEqual(a.route, "compose")
        self.assertEqual((a.draft["to"], a.draft["subject"]), ("fambrose@example.edu", "Cabin money"))
        self.assertIn("Felix Ambrose, Nov 13", a.draft["used"])

    def test_unknown_topic_tell_me_more(self):
        seen = {}
        def w(topic, to, notes, greeting):
            seen["notes"] = notes
            return {"subject": "Lunch", "body": f"{greeting}\nLunch Friday?"}
        with mock.patch("reason.compose.write_new", side_effect=w):
            a = self.ask("write an email to Felix about lunch")
            self.assertEqual(a.text, "I don't have anything about lunch. Tell me a little more: what should it say?")
            a = self.ask("ask if he wants lunch Friday")
        self.assertEqual(a.draft["to"], "fambrose@example.edu")
        self.assertIn("The student said: ask if he wants lunch Friday", seen["notes"])
        self.assertEqual(a.draft["used"], ["what you said"])

    def test_unknown_name_leaves_to_empty(self):
        w = lambda topic, to, notes, greeting: {"subject": "Cabin", "body": f"{greeting}\nCabin."}
        with mock.patch("reason.compose.write_new", side_effect=w):
            a = self.ask("write an email to Zed about the cabin trip")
            self.assertEqual(a.text, "I don't have anyone called Zed. Who is this to?")
            a = self.ask("Zed Park")
        self.assertEqual(a.draft["to"], "")
        self.assertIn("To is empty", a.text)

    def test_which_nina(self):
        a = self.ask("write an email to Nina about the poster")
        self.assertTrue(a.text.startswith("Which Nina?"))
        with mock.patch("reason.compose.write_new",
                        side_effect=lambda *a_: {"subject": "Poster", "body": "Hi Nina,\nPoster."}):
            a = self.ask("Valdez")
        self.assertEqual(a.draft["to"], "nv@example.edu")

    def test_yes_and_new_questions_drop_the_hold(self):
        self.ask("write an email")
        self.assertEqual(self.ask("yes").route, "act")
        self.ask("write an email")
        self.assertEqual(self.ask("What did Greta ask me?").route, "person")


if __name__ == "__main__":
    unittest.main()


class WindowEndpoints(Base):
    def test_ask_suggest_dismiss_draft_open(self):
        import json
        import threading
        import urllib.request
        from http.server import HTTPServer
        from reason.web import PAGE, make_handler
        s, opened, mailed = Session(), [], []
        srv = HTTPServer(("127.0.0.1", 0), make_handler(
            answer_fn=lambda q, today=None: answer(q, today=TODAY, root=self.root, session=s, _events=cal),
            online_fn=lambda: False, count_fn=lambda: 7, entries_fn=lambda: [], session=s,
            mail_fn=lambda u: mailed.append(u) or SimpleNamespace(returncode=0),
            open_fn=lambda url: opened.append(url) or f"Opened {url}.",
            draft_fn=lambda e: compose.reply_draft(e, root=self.root, events_fn=cal)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def post(path, obj=None):
            req = urllib.request.Request(base + path, data=json.dumps(obj or {}).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read())
        try:
            r = post("/ask", {"question": "What's due tomorrow?"})
            self.assertEqual(len(r["suggestions"]), 2)
            self.assertEqual(set(r["suggestions"][0]), {"id", "line", "button", "kind"})
            op = next(x for x in r["suggestions"] if x["kind"] == "open")
            self.assertEqual(post(f"/suggest/{op['id']}")["text"], "Opened file:///tmp/canvas/hw9.html.")
            self.assertEqual(opened, ["file:///tmp/canvas/hw9.html"])
            self.assertIn("isn't available", post(f"/suggest/{op['id']}")["text"])
            r = post("/ask", {"question": "What did Greta ask me?"})
            d = post(f"/suggest/{r['suggestions'][0]['id']}")["draft"]
            self.assertIn("I have Lab then", d["body"])
            r = post("/ask", {"question": "What did Ivy ask me?"})
            self.assertTrue(post(f"/suggest/{r['suggestions'][0]['id']}/dismiss")["ok"])
            self.assertEqual(post("/ask", {"question": "What did Ivy ask me?"})["suggestions"], [])
            out = post("/draft/open", {"to": d["to"], "subject": d["subject"], "body": d["body"]})
            self.assertIn("Nothing was sent", out["text"])
            self.assertTrue(mailed[0].startswith("mailto:glund@example.edu?subject=Re%3A%20Book%20club"))
            r = post("/ask", {"question": "Draft a reply to Milo"})
            self.assertEqual(r["route"], "compose")
            self.assertEqual(r["draft"]["to"], "mfenn@example.edu")
        finally:
            srv.shutdown()
        for hook in ("function draftBox", "function suggestRows", "Open in Mail", "'Suggested'"):
            self.assertIn(hook, PAGE)
