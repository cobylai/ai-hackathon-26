"""S6: the research loop stops early, rewrites, respects caps and survives walls."""

from __future__ import annotations

from pathlib import Path

from harness import llm, registry
from harness.browser.text import page_text
from harness.search import engine, loop, tools
from harness.search.google import Result

ARTICLE = page_text(
    (Path(__file__).parent / "pages" / "article.html").read_text(encoding="utf-8")
)


def results_for(tag: str, count: int = 5) -> list[Result]:
    return [
        Result(
            f"{tag} result {n}",
            f"https://{tag}{n}.example/page",
            f"{tag}{n}.example",
            "A page about the lighthouse.",
        )
        for n in range(1, count + 1)
    ]


class Script:
    """A search + open_page pair over fixture pages, with call counters."""

    def __init__(self, blocked: set[str] | None = None) -> None:
        self.queries: list[str] = []
        self.opened: list[str] = []
        self.blocked = blocked or set()

    def search(self, query: str) -> list[Result]:
        self.queries.append(query)
        return results_for(f"round{len(self.queries)}")

    def open_page(self, url: str) -> tuple[str, str]:
        self.opened.append(url)
        if any(marker in url for marker in self.blocked):
            return "BLOCKED", ""
        return "OK", ARTICLE


def answer_words(text: str) -> int:
    return len(text.splitlines()[0].split())


def test_stops_early_when_the_notes_are_enough():
    fake = llm.FakeLLM(
        [
            "1",  # pick
            "The keeper kept the light for thirty-one years.",  # note
            "YES",  # enough
            "He kept it for thirty-one years [1].",  # answer
        ]
    )
    site = Script()
    outcome = loop.research(
        "how long did the keeper keep the light?",
        ask=fake.ask,
        search=site.search,
        open_page=site.open_page,
    )
    assert outcome.rounds == 1
    assert len(site.queries) == 1
    assert len(site.opened) == 1
    assert "thirty-one years" in outcome.answer
    assert "Sources: 1. round11.example" in outcome.answer
    assert len(fake.prompts) == 4


def test_rewrites_when_the_notes_are_not_enough():
    fake = llm.FakeLLM(
        [
            "1",
            "The page mentions the steps.",
            "NO",
            "lighthouse automation date",
            "2",
            "The automation crew arrived two winters later.",
            "YES",
            "The crew arrived two winters later [2].",
        ]
    )
    site = Script()
    outcome = loop.research(
        "when was the light automated?",
        ask=fake.ask,
        search=site.search,
        open_page=site.open_page,
    )
    assert site.queries == ["when was the light automated?", "lighthouse automation date"]
    assert outcome.rounds == 2
    assert "2. round22.example" in outcome.answer
    assert len(site.opened) == 2


def test_stop_after_notes_skips_the_enough_call(monkeypatch):
    monkeypatch.setattr(loop, "STOP_AFTER_NOTES", 2)
    fake = llm.FakeLLM(["1 2", "note A", "note B", "Answer [1]."])
    site = Script()
    outcome = loop.research("q", ask=fake.ask, search=site.search, open_page=site.open_page)
    assert outcome.rounds == 1
    assert len(outcome.notes) == 2
    assert not any("fully answer" in prompt for prompt in fake.prompts)


def test_stop_after_notes_keeps_searching_when_one_note_arrives(monkeypatch):
    monkeypatch.setattr(loop, "STOP_AFTER_NOTES", 2)
    fake = llm.FakeLLM(
        ["1", "note A", "NO", "q2", "1", "note B", "YES", "Answer [1]."]
    )
    site = Script()
    outcome = loop.research("q", ask=fake.ask, search=site.search, open_page=site.open_page)
    assert outcome.rounds == 2
    assert len(outcome.notes) == 2
    assert any("fully answer" in prompt for prompt in fake.prompts)


