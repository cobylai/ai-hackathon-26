# Confirmed send (branch `feature/agent-confirmed-send`)

**Off by default.** With `FLUX_ALLOW_SEND` unset (the demo, every test, every suite), Flux still
sends nothing, and the README line "nothing is ever sent" stays true. "Send it" then answers
"Sending is off, so nothing was sent."

No email was sent while building this. There is no live send test. The Gmail driver was never
run; a test makes sure it is refused under pytest.

## What was built

| Part | File |
|---|---|
| The only send path: `prepare_send` (pause: preview + one-time token), `send_draft` (resume: needs a clicked approval), `cancel`, the Gmail driver `gmail_send` | `harness/email/send.py` |
| The "send it" route: shows the preview, never sends | `reason/send.py`, `playbooks/send.md` (route `send`, 5 steps, 3 examples) |
| Window: `Send…` in the draft box (only when the server says sending is on), a read-only preview box with **Send** and **Cancel**; `POST /send/prepare`, `/send/confirm`, `/send/cancel`; `/status` has `"send": bool` | `reason/web.py` |
| Draft ids Flux made (`is_flux_draft`), the newest draft (`last_draft`), cleared on a new or reopened chat | `reason/compose.py` |
| Secret / PII patterns (vendored, Apache-2.0) | `third_party/openjarvis/scanner.py`, `THIRD_PARTY_NOTICES.md` |
| Rules wording: send is the one exception, only with the flag and a click | `playbooks/RULES.md` rules 6, 12, 13; `README.md` Drafts line |

### How it works

1. You make a draft as before ("draft an email to me about …", or a reply). It is a Flux draft:
   its id exists only in this window's process.
