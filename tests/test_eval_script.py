"""The evaluation script's grader: an echo of the question is not an answer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "eval_search.py"


def load_script():
    spec = importlib.util.spec_from_file_location("eval_search_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_question_echo_is_not_a_pass():
    module = load_script()
    answer = 'No useful results were found for "What is the weather in Seattle?" after 1 round.'
    assert module.is_pass(answer, "Seattle", notes=0) is False


def test_pass_needs_notes_and_the_expected_text():
    module = load_script()
    assert module.is_pass("The capital is Lisbon [1].", "Lisbon", notes=1) is True
    assert module.is_pass("The capital is Porto [1].", "Lisbon", notes=1) is False
    assert module.is_pass("The capital is Lisbon [1].", "Lisbon", notes=0) is False


def test_grading_is_case_insensitive():
    module = load_script()
    assert module.is_pass("hypertext transfer protocol", "Hypertext", notes=1) is True


def test_question_file_has_twelve_well_formed_rows():
    module = load_script()
    items = module.load_questions(module.QUESTIONS)
    assert len(items) == 12
    for item in items:
        assert set(item) == {"id", "kind", "question", "expect"}
        assert item["id"] and item["question"] and item["expect"]
    assert len({item["id"] for item in items}) == 12
