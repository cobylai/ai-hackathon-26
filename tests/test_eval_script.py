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


def test_verdict_judges_each_budget_on_its_own():
    module = load_script()
    checks = module.verdict(passes=12, seconds=19.0, chars=9900, tokens=2250)
    assert checks == {"pass": True, "time": True, "tokens": True, "chars": False}
    assert module.verdict(passes=4, seconds=25.0, chars=9000, tokens=2600) == {
        "pass": False,
        "time": False,
        "tokens": False,
        "chars": False,
    }


def test_table_shows_engine_and_walled_searches():
    module = load_script()
    row = {
        "id": "q01",
        "kind": "fact",
        "pass": True,
        "engines": ["google"],
        "rounds": 1,
        "searches": 1,
        "search_walls": 0,
        "pages": 2,
        "blocked": 0,
        "model_calls": 3,
        "chars": 100,
        "prompt_tokens": 25,
        "seconds": 1.0,
    }
    table = module.markdown([row])
    assert "searches walled" in table
    assert "| google | 1 | 0/1 | 2 |" in table


def test_question_file_has_twelve_well_formed_rows():
    module = load_script()
    items = module.load_questions(module.QUESTIONS)
    assert len(items) == 12
    for item in items:
        assert set(item) == {"id", "kind", "question", "expect"}
        assert item["id"] and item["question"] and item["expect"]
    assert len({item["id"] for item in items}) == 12
