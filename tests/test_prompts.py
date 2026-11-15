"""S5: `llm.ask` wire format and the four prompt helpers, with a scripted model."""

from __future__ import annotations

from dataclasses import dataclass

from harness import llm
from harness.search import prompts


@dataclass
class Item:
    title: str
    domain: str
    snippet: str = ""


RESULTS = [
    Item("The Lighthouse Keeper", "example.org", "A history of the light."),
    Item("Breakwater design", "coast.example", "How stone walls are built."),
    Item("Mantle glass", "glass.example", "Lamps and spare mantles."),
]


# --- FakeLLM ---------------------------------------------------------------


def test_fake_llm_scripts_replies_and_records_prompts():
    fake = llm.FakeLLM(["first", "second"])
    assert fake.ask("one") == "first"
    assert fake.ask("two") == "second"
    assert fake.ask("three") == ""
    assert fake.prompts == ["one", "two", "three"]


def test_fake_llm_coerces_choices():
    fake = llm.FakeLLM(["yes please", "banana"])
    assert fake.ask("q", choices=["YES", "NO"]) == "YES"
    assert fake.ask("q", choices=["YES", "NO"]) == ""


# --- pick ------------------------------------------------------------------


def test_pick_returns_numbers_in_order():
    fake = llm.FakeLLM(["2, 1"])
    assert prompts.pick("who kept the light?", RESULTS, ask=fake.ask) == [2, 1]
    assert "The Lighthouse Keeper" in fake.prompts[0]
    assert "who kept the light?" in fake.prompts[0]


def test_pick_drops_out_of_range_and_duplicate_numbers():
    assert prompts.pick("q", RESULTS, ask=llm.FakeLLM(["9, 2, 2, 0"]).ask) == [2]
    assert prompts.pick("q", RESULTS, ask=llm.FakeLLM(["none"]).ask) == []
    assert prompts.pick("q", RESULTS, ask=llm.FakeLLM([""]).ask) == []
    assert prompts.pick("q", [], ask=llm.FakeLLM(["1"]).ask) == []


def test_pick_keeps_at_most_three():
    five = RESULTS + [Item("four", "a.example"), Item("five", "b.example")]
    assert prompts.pick("q", five, ask=llm.FakeLLM(["1 2 3 4 5"]).ask) == [1, 2, 3]


# --- note ------------------------------------------------------------------


def test_note_returns_short_text():
    fake = llm.FakeLLM(["  The keeper climbed one hundred and twelve steps.  "])
    text = prompts.note("how many steps?", "Steps were many.", ask=fake.ask)
    assert text == "The keeper climbed one hundred and twelve steps."
    assert "Steps were many." in fake.prompts[0]


def test_note_rejects_none_and_empty():
    assert prompts.note("q", "chunk", ask=llm.FakeLLM(["NONE"]).ask) is None
    assert prompts.note("q", "chunk", ask=llm.FakeLLM(["None of this helps."]).ask) is None
    assert prompts.note("q", "chunk", ask=llm.FakeLLM([""]).ask) is None


def test_note_is_capped():
    text = prompts.note("q", "chunk", ask=llm.FakeLLM(["word " * 200]).ask)
    assert text is not None and len(text) <= prompts.MAX_NOTE_CHARS


# --- enough ----------------------------------------------------------------


def test_enough_reads_yes_and_no():
    notes = [("1", "example.org", "a note")]
    assert prompts.enough("q", notes, ask=llm.FakeLLM(["YES"]).ask)
    assert not prompts.enough("q", notes, ask=llm.FakeLLM(["NO"]).ask)
    assert not prompts.enough("q", [], ask=llm.FakeLLM([""]).ask)


def test_enough_prompt_lists_the_notes():
    fake = llm.FakeLLM(["YES"])
    prompts.enough("how many steps?", [("2", "example.org", "one hundred and twelve")], ask=fake.ask)
    assert "[2] example.org: one hundred and twelve" in fake.prompts[0]


# --- rewrite ---------------------------------------------------------------


def test_rewrite_returns_a_clean_query():
    query = prompts.rewrite(
        "when was it automated?",
        "lighthouse",
        [],
        ask=llm.FakeLLM(['"lighthouse automation 1990s"']).ask,
    )
    assert query == "lighthouse automation 1990s"