def test_stop_after_notes_is_off_unless_asked(monkeypatch):
    monkeypatch.setattr(loop, "STOP_AFTER_NOTES", 0)
    fake = llm.FakeLLM(["1 2", "note A", "note B", "YES", "Answer [1]."])
    site = Script()
    loop.research("q", ask=fake.ask, search=site.search, open_page=site.open_page)
    assert any("fully answer" in prompt for prompt in fake.prompts)


def test_last_round_does_not_ask_enough():
    fake = llm.FakeLLM(
        [
            "1", "note one", "NO", "q2",
            "1", "note two", "NO", "q3",
            "1", "note three",
        ]
    )
    site = Script()
    loop.research("q", ask=fake.ask, search=site.search, open_page=site.open_page)
    enough_calls = sum(1 for prompt in fake.prompts if "fully answer" in prompt)
    assert enough_calls == loop.MAX_ROUNDS - 1


def test_rewrite_sees_only_the_latest_notes():
    fake = llm.FakeLLM(
        [
            "1", "FIRST-ROUND-NOTE", "NO", "q2",
            "1", "SECOND-ROUND-NOTE", "NO", "q3",
        ]
    )
    site = Script()
    loop.research("q", ask=fake.ask, search=site.search, open_page=site.open_page)
    first_rewrite = next(p for p in fake.prompts if "better search query" in p)
    later_rewrites = [p for p in fake.prompts if "better search query" in p][1:]
    assert "FIRST-ROUND-NOTE" in first_rewrite
    assert later_rewrites
    for prompt in later_rewrites:
        assert "SECOND-ROUND-NOTE" in prompt
        assert "FIRST-ROUND-NOTE" not in prompt


class GreedyModel:
    """Always picks five results, never finds anything useful, always asks again."""

    def __init__(self) -> None:
        self.rewrites = 0
        self.prompts: list[str] = []

    def __call__(self, prompt: str, choices=None, max_tokens: int = 64) -> str:
        self.prompts.append(prompt)
        if "Search results:" in prompt:
            return "1 2 3 4 5"
        if "Page chunk:" in prompt:
            return "NONE"
        if choices:
            return "NO"
        if "better search query" in prompt:
            self.rewrites += 1
            return f"another query {self.rewrites}"
        return "an answer"


def test_never_exceeds_round_and_page_caps():
    site = Script()
    outcome = loop.research(
        "anything", ask=GreedyModel(), search=site.search, open_page=site.open_page
    )
    assert outcome.rounds == loop.MAX_ROUNDS == 3
    assert loop.MAX_PAGES_PER_ROUND == 2
    assert len(site.queries) == 3
    assert len(site.opened) == 6  # two pages per round, never more
    assert len(set(site.opened)) == 6
    assert outcome.notes == []
    assert "No useful results were found" in outcome.answer


def test_at_most_two_picks_are_opened_in_a_round():
    fake = llm.FakeLLM(["1 2 3 4 5", "A useful note.", "YES", "Answer [1]."])
    site = Script()
    outcome = loop.research("q", ask=fake.ask, search=site.search, open_page=site.open_page)
    assert outcome.rounds == 1
    assert len(site.opened) == 2


def test_survives_a_blocked_page():
    fake = llm.FakeLLM(
        [
            "1, 2",  # pick; result 1 is walled
            "The crew arrived two winters later.",  # note from result 2
            "YES",
            "Two winters later [2].",
        ]
    )
    site = Script(blocked={"round11.example/page"})
    outcome = loop.research("q", ask=fake.ask, search=site.search, open_page=site.open_page)
    assert len(site.opened) == 2  # the walled page was visited, not retried
    assert [note[0] for note in outcome.notes] == [1]  # note numbering, not result numbering
    assert outcome.notes[0][1] == "round12.example"
    assert "Sources: 1. round12.example" in outcome.answer


