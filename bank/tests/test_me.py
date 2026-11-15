"""Notes about the user (bank/me.py) and person pages (bank/people.py). No model, no network."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

import bank
from bank import people, store

DAY = date(2026, 11, 14)


def email(id_, name, addr, sent, subject):
    return {"id": id_, "kind": "email", "folder": "person", "source": f"t:{id_}", "sender_name": name,
            "sender_address": addr, "sent_date": sent, "subject": subject, "ask": None, "deadlines": [],
            "course": None, "topic": None, "ingested_at": "2026-11-14T00:00:00", "body": f"About {subject}."}


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()


class Notes(Tmp):
    def test_remember_files_a_me_entry_in_the_users_words(self):
        got = bank.remember("My lab is Tuesdays at 2.", today=DAY, root=self.root)
        self.assertEqual(got["status"], "added")
        e = store.read_entry(Path(got["path"]))
        self.assertEqual((e["kind"], e["folder"], e["body"], e["subject"], e["sender_name"], e["deadlines"]),
                         ("me", "me", "My lab is Tuesdays at 2", "My lab is Tuesdays at 2", "you", []))
        self.assertTrue(got["path"].startswith(str(self.root / "me")))
        self.assertIn("My lab is Tuesdays at 2", (self.root / "index.md").read_text())

    def test_duplicate_ignores_case_and_period(self):
        bank.remember("I'm vegetarian", root=self.root)
        self.assertEqual(bank.remember("i'm vegetarian.", root=self.root)["status"], "duplicate")
        self.assertEqual(len(bank.notes(root=self.root)), 1)

    def test_empty_is_an_error(self):
        with self.assertRaises(ValueError):
            bank.remember("  . ", root=self.root)

    def test_search_finds_a_note(self):
        bank.remember("my lab is Tuesdays at 2", root=self.root)
        hits = bank.search("when is my lab", root=self.root)
        self.assertEqual([h["kind"] for h in hits], ["me"])

    def test_notes_newest_first(self):
        bank.remember("first", root=self.root)
        bank.remember("second", root=self.root)
        self.assertEqual([n["body"] for n in bank.notes(root=self.root)], ["second", "first"])

    def test_forget_best_match(self):
        bank.remember("my lab is Tuesdays at 2", root=self.root)
        bank.remember("I'm vegetarian", root=self.root)
        got = bank.forget("my lab", root=self.root)
        self.assertEqual((got["status"], got["removed"]["body"]), ("removed", "my lab is Tuesdays at 2"))
        self.assertEqual([n["body"] for n in bank.notes(root=self.root)], ["I'm vegetarian"])
        self.assertNotIn("Tuesdays", (self.root / "index.md").read_text())

    def test_forget_tie_removes_nothing(self):
        bank.remember("my lab is Tuesdays", root=self.root)
        bank.remember("my lab partner is Sam", root=self.root)
        got = bank.forget("lab", root=self.root)
        self.assertEqual((got["status"], len(got["candidates"])), ("ambiguous", 2))
        self.assertEqual(len(bank.notes(root=self.root)), 2)

    def test_forget_no_match_and_empty_bank(self):
        self.assertEqual(bank.forget("anything", root=self.root)["status"], "none")
        bank.remember("I'm vegetarian", root=self.root)
        self.assertEqual(bank.forget("bike lock code", root=self.root)["status"], "none")
        self.assertEqual(len(bank.notes(root=self.root)), 1)

    def test_forget_empty_text_removes_newest(self):
        bank.remember("first", root=self.root)
        bank.remember("second", root=self.root)
        self.assertEqual(bank.forget("", root=self.root)["removed"]["body"], "second")


class People(Tmp):
    def setUp(self):
        super().setUp()
        store.write_entry(email("p00000000001", "Felix Ambrose", "felix@x.example", "2026-11-15",
                                "Pay your share"), self.root)
        store.write_entry(email("p00000000002", "Felix Ambrose", "felix@x.example", "2026-11-12",
                                "Cabin list"), self.root)

    def test_starts_empty_but_a_sender_gets_a_page(self):
        self.assertEqual(people.names(root=self.root), [])
        pg = people.get("felix", root=self.root)
        self.assertEqual((pg["name"], pg["relation"], pg["facts"], pg["path"]), ("Felix Ambrose", None, [], None))
        self.assertEqual([e["subject"] for e in pg["entries"]], ["Pay your share", "Cabin list"])
        self.assertIsNone(people.get("zelda", root=self.root))
        self.assertFalse((self.root / "people").exists())

    def test_set_fact_and_relation(self):
        people.set_relation("Felix Ambrose", "cabin trip organizer", root=self.root)
        people.set_fact("Felix Ambrose", "collects the cabin money", source="t:p00000000001", root=self.root)
        people.set_fact("felix", "Collects the cabin money", root=self.root)  # repeat, skipped
        pg = people.get("Felix", root=self.root)
        self.assertEqual(pg["relation"], "cabin trip organizer")
        self.assertEqual([f["fact"] for f in pg["facts"]], ["collects the cabin money"])
        self.assertEqual(pg["facts"][0]["source"], "t:p00000000001")
        self.assertEqual(len(pg["entries"]), 2)
        self.assertEqual(people.names(root=self.root), ["Felix Ambrose"])
        text = (self.root / "people" / "felix-ambrose.md").read_text()
        self.assertIn("How they relate to you: cabin trip organizer", text)
        self.assertIn("- collects the cabin money", text)

    def test_page_is_not_a_bank_entry(self):
        people.set_fact("Felix Ambrose", "plays cello", root=self.root)
        self.assertEqual(bank.search("cello", root=self.root), [])

    def test_alias_and_remove(self):
        people.add_alias("Felix Ambrose", "Fe", root=self.root)
        people.set_fact("Fe", "plays cello", root=self.root)
        self.assertEqual(people.names(root=self.root), ["Felix Ambrose"])
        self.assertTrue(people.remove_fact("Felix Ambrose", "plays cello", root=self.root))
        self.assertFalse(people.remove_fact("Felix Ambrose", "plays cello", root=self.root))
        self.assertEqual(people.get("fe", root=self.root)["facts"], [])

    def test_page_for_someone_with_no_mail(self):
        people.set_relation("Sam Lee", "lab partner", root=self.root)
        pg = people.get("sam", root=self.root)
        self.assertEqual((pg["name"], pg["relation"], pg["entries"]), ("Sam Lee", "lab partner", []))


if __name__ == "__main__":
    unittest.main()
