"""Confirmed send: every gate fails closed, and the driver runs only when all pass.

Offline: a fake driver stands in for Gmail, files live in a temp FLUX_SEND_DIR, and
the real Gmail driver is refused under pytest. Made-up addresses only.
"""

from __future__ import annotations

import json

import pytest

from harness.email import send

ME = "me@example.test"
FRIEND = "friend@example.test"
STRANGER = "stranger@example.test"
DRAFT = "d1"


class Driver:
    def __init__(self, result=send.SENT):
        self.calls, self.result = [], result

    def __call__(self, to, subject, body):
        self.calls.append((to, subject, body))
        return self.result


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv(send.DIR_ENV, str(tmp_path))
    monkeypatch.delenv(send.SELF_ENV, raising=False)
    monkeypatch.setenv(send.ALLOW_ENV, "1")
    (tmp_path / "send_allow.json").write_text(json.dumps({"self": ME, "allow": [FRIEND]}))
    send.forget_all()
    yield tmp_path
    send.forget_all()


def flux(draft_id):
    return draft_id == DRAFT


def click():
    return send.UserApproval.from_click("POST", "/send/confirm", {send.CLICK_HEADER: send.CLICK_VALUE},
                                        ("http://localhost:8765",))


def prepare(to=ME, subject="Hello", body="Hi,\n\nTest.", **kw):
    kw.setdefault("draft_id", DRAFT)
    kw.setdefault("is_flux_draft", flux)
    return send.prepare_send(to, subject, body, **kw)


def go(p, driver, **over):
    args = {"to": p["to"], "subject": p["subject"], "body": p["body"]} | over
    return send.send_draft(p["token"], args["to"], args["subject"], args["body"], approval=click(), driver=driver)


def log_rows(tmp):
    path = tmp / "send_log.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


# ---- the happy path (fake driver) ------------------------------------------------

def test_all_gates_pass_sends_once_to_self(sandbox):
    d = Driver()
    p = prepare()
    assert set(p) >= {"token", "to", "subject", "body", "expires_in"} and p["expires_in"] == 300
    assert go(p, d) == send.SENT
    assert d.calls == [(ME, "Hello", "Hi,\n\nTest.")]


def test_allowlisted_address_sends(sandbox):
    d = Driver()
    assert go(prepare(to=FRIEND), d) == send.SENT and len(d.calls) == 1


def test_self_address_from_env(sandbox, monkeypatch):
    (sandbox / "send_allow.json").unlink()
    monkeypatch.setenv(send.SELF_ENV, ME)
    d = Driver()
    assert go(prepare(), d) == send.SENT


# ---- 1. flag ----------------------------------------------------------------------

