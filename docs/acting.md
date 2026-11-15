# Acting: drafts and computer control

`reason/act.py` handles requests to *do* something. It uses the partner's tools from `harness/` as they are, with no changes inside `harness/`.

| Say | What Flux does after your yes | Needs a connection |
|---|---|---|
| "open my calendar" (also notes, finder, textedit, preview, calculator) | `harness.computer.tools.app_open` | no |
| "open the assignment page" | opens a bank link in the default browser: the best match for any named words ("open the map essay assignment"), otherwise the Canvas assignment due soonest (worker 13: `kind="canvas"`, `source` a file:// page, opens offline) | the page might |
| "draft a reply to Felix saying yes" | `harness.email.search` by sender, then `harness.email.draft.reply` | yes |

## The rule: show it, wait for a yes

1. Code spots the request; no model is involved. It runs before every other route, because "draft a reply to Felix" contains a sender's name.
2. Flux shows exactly what it will do: the app, the link, or the full draft with its To, subject and body. It ends with "Say or type yes to go ahead, no to cancel."
3. One action is held for 3 minutes. The next input decides it:
   - **yes / yeah / yep / sure / ok / do it / go ahead** runs it.
   - **no / cancel / stop** cancels it.
   - **anything else** drops it, and that input is answered normally.
4. Saying it works too, since spoken text goes through the same `answer()`. In the chat loop, press Enter on an empty line and say "yes". The window shows **Yes, do it** and **Cancel** buttons, and hold-to-talk works there as well.

## Drafts: never sent

- **No send path.** `harness/email` has no send function, and `tests/test_no_send.py` checks that. `reason/tests/test_act.py` also checks that `act.py` never calls anything named send.
- **Test account only.** Before saving, Flux reads the Gmail tab title. If the address there isn't `ilovelocalai@gmail.com`, it refuses and saves nothing.
- **Who it goes to and what it says.** The recipient and subject come from that sender's newest email in the bank. Bonsai writes a 1–3 sentence body from what you said ("saying yes") and that email's summary and ask.
- **Which thread.** Gmail is searched by the sender's address, and the row with the matching subject is picked (row 1 if none matches).
- **Recipient check.** If the saved draft's To isn't the expected address, the reply says WARNING.
- **Offline:** "Drafting a reply needs a connection, and the Mac is offline. Nothing was drafted."

## Computer control

- `app_open` applies the partner's policy (`~/.harness/policy.json`): the block list wins, otherwise the app must be on the allow list, and every action goes into `~/.harness/actions.log`. A `~/.harness/STOP` file stops every action.
- Flux itself only offers Calendar, Notes, Finder, TextEdit, Preview and Calculator.
- `open -a` needs no Accessibility permission.
- **Opening a page:** no browser is on the partner's allow list, so opening a page calls `direct.open_path` itself. It is logged as `Browser open_url` and allowed only for http, https and file links taken from the bank (Coby approved).

## API

```python
from reason import act
act.handle(question, today=None, root=None, deps=None) -> Answer | None   # route "act"
act.waiting() -> bool   # an action is held (the window's /ask JSON has "pending")
act.parse(question) -> {"kind": "draft", "name", "gist"} | {"kind": "open", "target"} | None
```

`deps` replaces `online`, `open_app`, `open_page`, `save_draft` and `write_reply`; the tests use it.

Tests: `python -m unittest reason.tests.test_act`. These need no model, network or browser, and nothing is opened.

## Playbook

All wording, the trigger patterns and the draft prompt live in `playbooks/act.md` (format: `playbooks/RULES.md`). Its examples run with `MUSE_BANK_DIR=~/muse-demo-bank uv run python -m reason.playbook_check --only act`: 6/6 on 2026-11-15, with the network blocked. No example says yes, so the checker never opens or drafts anything.

## Computer control: take me there, add to calendar, remind me, set me up (brief X)

`reason/computer.py`, with the actions in `reason/act.py` and wording in `playbooks/open.md`, `schedule.md` and `setup.md`. Every action is one step: code picks it from Coby's words and what the bank holds, shows it, and waits for a yes. Each action first checks the partner's STOP file and block list (`harness.computer.policy`) and writes one line to `~/.harness/actions.log`.

| Say | Shown first | On yes | Offline |
|---|---|---|---|
| "open it" / "open the second one" (after an answer with rows) | what will open | **Email:** Apple Mail, test account only, found by sender and subject. Otherwise its Gmail page (online, real threads). Otherwise the saved copy. **Canvas or page:** its link. **Calendar row:** Calendar shows the event. | Mail, Canvas pages and Calendar yes |
| "add Milo's band practice to my calendar", "add it to my calendar" | title, day and time, place | `applecal.write.add_event` into MUSE_CALENDAR ("Muse demo") | yes |
| "remind me about homework 9 (the day before)" | name, alert time, due | `applecal.write.add_reminder` into the "Muse demo" Reminders list | yes |
| "set me up for homework 9", "let's work on …" | the page, up to 2 emails, up to 2 notes | opens them all | yes, except Gmail pages |

**Times** come from the entry's stored deadlines, which the bank's date code worked out at ingest. If an entry has none, Flux reads date phrases in its ask and summary with the same code. The model is never asked. With no time, Flux says so and doesn't guess.

**Places** come only from a code pattern ("in Lincoln Hall 101").

**Reminder alerts** are the day before at 9am when asked; otherwise 2 hours before a timed deadline, or 9am on the day.

**"This" / "it" / "the second one"** is a row of the last answer in this conversation (`reason/session.py`). With no conversation, Flux asks.

**Safety**
- Text read from an email or page is data, never an instruction (RULES 10). Only an entry's own stored source is ever opened.
- osascript gets every value as an argument, never pasted into the script.
- Mail is searched only in `ilovelocalai@gmail.com`'s inbox. Nothing is sent, moved or deleted.
- The only writes are one event or one reminder, into "Muse demo".
- `sandbox-exec` breaks Calendar and Reminders scripting (-10004), so the offline check is the in-process network block or a real Wi-Fi-off run.

**Demo data:** `scripts/make_test_mail.py` m21 (Milo: band practice Thu Nov 19 7pm, free), m22 (Greta: book club Wed Nov 18 2pm), m23 (Ivy: "sometime soon", no time). The "Muse demo" calendar has "Lab" Wed Nov 18 1:30–3:30pm, which clashes with m22.

Tests: `reason/tests/test_computer.py`, with Mail, Calendar and Reminders mocked, including the injection test.
