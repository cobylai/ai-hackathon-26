"""Discovery: propose, confirm, review. No model (a model call fails the test), no network,
no calendar (events are passed in), on a temporary bank."""
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import bank
from bank import people, store
from discover import propose, session, state
from reason import answer

DAY = date(2026, 11, 15)


def entry(id_, name, sent, subject, *, kind="email", course=None, ask=None, deadlines=None, addr=None):
    return {"id": id_, "kind": kind, "folder": "course" if course else "person", "source": f"t:{id_}",
            "sender_name": name,
            "sender_address": None if kind == "canvas" else (addr or f"{name.split()[0].lower()}@x.example"),
            "sent_date": sent, "subject": subject, "ask": ask, "deadlines": deadlines or [],
            "course": course, "topic": None, "ingested_at": "2026-11-14T00:00:00", "body": f"About {subject}."}


def lab_events(n=3):
    first = datetime(2026, 10, 27, 14, 0)  # a Tuesday
    return [{"title": "Lab", "start": first + timedelta(weeks=i), "end": first + timedelta(weeks=i, hours=2),
             "location": "", "all_day": False} for i in range(n)]


def no_model(*a, **k):
    raise AssertionError("model called")


@mock.patch("llm.client.complete_json", no_model)
@mock.patch("llm.client.complete", no_model)
@mock.patch("llm.client.chat", no_model)
class Discover(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for e in [
            entry("a1", "Lena Marsh", "2026-11-12", "Problem set 7 for ZOOL 2150", course="ZOOL 2150"),
            entry("a2", "Lena Marsh", "2026-11-13", "Room change for review session"),
            entry("a3", "Lena Marsh", "2026-11-15", "Lab report format"),
            entry("b1", "Felix Ambrose", "2026-10-15", "Cabin deposit", ask="Send me $35 for the cabin",
                  deadlines=[{"phrase": "Friday", "date": "2026-10-20", "time": None}]),
            entry("b2", "Felix Ambrose", "2026-11-15", "Pay your share", ask="Send $40 by Friday",
                  deadlines=[{"phrase": "Friday", "date": "2026-11-20", "time": "12:00"}]),
            entry("c1", "HIST 2147 Maps and Empires", "2026-11-15", "Essay 2", kind="canvas", course="HIST 2147"),
            entry("d1", "Jonah Pike", "2026-11-12", "Study group for MATH 3320", course="MATH 3320"),
            entry("n1", "Dining Services", "2026-11-01", "Menu"),
            entry("n2", "Dining Services", "2026-11-02", "Menu"),
            entry("n3", "Dining Services", "2026-11-03", "Menu"),
        ]:
            store.write_entry(e, self.root)
        session.reset()
        self.relations = []
        self.deps = {"online": lambda: False, "events": lambda s, e: lab_events(),
                     "relation": lambda name, es: self.relations.append(name) or "TA",
                     "sync": lambda root: (_ for _ in ()).throw(AssertionError("sync while offline"))}

    def tearDown(self):
        session.reset()
        self.tmp.cleanup()

    def ask(self, q):
        return session.handle(q, DAY, self.root, deps=self.deps)

    def run_all(self, reply):
        a = self.ask("discover")
        asked = []
        while session.waiting():
            asked.append(session._run["queue"][0])
            a = self.ask(reply)
        return asked, a

    # ---- propose ----

    def test_one_candidate_of_each_kind(self):
        cands = propose.candidates(store.all_entries(self.root), lab_events(), relation_fn=lambda n, e: "TA")
        q = {c["kind"]: [x["question"] for x in cands if x["kind"] == c["kind"]] for c in cands}
        self.assertIn("Does Lena Marsh write to you about ZOOL 2150?", q["person"])
        self.assertIn("Is Lena Marsh your TA?", q["relation"])
        self.assertIn("Are you taking HIST 2147 Maps and Empires?", q["course"])
        self.assertEqual(q["event"], ["Do you have Lab every Tuesday at 2pm?"])
        self.assertEqual(q["bill"], ["Does Felix Ambrose send you bills to pay ($40 due Nov 20; $35 due Oct 20)?"])
        self.assertFalse(any("Dining" in x for v in q.values() for x in v))  # automated sender
        self.assertFalse(any("MATH 3320" in x for v in q.values() for x in v))  # one mail only
        for c in cands:
            self.assertTrue(c["sources"], c)

    def test_thresholds(self):
        self.assertEqual(propose.event_candidates(lab_events(2)), [])
        es = [e for e in store.all_entries(self.root) if e["id"] != "a3"]
        self.assertFalse([c for c in propose.person_candidates(es) if "Lena" in c["question"]])
        self.assertFalse(propose.bill_candidates([e for e in es if e["id"] != "b1"]))

    def test_relation_is_checked_in_code(self):
        self.assertEqual(session.clean_relation("My Lab Partner.", "Lena Marsh"), "lab partner")
        self.assertIsNone(session.clean_relation("unknown"))
        self.assertIsNone(session.clean_relation("the sender of these emails"))
        self.assertIsNone(session.clean_relation("Lena's friend", "Lena Marsh"))
        self.assertIsNone(session.clean_relation("one two three four five six"))
        self.assertIsNone(session.clean_relation(None))

    # ---- confirm ----

    def test_question_shows_its_entries_and_source(self):
        a = self.ask("Discover")
        self.assertEqual(a.route, "discover")
        self.assertIn("Question 1 of", a.text)
        self.assertIn("Lena Marsh: Problem set 7 for ZOOL 2150", a.text)
        self.assertIn("Say yes, no or skip", a.text)
        self.assertTrue(a.text.splitlines()[-1].startswith("Source: "))
        self.assertTrue(session.waiting())

    def test_nothing_written_without_yes(self):
        before = sorted(p.name for p in self.root.rglob("*.md"))
        self.run_all("skip")
        self.assertEqual(sorted(p.name for p in self.root.rglob("*.md")), before)
        self.assertEqual(state.load(self.root), [])

    def test_yes_writes_through_piece_one(self):
        asked, done = self.run_all("yes")
        self.assertIn("That's all for now", done.text)
        self.assertEqual({n["body"] for n in bank.notes(root=self.root)},
                         {"I'm taking HIST 2147 Maps and Empires", "I have Lab every Tuesday at 2pm"})
        lena = people.get("Lena", root=self.root)
        self.assertEqual(lena["relation"], "TA")
        self.assertEqual([f["fact"] for f in lena["facts"]], ["writes to you about ZOOL 2150"])
        self.assertIn("a1", lena["facts"][0]["source"] or "")
        self.assertIn("sends you bills to pay", [f["fact"] for f in people.get("Felix", root=self.root)["facts"]])
        # and the existing routes find them, with no network
        me = answer("What do you know about me?", today=DAY, root=self.root)
        self.assertIn("I'm taking HIST 2147", me.text)
        who = answer("Who is Lena?", today=DAY, root=self.root)
        self.assertEqual(who.route, "people")
        self.assertIn("How you know them: TA", who.text)

    def test_no_is_never_asked_again_and_skip_comes_back(self):
        a = self.ask("discover")
        first = session._run["queue"][0]["question"]
        self.ask("no")
        second = session._run["queue"][0]["question"]
        self.ask("skip")
        self.ask("stop")
        self.assertFalse(session.waiting())
        asked, _ = self.run_all("skip")
        qs = [c["question"] for c in asked]
        self.assertNotIn(first, qs)
        self.assertIn(second, qs)

    def test_second_run_asks_nothing_answered(self):
        self.run_all("yes")
        a = self.ask("discover")
        self.assertIn("Nothing new to ask", a.text)
        self.assertFalse(session.waiting())
        self.assertEqual(self.relations, ["Lena Marsh"])  # no second relation guess

    def test_known_facts_are_not_asked(self):
        bank.remember("I have Lab every Tuesday at 2pm", today=DAY, root=self.root)
        asked, _ = self.run_all("skip")
        self.assertNotIn("event", [c["kind"] for c in asked])

    def test_cap_of_ten(self):
        events = []
        for k in range(12):
            first = datetime(2026, 10, 5, 8 + k % 10, 0) + timedelta(days=k % 5)
            events += [{"title": f"Thing {k}", "start": first + timedelta(weeks=i), "all_day": False}
                       for i in range(3)]
        self.deps["events"] = lambda s, e: events
        a = self.ask("discover")
        self.assertIn("I found 10 things", a.text)
        self.assertEqual(session._run["n"], 10)

    def test_other_input_ends_the_run(self):
        self.ask("discover")
        self.assertIsNone(self.ask("what's due tomorrow"))
        self.assertFalse(session.waiting())
        self.assertIsNone(self.ask("yes"))  # nothing held: act's yes handles it

    def test_calendar_and_sync_failures_are_said(self):
        from applecal import CalendarError
        self.deps["events"] = lambda s, e: (_ for _ in ()).throw(CalendarError("no permission"))
        self.deps["online"] = lambda: True
        self.deps["sync"] = lambda root: (_ for _ in ()).throw(SystemExit("Not signed in to Gmail"))
        a = self.ask("discover")
        self.assertIn("I couldn't check your mail first", a.text)
        self.assertIn("I couldn't read Apple Calendar (no permission)", a.text)
        self.assertTrue(session.waiting())

    def test_sync_runs_first_when_online(self):
        seen = []
        self.deps["online"] = lambda: True
        self.deps["sync"] = lambda root: seen.append(root) or 2
        a = self.ask("discover")
        self.assertEqual(seen, [self.root])
        self.assertIn("Checked your mail first (2 new)", a.text)

    def test_sync_at_most_every_30_minutes(self):
        seen = []
        self.deps["online"] = lambda: True
        self.deps["sync"] = lambda root: seen.append(1) or 0
        self.ask("discover")
        self.ask("stop")
        self.ask("discover")
        self.assertEqual(len(seen), 1)

    def test_demo_bank_skips_mail_sync_quietly(self):
        import io
        from contextlib import redirect_stderr
        demo = self.root / "muse-demo-bank"
        demo.mkdir()
        for e in store.all_entries(self.root):
            store.write_entry({k: v for k, v in e.items() if k != "path"}, demo)
        self.deps["online"] = lambda: True
        self.deps["sync"] = session._default_sync  # the real one: it must stop before Gmail
        err = io.StringIO()
        with mock.patch("harness.browser.session.get_session", side_effect=AssertionError("Gmail opened")), \
                redirect_stderr(err):
            a = session.handle("discover", DAY, demo, deps=self.deps)
        self.assertNotIn("mail", a.text.splitlines()[0].lower())
        self.assertIn("I found", a.text)
        self.assertTrue(session.waiting())
        self.assertEqual(err.getvalue().count("\n"), 1)
        self.assertIn("mail sync skipped", err.getvalue())
        self.assertEqual(state.since_sync(demo), float("inf"))  # not stamped

    def test_relation_guess_only_when_its_question_comes_up(self):
        self.deps["events"] = lambda s, e: lab_events(8)  # the Lab question outranks Lena's
        self.ask("discover")
        self.assertEqual(self.relations, [])
        while session.waiting() and not self.relations:
            self.ask("skip")
        self.assertEqual(self.relations, ["Lena Marsh"])
        self.assertIn("Is Lena Marsh your TA?", session._run["queue"][0]["question"])

    def test_unusable_relation_guess_is_dropped(self):
        self.deps["relation"] = lambda name, es: None
        asked, _ = self.run_all("skip")
        self.assertNotIn("relation", [c["kind"] for c in asked])
        self.assertTrue(all(not c.get("lazy") for c in asked))

    # ---- review ----

    def test_learned_and_unlearn(self):
        self.assertIn("Nothing learned yet", self.ask("What have you learned?").text)
        self.run_all("yes")
        a = self.ask("What have you learned?")
        self.assertIn("1. Lena Marsh writes to you about ZOOL 2150 (from Lena Marsh, Nov 15", a.text)
        self.assertIn("Lena Marsh is your TA", a.text)
        self.assertIn("Source: your answers in discovery", a.text)
        rows = [ln for ln in a.text.splitlines() if ln[:1].isdigit()]
        for i, row in reversed(list(enumerate(rows, 1))):
            self.assertIn("Removed:", self.ask(f"unlearn {i}").text)
        self.assertEqual(bank.notes(root=self.root), [])
        lena = people.get("Lena", root=self.root)
        self.assertEqual((lena["relation"], lena["facts"]), (None, []))
        self.assertIn("Nothing learned yet", self.ask("what have you learned").text)
        self.assertIn("Nothing new to ask", self.ask("discover").text)  # removed = never again
        self.assertIn("There's no learned fact 9", self.ask("unlearn 9").text)

    def test_unlearn_never_removes_another_note(self):
        self.run_all("yes")
        recs = state.learned(self.root)
        k = next(i for i, r in enumerate(recs, 1) if r["fact"] == "I have Lab every Tuesday at 2pm")
        bank.forget("I have Lab every Tuesday at 2pm", root=self.root)  # the user already forgot it
        self.ask(f"unlearn {k}")
        self.assertEqual([n["body"] for n in bank.notes(root=self.root)], ["I'm taking HIST 2147 Maps and Empires"])

    def test_answers_file_is_outside_the_bank_folders(self):
        self.run_all("no")
        p = state.path(self.root)
        self.assertTrue(p.exists())
        self.assertTrue(all(r["answer"] == "no" for r in json.loads(p.read_text())["answers"]))
        self.assertFalse(any(e["path"].startswith(str(p.parent)) for e in store.all_entries(self.root)))


if __name__ == "__main__":
    unittest.main()