@pytest.mark.parametrize("value", [None, "", "0", "true", "yes", " 1", "1 "])
def test_flag_off_refuses_prepare(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(send.ALLOW_ENV)
    else:
        monkeypatch.setenv(send.ALLOW_ENV, value)
    with pytest.raises(send.SendRefused) as e:
        prepare()
    assert e.value.gate == "flag"


def test_flag_off_between_prepare_and_send(monkeypatch):
    d = Driver()
    p = prepare()
    monkeypatch.setenv(send.ALLOW_ENV, "0")
    with pytest.raises(send.SendRefused) as e:
        go(p, d)
    assert e.value.gate == "flag" and not d.calls


def test_default_is_off(monkeypatch):
    monkeypatch.delenv(send.ALLOW_ENV)
    assert send.enabled() is False


# ---- 2. flux draft ----------------------------------------------------------------

@pytest.mark.parametrize("draft_id,check", [("", flux), ("other", flux), (DRAFT, None)])
def test_only_flux_drafts(draft_id, check):
    kw = {"draft_id": draft_id}
    if check is not None:
        kw["is_flux_draft"] = check
    else:
        kw["is_flux_draft"] = send._not_flux
    with pytest.raises(send.SendRefused) as e:
        prepare(**kw)
    assert e.value.gate == "flux draft"


def test_flux_draft_check_defaults_to_no():
    with pytest.raises(send.SendRefused) as e:
        send.prepare_send(ME, "s", "b", draft_id=DRAFT)
    assert e.value.gate == "flux draft"


# ---- 3. click ---------------------------------------------------------------------

@pytest.mark.parametrize("approval", [None, True, "yes", object(), {"clicked": True}])
def test_no_click_no_send(approval):
    d = Driver()
    p = prepare()
    with pytest.raises(send.SendRefused) as e:
        send.send_draft(p["token"], p["to"], p["subject"], p["body"], approval=approval, driver=d)
    assert e.value.gate == "click" and not d.calls


def test_approval_cannot_be_built_by_hand():
    with pytest.raises(send.SendRefused):
        send.UserApproval(None, 0)
    with pytest.raises(send.SendRefused):
        send.UserApproval(object(), 0)


@pytest.mark.parametrize("method,path,headers", [
    ("GET", "/send/confirm", {send.CLICK_HEADER: send.CLICK_VALUE}),
    ("POST", "/ask", {send.CLICK_HEADER: send.CLICK_VALUE}),
    ("POST", "/send/confirm", {}),
    ("POST", "/send/confirm", {send.CLICK_HEADER: "yes"}),
    ("POST", "/send/confirm", {send.CLICK_HEADER: send.CLICK_VALUE, "Origin": "https://evil.example"}),
    ("POST", "/send/confirm", None),
])
def test_click_request_shape(method, path, headers):
    with pytest.raises(send.SendRefused) as e:
        send.UserApproval.from_click(method, path, headers, ("http://localhost:8765",))
    assert e.value.gate == "click"


# ---- 4. token ---------------------------------------------------------------------

def test_token_single_use():
    d = Driver()
    p = prepare()
    go(p, d)
    with pytest.raises(send.SendRefused) as e:
        go(p, d)
    assert e.value.gate == "token" and len(d.calls) == 1


def test_token_used_up_even_by_a_refused_attempt():
    d = Driver()
    p = prepare()
    with pytest.raises(send.SendRefused):
        go(p, d, body="changed")
    with pytest.raises(send.SendRefused) as e:
        go(p, d)
    assert e.value.gate == "token" and not d.calls


@pytest.mark.parametrize("token", ["", "made-up", None, 123])
def test_unknown_token(token):
    d = Driver()
    p = prepare()
    with pytest.raises(send.SendRefused) as e:
        send.send_draft(token, p["to"], p["subject"], p["body"], approval=click(), driver=d)
    assert e.value.gate == "token" and not d.calls


def test_token_expires_after_5_minutes():
    d = Driver()
    p = send.prepare_send(ME, "s", "b", draft_id=DRAFT, is_flux_draft=flux, now=1000.0)
    with pytest.raises(send.SendRefused) as e:
        send.send_draft(p["token"], ME, "s", "b", approval=click(), driver=d, now=1000.0 + 301)
    assert e.value.gate == "token" and not d.calls


def test_cancel_drops_the_token():
    d = Driver()
    p = prepare()
    assert send.cancel(p["token"]) is True
    with pytest.raises(send.SendRefused) as e:
        go(p, d)
    assert e.value.gate == "token" and not d.calls


# ---- 5. content hash ----------------------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("to", FRIEND), ("to", ME.upper()), ("to", " " + ME), ("subject", "Hello!"), ("subject", "hello"),
    ("body", "Hi,\n\nTest. "), ("body", "Hi,\nTest."), ("body", None), ("subject", None)])
def test_any_change_invalidates(field, value):
    d = Driver()
    p = prepare()
    with pytest.raises(send.SendRefused) as e:
        go(p, d, **{field: value})
    assert e.value.gate == "content" and not d.calls


# ---- 6. one recipient -------------------------------------------------------------

@pytest.mark.parametrize("to", ["", "   ", f"{ME},{FRIEND}", f"{ME}; {FRIEND}", f"{ME} {FRIEND}",
                                f"Me <{ME}>", "not-an-address", f"{ME}\ncc: {FRIEND}", "@example.test"])