def test_rewrite_uses_first_line_only():
    reply = "keeper automation date\nbecause the notes were vague"
    assert prompts.rewrite("q", "old", [], ask=llm.FakeLLM([reply]).ask) == "keeper automation date"


def test_rewrite_falls_back_to_the_old_query():
    assert prompts.rewrite("q", "old query", [], ask=llm.FakeLLM([""]).ask) == "old query"
    assert prompts.rewrite("q", "old query", [], ask=llm.FakeLLM(["   "]).ask) == "old query"


# --- llm.ask ---------------------------------------------------------------


class FakeResponse:
    def __init__(self, content: str, status: int = 200, usage: dict | None = None) -> None:
        self.content = content
        self.status = status
        self.usage = usage

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise RuntimeError(f"http {self.status}")

    def json(self):
        body = {"choices": [{"message": {"content": self.content}}]}
        if self.usage is not None:
            body["usage"] = self.usage
        return body


def patch_post(monkeypatch, result) -> dict:
    seen: dict = {}

    def fake_post(url, json=None, timeout=None):
        seen["url"] = url
        seen["payload"] = json
        seen["timeout"] = timeout
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    return seen


def test_ask_posts_to_the_configured_endpoint(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://model.local:9000/v1/")
    monkeypatch.setenv("LLM_MODEL", "tiny")
    seen = patch_post(monkeypatch, FakeResponse(" hello there "))
    assert llm.ask("hi") == "hello there"
    assert seen["url"] == "http://model.local:9000/v1/chat/completions"
    assert seen["payload"]["model"] == "tiny"
    assert seen["payload"]["max_tokens"] == 64
    assert seen["payload"]["messages"][-1] == {"role": "user", "content": "hi"}
    assert "response_format" not in seen["payload"]


def test_ask_constrains_to_choices(monkeypatch):
    seen = patch_post(monkeypatch, FakeResponse('{"choice": "NO"}'))
    assert llm.ask("is it enough?", choices=["YES", "NO"], max_tokens=4) == "NO"
    schema = seen["payload"]["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["choice"]["enum"] == ["YES", "NO"]
    assert seen["payload"]["max_tokens"] == 4


def test_ask_maps_free_text_onto_a_choice(monkeypatch):
    patch_post(monkeypatch, FakeResponse("no, the notes are missing a date"))
    assert llm.ask("q", choices=["YES", "NO"]) == "NO"


def test_ask_returns_empty_on_bad_reply_or_dead_server(monkeypatch):
    patch_post(monkeypatch, FakeResponse("banana"))
    assert llm.ask("q", choices=["YES", "NO"]) == ""
    patch_post(monkeypatch, llm.httpx.ConnectError("no model"))
    assert llm.ask("q") == ""
    patch_post(monkeypatch, FakeResponse("", status=500))
    assert llm.ask("q") == ""


def test_ask_can_turn_off_reasoning(monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "none")
    seen = patch_post(monkeypatch, FakeResponse("Ready"))
    assert llm.ask("hi") == "Ready"
    assert seen["payload"]["reasoning_effort"] == "none"


def test_ask_records_real_token_usage(monkeypatch):
    patch_post(
        monkeypatch,
        FakeResponse("Ready", usage={"prompt_tokens": 41, "completion_tokens": 5}),
    )
    assert llm.ask("hi", max_tokens=16) == "Ready"
    assert llm.last_usage == {"prompt_tokens": 41, "completion_tokens": 5}


def test_ask_clears_usage_on_failure(monkeypatch):
    patch_post(
        monkeypatch,
        FakeResponse("Ready", usage={"prompt_tokens": 41, "completion_tokens": 5}),
    )
    llm.ask("hi")
    patch_post(monkeypatch, llm.httpx.ConnectError("down"))
    assert llm.ask("hi") == ""
    assert llm.last_usage == {}


def test_ask_without_choices_returns_plain_text(monkeypatch):
    patch_post(monkeypatch, FakeResponse("  just words  "))
    assert llm.ask("q") == "just words"