def test_stops_after_one_search_when_the_engine_is_walled(monkeypatch):
    queries: list[str] = []

    def walled(query: str):
        queries.append(query)
        monkeypatch.setattr(loop.engine, "last_query", query)  # what engine.search does
        return []

    monkeypatch.setattr(loop.engine, "search", walled)
    monkeypatch.setattr(loop.engine, "last_status", "BLOCKED")
    fake = llm.FakeLLM(["a better query", "another query"])
    outcome = loop.research("anything", ask=fake.ask)
    assert len(queries) == 1
    assert outcome.rounds == 1
    assert "1 search round" in outcome.answer
    assert not any("better search query" in prompt for prompt in fake.prompts)


def test_stops_after_one_search_when_the_engine_errors(monkeypatch):
    queries: list[str] = []

    def broken(query: str):
        queries.append(query)
        monkeypatch.setattr(loop.engine, "last_query", query)
        return []

    monkeypatch.setattr(loop.engine, "search", broken)
    monkeypatch.setattr(loop.engine, "last_status", "ERR")
    fake = llm.FakeLLM(["a better query", "another query"])
    outcome = loop.research("anything", ask=fake.ask)
    assert len(queries) == 1
    assert outcome.rounds == 1
    assert not outcome.notes


def test_one_broken_page_does_not_end_the_run():
    results = [
        Result("A", "https://a.example/1", "a.example", ""),
        Result("B", "https://b.example/1", "b.example", ""),
    ]

    def open_page(url: str) -> tuple[str, str]:
        if "a.example" in url:
            raise RuntimeError("browser died mid-run")
        return "OK", ARTICLE

    fake = llm.FakeLLM(["1 2", "The keeper kept a note.", "YES", "Answer [1]."])
    outcome = loop.research(
        "q", ask=fake.ask, search=lambda query: results, open_page=open_page
    )
    assert outcome.pages == 2
    assert len(outcome.notes) == 1
    assert "b.example" in outcome.answer


def test_wall_stop_survives_a_search_wrapper(monkeypatch):
    """The evaluation wraps `engine.search`; the stop rule must still fire."""
    queries: list[str] = []

    def fake_engine(query: str):
        queries.append(query)
        monkeypatch.setattr(loop.engine, "last_query", query)
        return []

    monkeypatch.setattr(loop.engine, "search", fake_engine)
    monkeypatch.setattr(loop.engine, "last_status", "BLOCKED")

    def recording_wrapper(query: str):  # what scripts/eval_search.py does
        return loop.engine.search(query)

    fake = llm.FakeLLM(["a better query"])
    outcome = loop.research("anything", ask=fake.ask, search=recording_wrapper)
    assert len(queries) == 1
    assert outcome.rounds == 1


def test_empty_results_from_a_working_engine_still_rewrite(monkeypatch):
    queries: list[str] = []

    def empty(query: str):
        queries.append(query)
        return []

    monkeypatch.setattr(loop.engine, "search", empty)
    monkeypatch.setattr(loop.engine, "last_status", "OK")
    fake = llm.FakeLLM(["query two", "query three"])
    loop.research("anything", ask=fake.ask)
    assert len(queries) == loop.MAX_ROUNDS


def test_repeating_a_query_stops_the_loop():
    fake = llm.FakeLLM(["1", "One note.", "NO", "   "])
    site = Script()
    outcome = loop.research(
        "original question", ask=fake.ask, search=site.search, open_page=site.open_page
    )
    assert outcome.rounds == 1
    assert site.queries == ["original question"]


def test_pages_are_opened_only_once():
    fake = llm.FakeLLM(["1", "One note.", "NO", "second query", "1", "YES", "Done [1]."])
    site = Script()
    site.search = lambda query: results_for("same")  # same URLs every round
    outcome = loop.research("q", ask=fake.ask, search=site.search, open_page=site.open_page)
    assert len(site.opened) == 1
    assert outcome.rounds == 2


def test_answer_is_capped_at_120_words():
    long_reply = " ".join(f"word{n}" for n in range(400))
    fake = llm.FakeLLM(["1", "A note.", "YES", long_reply])
    site = Script()
    outcome = loop.research("q", ask=fake.ask, search=site.search, open_page=site.open_page)
    assert answer_words(outcome.answer) == loop.MAX_ANSWER_WORDS