def test_exactly_one_plain_recipient(to):
    with pytest.raises(send.SendRefused) as e:
        prepare(to=to)
    assert e.value.gate == "one recipient"


def test_there_is_no_cc_or_bcc_parameter():
    p = prepare()
    with pytest.raises(TypeError):
        send.send_draft(p["token"], p["to"], p["subject"], p["body"], approval=click(), driver=Driver(), cc=FRIEND)
    with pytest.raises(TypeError):
        send.prepare_send(ME, "s", "b", bcc=FRIEND)


def test_subject_line_break_refused():
    with pytest.raises(send.SendRefused) as e:
        prepare(subject="Hi\nBcc: x@example.test")
    assert e.value.gate == "content"


# ---- 7. allowlist / own address ---------------------------------------------------

def test_stranger_refused():
    with pytest.raises(send.SendRefused) as e:
        prepare(to=STRANGER)
    assert e.value.gate == "allowlist"


def test_missing_allow_file_means_nobody(sandbox):
    (sandbox / "send_allow.json").unlink()
    for to in (ME, FRIEND):
        with pytest.raises(send.SendRefused) as e:
            prepare(to=to)
        assert e.value.gate == "allowlist"


@pytest.mark.parametrize("content", ["not json", "[]", '{"allow": "friend@example.test"}', '{"self": 5}'])
def test_broken_allow_file_means_nobody(sandbox, content):
    (sandbox / "send_allow.json").write_text(content)
    with pytest.raises(send.SendRefused) as e:
        prepare(to=FRIEND)
    assert e.value.gate == "allowlist"


def test_allowlist_removed_after_prepare(sandbox):
    d = Driver()
    p = prepare(to=FRIEND)
    (sandbox / "send_allow.json").write_text(json.dumps({"allow": []}))
    with pytest.raises(send.SendRefused) as e:
        go(p, d)
    assert e.value.gate == "allowlist" and not d.calls


# ---- 8. secrets (OpenJarvis patterns) ---------------------------------------------

@pytest.mark.parametrize("body", [
    "my key is sk-" + "a" * 24,
    "AKIA" + "A" * 16,
    "-----BEGIN PRIVATE KEY-----",
    'password = "hunter22"',
    "ghp_" + "x" * 36,
    "ssn 123-45-6789",
    "card 4111 1111 1111 1111",
])
def test_secrets_block_prepare(body):
    with pytest.raises(send.SendRefused) as e:
        prepare(body=body)
    assert e.value.gate == "secrets"


def test_secret_in_subject_blocked():
    with pytest.raises(send.SendRefused) as e:
        prepare(subject="xoxb-1234567890abc")
    assert e.value.gate == "secrets"


def test_ordinary_mail_passes_the_scanner():
    prepare(body="Hi Sam,\n\nSee you at 3pm in room 204. Call me at the office if late.\n\nAlex")


# ---- 9. rate limit ----------------------------------------------------------------

def test_three_per_hour(sandbox):
    d = Driver()
    for _ in range(3):
        go(prepare(), d)
    with pytest.raises(send.SendRefused) as e:
        prepare()
    assert e.value.gate == "rate" and len(d.calls) == 3


def test_rate_checked_again_at_send(sandbox):
    d = Driver()
    pending = [prepare() for _ in range(4)]
    for p in pending[:3]:
        go(p, d)
    with pytest.raises(send.SendRefused) as e:
        go(pending[3], d)
    assert e.value.gate == "rate" and len(d.calls) == 3


def test_failed_attempts_count_toward_the_limit(sandbox):
    for _ in range(3):
        with pytest.raises(send.SendRefused):
            go(prepare(), Driver("ERR mail.google.com | x"))
    with pytest.raises(send.SendRefused) as e:
        prepare()
    assert e.value.gate == "rate"


