"""B7: the CLI wires arguments to tools correctly and handles exit codes."""

import pytest

import harness.__main__ as cli


class FakeTool:
    def __init__(self, result: str = "OK example.com | Example Domain"):
        self.result = result
        self.calls: list[dict] = []

    def run(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return self.result


@pytest.fixture()
def fake(monkeypatch):
    tools = {
        name: FakeTool() for name in ("goto", "read", "elements", "click", "type", "back")
    }
    stopped = []

    class Stopper:
        def stop(self):
            stopped.append(True)

    monkeypatch.setattr(cli, "TOOLS", tools)
    monkeypatch.setattr(cli, "get_session", lambda: Stopper())
    return tools, stopped


def test_goto_passes_the_url(fake):
    tools, stopped = fake
    assert cli.main(["goto", "https://example.com"]) == 0
    assert tools["goto"].calls == [{"url": "https://example.com"}]
    assert stopped == [True]


def test_read_defaults_to_page_one(fake):
    tools, _ = fake
    cli.main(["read"])
    assert tools["read"].calls == [{"page": 1}]
    cli.main(["read", "3"])
    assert tools["read"].calls[-1] == {"page": 3}


def test_elements_filter_is_optional(fake):
    tools, _ = fake
    cli.main(["elements"])
    cli.main(["elements", "sign"])
    assert tools["elements"].calls == [{"filter": None}, {"filter": "sign"}]


def test_click_and_back(fake):
    tools, _ = fake
    cli.main(["click", "2"])
    cli.main(["back"])
    assert tools["click"].calls == [{"n": 2}]
    assert tools["back"].calls == [{}]


def test_type_maps_the_enter_flag(fake):
    tools, _ = fake
    cli.main(["type", "2", "hello world"])
    cli.main(["type", "2", "hello world", "--enter"])
    assert tools["type"].calls == [
        {"n": 2, "text": "hello world", "enter": 0},
        {"n": 2, "text": "hello world", "enter": 1},
    ]


def test_non_ok_result_exits_one(fake, capsys):
    tools, _ = fake
    tools["goto"].result = "BLOCKED example.com | Just a moment | bot check"
    assert cli.main(["goto", "https://example.com"]) == 1
    assert capsys.readouterr().out.startswith("BLOCKED")


def test_login_dispatches_to_the_sign_in_flow(fake, monkeypatch):
    called = []

    def fake_login(url):
        called.append(url)
        return 0

    monkeypatch.setattr("harness.browser.login.login", fake_login)
    assert cli.main(["login", "https://example.com"]) == 0
    assert called == ["https://example.com"]
