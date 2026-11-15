"""Playbook files: layout, step counts, wording keys used by code, prompt copies. No model, no network."""
import re
import string
import unittest
from datetime import date
from pathlib import Path

import importlib
ans = importlib.import_module("reason.answer")
from reason import playbook

ROOT = Path(__file__).resolve().parents[2]
CODE = "\n".join(p.read_text() for p in (ROOT / "reason").glob("*.py"))


class Layout(unittest.TestCase):
    def test_every_route_has_its_file_and_sections_in_order(self):
        self.assertTrue((playbook.DIR / "RULES.md").exists())
        for name in ans.STEPS:
            pb = playbook.load(name)
            heads = [h for h in pb.sections if h in playbook.SECTIONS]
            self.assertEqual(heads, list(playbook.SECTIONS), name)
            self.assertTrue(pb.examples, f"{name}.md has no examples")

    def test_step_counts_match_code(self):
        for name, n in ans.STEPS.items():
            self.assertEqual(len(playbook.load(name).steps), n, f"{name}.md steps vs STEPS")

    def test_every_route_with_a_file_is_in_steps(self):
        self.assertEqual(set(playbook.names()), set(ans.STEPS))


class Wording(unittest.TestCase):
    def test_every_key_code_uses_exists_with_the_right_placeholders(self):
        uses = re.findall(r'say\(\s*["\'](\w+)["\'],\s*["\'](\w+)["\']((?:[^()]|\([^()]*\))*)\)', CODE)
        self.assertGreaterEqual(len(uses), 15)
        for book, key, args in uses:
            text = playbook.load(book).wording.get(key)
            self.assertIsNotNone(text, f"{book}.md has no wording '{key}'")
            given = set(re.findall(r"(\w+)=", args)) - {"for"}
            if "**row" in args:
                given |= {"who", "date", "subject"}
            wanted = {f for _, f, _, _ in string.Formatter().parse(text) if f}
            self.assertLessEqual(wanted, given, f"{book}.md '{key}' placeholders")

    def test_same_words_as_before(self):
        self.assertEqual(playbook.say("person", "no_sender", name="Priya"), "I have nothing from Priya.")
        self.assertEqual(ans.OFFLINE_TEXT,
                         "I don't have that saved, and the Mac is offline, so I can't look it up.")
        self.assertEqual(playbook.say("RULES", "source", labels="x"), "Source: x")

    def test_missing_key_is_a_clear_error(self):
        with self.assertRaises(playbook.PlaybookError):
            playbook.say("due", "no_such_line")


class Triggers(unittest.TestCase):
    def test_parse_and_or(self):
        pb = playbook.parse("t", "## Triggers\n- k: `due`\n- k: `deadlines?`\n")
        self.assertEqual(pb.triggers, {"k": ["due", "deadlines?"]})

    def test_pattern_without_backticks_is_rejected(self):
        with self.assertRaises(playbook.PlaybookError):
            playbook.parse("t", "## Triggers\n- k: due\n")

    def test_examples_table(self):
        pb = playbook.parse("t", "## Examples\n\n| question | route | answer contains |\n|---|---|---|\n"
                                 "| What's due? | due | a; b |\n| Hi | bank | |\n")
        self.assertEqual(pb.examples, [{"question": "What's due?", "route": "due", "contains": ["a", "b"]},
                                       {"question": "Hi", "route": "bank", "contains": []}])


class PromptCopies(unittest.TestCase):
    """bank.md and web.md quote prompts that live in sufficiency/; the quotes must not drift."""

    def test_judge_and_rephrase(self):
        from sufficiency import prompts
        self.assertEqual(playbook.prompt("bank", "judge_system"), prompts.JUDGE_SYSTEM)
        self.assertEqual(playbook.prompt("bank", "judge_ask").rstrip(), prompts.ORIGINAL_ASK.rstrip())
        self.assertEqual(playbook.prompt("bank", "judge_hint"), prompts.ORIGINAL_HINT)
        self.assertEqual(playbook.prompt("web", "rephrase_system"), prompts.REPHRASE_SYSTEM)

    def test_person_prompt_formats(self):
        ans.PERSON_PROMPT.format(today="t", question="q", who="w", notes="n")


class CheckCalendar(unittest.TestCase):
    """playbook_check reads a fixed demo calendar, so Q10's leftover event cannot skew it."""

    def test_fixture_is_the_six_demo_events(self):
        check = importlib.import_module("reason.playbook_check")
        wed = check.fixture_events(date(2026, 11, 18), date(2026, 11, 18))
        self.assertEqual([(e["title"], e["start"].strftime("%H:%M")) for e in wed], [("Lab", "13:30")])
        thu = check.fixture_events(date(2026, 11, 19), date(2026, 11, 19))
        self.assertEqual([e["title"] for e in thu], ["Office hours"])
        week = check.fixture_events(date(2026, 11, 16), date(2026, 11, 22))
        self.assertEqual(len(week), 6)
        self.assertFalse([e for e in week if e["title"] == "Band practice Thursday"])


if __name__ == "__main__":
    unittest.main()