def test_old_sends_age_out(sandbox):
    rows = [{"at": 1000.0, "event": "attempt", "to": ME, "hash": "x"}] * 3
    (sandbox / "send_log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert send.recent_sends(now=1000.0 + 3601) == 0
    assert send.recent_sends(now=1000.0 + 10) == 3


# ---- 10. gmail driver outcome / test fence ----------------------------------------

def test_driver_error_is_a_refusal():
    with pytest.raises(send.SendRefused) as e:
        go(prepare(), Driver("ERR mail.google.com | refused a restored draft | body | nothing sent"))
    assert e.value.gate == "gmail"


def test_unknown_outcome_is_returned_not_retried():
    d = Driver("UNKNOWN mail.google.com | clicked Send once")
    assert go(prepare(), d).startswith("UNKNOWN") and len(d.calls) == 1


def test_real_gmail_driver_refused_under_pytest(monkeypatch):
    called = []
    monkeypatch.setattr(send, "gmail_send", lambda *a: called.append(a) or send.SENT)
    p = prepare()
    with pytest.raises(send.SendRefused) as e:
        send.send_draft(p["token"], p["to"], p["subject"], p["body"], approval=click())
    assert e.value.gate == "test" and not called


# ---- log ----------------------------------------------------------------------------

def test_log_is_append_only_and_has_no_subject_or_body(sandbox):
    go(prepare(subject="Secret plans", body="Meet at the zebra statue"), Driver())
    with pytest.raises(send.SendRefused):
        prepare(to=STRANGER)
    text = (sandbox / "send_log.jsonl").read_text()
    assert "Secret plans" not in text and "zebra" not in text
    events = [r["event"] for r in log_rows(sandbox)]
    assert events[:3] == ["prepared", "attempt", "sent"]
    assert set(log_rows(sandbox)[0]) <= {"at", "event", "to", "hash", "gate"}


def test_refusals_are_logged(sandbox):
    p = prepare()
    with pytest.raises(send.SendRefused):
        send.send_draft(p["token"], p["to"], p["subject"], p["body"], approval=None, driver=Driver())
    assert log_rows(sandbox)[-1] == {**log_rows(sandbox)[-1], "event": "refused", "gate": "click"}


def test_unwritable_log_refuses(sandbox, monkeypatch):
    blocker = sandbox / "file"
    blocker.write_text("x")
    monkeypatch.setenv(send.DIR_ENV, str(blocker / "sub"))
    with pytest.raises(Exception):
        send.prepare_send(ME, "s", "b", draft_id=DRAFT, is_flux_draft=flux)


# ---- every path without all gates raises --------------------------------------------

GATES = ["flag", "flux draft", "click", "token", "content", "one recipient", "allowlist", "secrets", "rate"]


@pytest.mark.parametrize("missing", GATES)
def test_each_missing_gate_alone_blocks_and_never_calls_the_driver(sandbox, monkeypatch, missing):
    d = Driver()
    to, subject, body = ME, "Hello", "Hi."
    if missing == "rate":
        rows = [{"at": 10**10, "event": "attempt", "to": ME, "hash": "x"}] * 3
        (sandbox / "send_log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        monkeypatch.setattr(send.time, "time", lambda: 10**10 + 1)
    if missing == "allowlist":
        to = STRANGER
    if missing == "one recipient":
        to = f"{ME},{FRIEND}"
    if missing == "secrets":
        body = "-----BEGIN RSA PRIVATE KEY-----"
    if missing == "flag":
        monkeypatch.setenv(send.ALLOW_ENV, "0")
    with pytest.raises(send.SendRefused) as e:
        if missing in ("click", "token", "content"):
            p = prepare(to, subject, body)
            token = "nope" if missing == "token" else p["token"]
            approval = None if missing == "click" else click()
            body2 = body + "!" if missing == "content" else body
            send.send_draft(token, to, subject, body2, approval=approval, driver=d)
        else:
            kw = {"is_flux_draft": send._not_flux} if missing == "flux draft" else {}
            prepare(to, subject, body, **kw)
    assert e.value.gate == missing
    assert not d.calls
