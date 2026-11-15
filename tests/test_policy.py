"""Table-driven tests for the computer-control policy (task C3)."""

import json

import pytest

from harness.computer import policy


@pytest.fixture
def home(tmp_path):
    return tmp_path


# (app, action, label, expected verdict)
CASES = [
    # allow: every default allowlisted app, case-insensitive
    ("Finder", "open", "", "ALLOW"),
    ("TextEdit", "open", "", "ALLOW"),
    ("Notes", "click", "New note", "ALLOW"),
    ("Calendar", "open", "", "ALLOW"),
    ("Preview", "open", "", "ALLOW"),
    ("Calculator", "click", "7", "ALLOW"),
    ("textedit", "type", "hello", "ALLOW"),
    ("  TextEdit  ", "open", "", "ALLOW"),
    # deny: blocked apps, even though the action itself is harmless
    ("System Settings", "open", "", "DENY"),
    ("Keychain Access", "open", "", "DENY"),
    ("Terminal", "open", "", "DENY"),
    ("1Password", "click", "Show", "DENY"),
    ("Bank of America", "open", "", "DENY"),
    ("terminal", "type", "ls", "DENY"),
    # deny: app simply not on the allowlist
    ("Google Chrome", "open", "", "DENY"),
    ("Safari", "click", "Reload", "DENY"),
    ("", "open", "", "DENY"),
    # confirm: a confirm word in the action or the label of an allowed app
    ("Finder", "click", "delete", "CONFIRM"),
    ("Finder", "click", "Move to Trash", "ALLOW"),
    ("Finder", "empty trash", "", "CONFIRM"),
    ("Notes", "click", "Delete note", "CONFIRM"),
    ("TextEdit", "click", "Remove style", "CONFIRM"),
    ("Calendar", "click", "Send invitation", "CONFIRM"),
    ("Preview", "click", "Erase markings", "CONFIRM"),
    ("Calculator", "click", "pay", "CONFIRM"),
    ("Notes", "click", "Buy more iCloud storage", "CONFIRM"),
    # no substring trickery: "sender" is not "send"
    ("Notes", "click", "Sender field", "ALLOW"),
    # deny beats confirm: a blocked app with a confirm word is still DENY
    ("Terminal", "click", "delete", "DENY"),
    # ... and so is an unlisted app: a confirm token must never reach an app
    # off the allow list (CONFIRM here would let a token replay run it)
    ("Google Chrome", "click", "Delete account", "DENY"),
    ("Safari", "type", "send", "DENY"),
]


@pytest.mark.parametrize("app,action,label,expected", CASES)
def test_check_verdicts(home, app, action, label, expected):
    assert policy.check(app, action, label, home=home) == expected


def test_block_cannot_be_overridden_by_allow(home):
    path = home / "policy.json"
    custom = policy.DEFAULT_POLICY | {"allow_apps": ["Terminal", "TextEdit"]}
    path.write_text(json.dumps(custom))
    assert policy.check("Terminal", "open", home=home) == "DENY"
    assert policy.check("TextEdit", "open", home=home) == "ALLOW"


def test_default_policy_file_is_written(home):
    policy.load_policy(home)
    data = json.loads((home / "policy.json").read_text())
    assert data == policy.DEFAULT_POLICY


def test_corrupt_policy_falls_back_to_defaults(home):
    home.mkdir(exist_ok=True)
    (home / "policy.json").write_text("{not json")
    assert policy.check("TextEdit", "open", home=home) == "ALLOW"
    assert policy.check("Terminal", "open", home=home) == "DENY"


def test_every_check_appends_one_log_line(home):
    policy.check("TextEdit", "open", home=home)
    policy.check("Terminal", "open", home=home)
    policy.check("Finder", "click", "Delete", home=home)
    lines = (home / "actions.log").read_text().splitlines()
    assert len(lines) == 3
    assert "\tALLOW\tTextEdit\topen" in lines[0]
    assert "\tDENY\tTerminal\topen" in lines[1]
    assert "\tCONFIRM\tFinder\tclick\tDelete" in lines[2]
    for line in lines:
        assert line.count("\n") == 0 and line.startswith("20")


def test_stop_file(home):
    assert policy.stopped(home) is False
    (home / "STOP").touch()
    assert policy.stopped(home) is True
    # the message every tool returns while stopped
    assert policy.STOPPED_MESSAGE == "ERR stopped by user"