2. Either type or say **"send it"** (route `send`: uses the newest Flux draft as Flux wrote it), or
   click **Send…** in the draft box (uses the box's current To / Subject / body, edits included).
3. The server calls `prepare_send`, which checks the flag, that it is a Flux draft, one recipient,
   the allowlist or your own address, secrets and the rate limit, then returns the exact text
   and a token bound to the sha256 of exactly that To, Subject and body (5 minutes, one use).
4. The window shows that text read-only with **Send** and **Cancel**. Nothing waits for a yes:
   a typed or spoken "yes" does nothing (`pending` is false; there is no Yes row).
5. Only a real click on **Send** (`event.isTrusted`) posts `/send/confirm` with the header
   `X-Flux-Send-Click: clicked`. The server builds a `UserApproval` from that request (method,
   path, header, and the Origin must be this window) and calls `send_draft` once. All gates are
   checked again, the token is consumed, then the Gmail driver opens a fresh compose, refuses a
   restored draft (`draft.blank_problem`), types, checks recipients (`draft.recipient_problem`),
   reads Subject and body back, finds exactly one Send button in that compose and clicks it once,
   then waits for "Message sent". No toast: "UNKNOWN … check Sent", and it is not retried.
6. Cancel drops the token. After one click, both buttons go away: a new send needs a new preview.

### Gates (each fails closed by raising `SendRefused(gate, why)`; the driver is never called)

| # | Gate | Checked in | Refuses when |
|---|---|---|---|
| 1 | flag | prepare and send | `FLUX_ALLOW_SEND` is anything but exactly `1` (unset, `0`, `true`, ` 1` …) |
| 2 | flux draft | prepare | the draft id is empty or was not made by Flux in this window (default check says no) |
| 3 | click | send | `approval` is not a `UserApproval`; one can't be built by hand; the request was not `POST /send/confirm` with the click header from this window's origin |
| 4 | token | send | unknown, already used (consumed even by a refused attempt), cancelled, older than 5 minutes, or dropped by a new chat |
| 5 | content | send | the sha256 of To / Subject / body differs from the previewed one (any change, even a space or a case) |
| 6 | one recipient | prepare and send | empty, a list (`,` `;` space), `Name <addr>`, not a plain address; Subject with a line break. There is no Cc or Bcc parameter at all |
| 7 | allowlist | prepare and send | the address is not in `~/.flux/send_allow.json` `"allow"` and is not your own (`"self"` there, or `FLUX_SELF_ADDRESS`). Missing or broken file: nobody |
| 8 | secrets | prepare and send | Subject or body has an API key, token, private key, password or connection string, an SSN or a card number (OpenJarvis patterns, HIGH and CRITICAL) |
| 9 | rate | prepare and send | 3 send attempts (sent, failed or unknown) in the last hour, read from the log |
| 10 | gmail | driver | not signed in, a restored draft, wrong recipients after typing, text read back differently, not exactly one Send button: closes as a draft, nothing sent |
| – | log | every step | `~/.flux/send_log.jsonl`, append-only (`O_APPEND`, mode 0600): time, event, recipient, 12-char hash, gate. Never a subject or body. If it can't be written, nothing is sent |
| – | text never triggers | structure | only `reason/web.py`'s click handler calls `send_draft` (and only after `UserApproval.from_click`); only `reason/send.py` calls `prepare_send`; nothing else imports the module; the model has no send tool. Checked by `tests/test_no_send.py` |

## Tests (all offline, fake driver, temp `FLUX_SEND_DIR`, made-up addresses)

- `tests/test_send_gates.py`: **91** (each gate, each gate alone missing blocks with the driver
  never called, single use, expiry, cancel, hash changes, allow file missing or broken, secrets,
  rate limit at prepare and at send, log has no subject or body, real driver refused under pytest).
- `tests/test_no_send.py`: **9** (was 4). The old "no send path" guards became "one fenced send
  path": Send markers and send functions only in `send.py`, no send tool, who may import and call.
- `reason/tests/test_send.py`: **16** (route matching, off by default, no draft, preview then yes /
  "send it" again never sends, text in an email never triggers, the window click path sends once,
  no header / other origin / edited / not a Flux draft / cancelled / new chat all refused).
- Suites on this branch: reason **194** OK (178 before), bank 72, sufficiency 54, applecal 10,
  canvas 11 OK, `uv run pytest -q` **371 passed** (275 before).
- `playbook_check`: **109/109** on the first run (106 + 3 send examples). Later runs gave
  107/109: the two Milo cases (compose "Draft a reply to Milo", suggest "What did Milo ask me?")
  fail because a leftover "Band practice Thursday" event is now in the Flux demo calendar at that
  time. That is the environment, not this branch (the coordinator sees the same on every branch);
  this branch does not touch the calendar.

## Your test: one self-addressed send (do this yourself; Flux's builder never sent anything)

Use the Gmail test account that is signed in at `~/.harness/profile`. Replace `YOU@EXAMPLE` with
that account's own address.

```bash
mkdir -p ~/.flux
printf '{"self": "YOU@EXAMPLE", "allow": []}\n' > ~/.flux/send_allow.json
cd ~/Desktop/flux-confirmed-send            # or main after the merge
FLUX_ALLOW_SEND=1 FLUX_BANK_DIR=~/flux-demo-bank uv run python -m reason.web --no-voice
```

1. In the window: `remember my name is Coby` is optional. Type
   `write an email to me about a confirmed send test`. It may ask "Who is this to?" or "What should
   it say?" (Bonsai must be running to write the body); answer briefly. When the draft box shows,
   put `YOU@EXAMPLE` in its **To** field (To is empty when no address is stored).
2. Check the box has a **Send…** button (it is missing when the flag is off).
3. Click **Send…**. A preview appears with the exact To, Subject and body.
4. Type `yes` in the ask box: nothing is sent (expected). Click **Send** in the preview.
5. Expect "Sent to YOU@EXAMPLE." Check the account's Sent folder and Inbox: one message.
6. Click **Send** again or reuse the preview: it is gone; a new send needs **Send…** again.
7. Negative checks (no mail should go out): change To to another address and click **Send…**
   ("is not in … send_allow.json"); type `send it` after restarting without `FLUX_ALLOW_SEND=1`
   ("Sending is off").
8. `cat ~/.flux/send_log.jsonl`: lines `prepared`, `attempt`, `sent`, and no subject or body.

Turn it off again by starting Flux without `FLUX_ALLOW_SEND=1` (the default). Delete
`~/.flux/send_allow.json` to empty the allowlist.

## Reused vs written

- **Reused:** OpenJarvis' secret and PII regex tables (Apache-2.0, vendored with its license,
  `third_party/openjarvis/`). The interrupt / approve flow follows LangGraph's interrupt-resume
  pattern (MIT) as a design only; no dependency. OpenHuman's `GateApprovalCard.tsx` (GPL-3.0) was
  read for the card design (one decision per request id, buttons cleared after it, deny drops it);
  **no OpenHuman code was copied**, so nothing here is under the GPL. Draft safety reuses
  `harness/email/draft.py` (`blank_problem`, `recipient_problem`, `compose_state`, …) unchanged.
- **Written:** `harness/email/send.py` (gates, tokens, log, the Gmail send driver), the pure-Python
  scan loop in the vendored file, `reason/send.py`, `playbooks/send.md`, the window endpoints and
  preview box, the tests.

## Not done / risks

- **The Gmail driver has never run.** The Send-button selectors
  (`div[role=button][aria-label^='Send']`, `data-tooltip^='Send'`) and the "Message sent" toast are
  from Gmail's usual markup but are not checked against the live page. The user test above is the
  first real run. If the button is not found, it refuses and leaves a draft (fails closed).
- The Mac app shows the same window page, so it gets the same Send box; not checked in the app.
- "Own address" comes from the allow file or `FLUX_SELF_ADDRESS`, not read from Gmail's account.
- Tokens live in the window server's memory: a restart drops them (that's fine, it fails closed).
- `send it` uses the draft as Flux wrote it; edits in the box need the box's **Send…**. The preview
  text says so.
- Reading a full body back from Gmail compares whitespace-normalised text; a body containing a
  `-- ` line is refused rather than sent (signature handling).
- Not added to `docs/reasoning-layer.md` / `docs/INTERFACES.md` yet (this file is the reference).