def test_a_silent_model_is_an_error_not_an_empty_result():
    site = Script()
    outcome = loop.research(
        "q", ask=llm.FakeLLM([]).ask, search=site.search, open_page=site.open_page
    )
    assert outcome.error and "LLM_BASE_URL" in outcome.error
    assert outcome.rounds == 1
    assert not outcome.notes
    assert "did not answer" in outcome.answer


class SteppingClock:
    """Advances on every read, so a budget test needs no sleeping."""

    def __init__(self, step: float = 1.0) -> None:
        self.value = 0.0
        self.step = step

    def __call__(self) -> float:
        self.value += self.step
        return self.value


def test_a_spent_budget_answers_from_the_notes(monkeypatch):
    monkeypatch.setattr(loop, "MAX_SECONDS", 2.0)
    monkeypatch.setattr(loop, "_now", SteppingClock(1.0))
    fake = llm.FakeLLM(["1", "The keeper kept the light.", "NO", "q2"])
    site = Script()
    outcome = loop.research("q", ask=fake.ask, search=site.search, open_page=site.open_page)
    assert outcome.rounds == 1
    assert len(outcome.notes) == 1
    assert "The keeper kept the light." in outcome.answer
    assert "Sources: 1." in outcome.answer


def test_a_budget_spent_before_the_first_search_says_so(monkeypatch):
    monkeypatch.setattr(loop, "MAX_SECONDS", 0.0)
    site = Script()
    outcome = loop.research("q", ask=llm.FakeLLM([]).ask, search=site.search, open_page=site.open_page)
    assert outcome.rounds == 0
    assert "Ran out of time" in outcome.answer
    assert not site.queries


def test_empty_question_is_handled():
    outcome = loop.research("   ")
    assert outcome.rounds == 0 and outcome.pages == 0
    assert "No question" in outcome.answer


def test_research_tool_formats_status_and_stays_under_the_cap(monkeypatch):
    engine.reset()
    monkeypatch.setattr(
        loop,
        "research",
        lambda question: loop.Outcome(
            "Answer [1].\nSources: 1. a.example", 1, 1, [(1, "a.example", "note")]
        ),
    )
    out = tools.research("q")
    assert out.startswith("OK research | 1 rounds | 1 pages")
    assert "Sources: 1. a.example" in out
    assert len(out) <= 1500


def test_research_tool_reports_a_blocked_wall(monkeypatch):
    engine.reset()
    engine.last_status = "BLOCKED"
    monkeypatch.setattr(loop, "research", lambda question: loop.Outcome("nothing", 3, 3, []))
    assert tools.research("q").startswith("BLOCKED research | 3 rounds")
    engine.reset()


def test_registry_research_runs_end_to_end_offline(monkeypatch, session, site):
    """The decision tree calls `registry.TOOLS["research"]`; everything below must fit."""
    from harness.browser import tools as browser_tools

    monkeypatch.setattr(browser_tools, "_page", lambda: session.page)
    monkeypatch.setattr(
        engine,
        "search",
        lambda query: [
            Result("The Keeper", site.url("article.html"), "127.0.0.1", "a story")
        ],
    )
    replies = iter(
        [
            "1",
            "The keeper climbed one hundred and twelve steps.",
            "YES",
            "He climbed one hundred and twelve steps [1].",
        ]
    )
    monkeypatch.setattr(llm, "ask", lambda prompt, choices=None, max_tokens=64: next(replies))

    out = registry.TOOLS["research"].run(question="how many steps did the keeper climb?")

    assert out.startswith("OK research |")
    assert "one hundred and twelve steps" in out
    assert "Sources: 1. 127.0.0.1" in out
    assert len(out) <= 1500


def test_registry_exposes_research():
    entry = registry.TOOLS["research"]
    assert entry.args == {"question": str}
    assert "research" in registry.GROUPS["search"]
    assert entry.desc and len(entry.desc) <= 100
