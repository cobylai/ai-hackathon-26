# Acting: drafts and computer control

`reason/act.py` handles requests to *do* something. It uses the partner's tools from `harness/` as they are, with no changes inside `harness/`.

| Say | What Muse does after your yes | Needs a connection |
|---|---|---|
| "open my calendar" (also notes, finder, textedit, preview, calculator) | `harness.computer.tools.app_open` | no |
| "open the assignment page" | opens a bank link in the default browser: the best match for any named words ("open the map essay assignment"), otherwise the Canvas assignment due soonest (worker 13: `kind="canvas"`, `source` a file:// page, opens offline) | the page might |
| "draft a reply to Felix saying yes" | `harness.email.search` by sender, then `harness.email.draft.reply` | yes |

## The rule: show it, wait for a yes

1. Code spots the request; no model is involved. It runs before every other route, because "draft a reply to Felix" contains a sender's name.
2. Muse shows exactly what it will do: the app, the link, or the full draft with its To, subject and body. It ends with "Say or type yes to go ahead, no to cancel."
3. One action is held for 3 minutes. The next input decides it:
   - **yes / yeah / yep / sure / ok / do it / go ahead** runs it.
   - **no / cancel / stop** cancels it.
   - **anything else** drops it, and that input is answered normally.
4. Saying it works too, since spoken text goes through the same `answer()`. In the chat loop, press Enter on an empty line and say "yes". The window shows **Yes, do it** and **Cancel** buttons, and hold-to-talk works there as well.

## Drafts: never sent

- **No send path.** `harness/email` has no send function, and `tests/test_no_send.py` checks that. `reason/tests/test_act.py` also checks that `act.py` never calls anything named send.
- **Test account only.** Before saving, Muse reads the Gmail tab title. If the address there isn't `ilovelocalai@gmail.com`, it refuses and saves nothing.
- **Who it goes to and what it says.** The recipient and subject come from that sender's newest email in the bank. Bonsai writes a 1–3 sentence body from what you said ("saying yes") and that email's summary and ask.
- **Which thread.** Gmail is searched by the sender's address, and the row with the matching subject is picked (row 1 if none matches).
- **Recipient check.** If the saved draft's To isn't the expected address, the reply says WARNING.
- **Offline:** "Drafting a reply needs a connection, and the Mac is offline. Nothing was drafted."

## Computer control

- `app_open` applies the partner's policy (`~/.harness/policy.json`): the block list wins, otherwise the app must be on the allow list, and every action goes into `~/.harness/actions.log`. A `~/.harness/STOP` file stops every action.
- Muse itself only offers Calendar, Notes, Finder, TextEdit, Preview and Calculator.
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
