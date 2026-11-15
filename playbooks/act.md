# Act

## For

Requests to do something: open an app, open a saved page, or draft a reply. "Open my calendar", "open the assignment page", "open the map essay assignment", "draft a reply to Felix saying yes", "write a reply to Lena that I'll be late". Muse always shows what it will do and waits for a yes, typed or spoken. It drafts and never sends.

## Triggers

- draft: `^(?:please\s+|can you\s+|could you\s+)?(?:(?:draft|write)\s+(?:a\s+|an\s+)?(?:quick\s+|short\s+)?(?:reply|response|answer|email)(?:\s+back)?|reply)\s+to\s+([A-Za-z][A-Za-z'\-]*)(?:'s\s+(?:email|message|mail))?(?:[\s,]+(?:saying|that says|to say|telling (?:him|her|them)|that)\s+(.+?))?(?:\s+(?:in gmail|as a gmail draft))?$`
- open: `^(?:please\s+|can you\s+|could you\s+|muse,?\s+)?(?:open|launch|pull up|bring up)\s+(?:up\s+)?(?:my\s+|the\s+)?(.+?)(?:\s+app)?(?:\s+please)?$`
- page: `page|link|site|website|assignment|canvas|syllabus|url`
- yes: `^(?:yes|yeah|yep|yup|sure|ok|okay|do it|go ahead|confirm|yes please|please do|yes do it|go for it)$`
- no: `^(?:no|nope|cancel|stop|dont|don't|no thanks|never mind|nevermind|cancel it|no dont|no don't)$`

A plain "draft a reply to …" goes to the compose route (`compose.md`, Open in Mail); `draft` here takes only "… in Gmail" / "… as a Gmail draft", for a draft saved in the test account's Gmail. `draft` and `open` are tried on the question with its end punctuation removed. Group 1 is the name (draft) or the thing to open; group 2 is what the reply should say. `yes` and `no` are tried on the question lowercased, with punctuation removed. The apps Muse offers are in code (`APPS` in `reason/act.py`): Calendar, Notes, Finder, TextEdit, Preview, Calculator.

## Steps

1. If an action is held (at most 3 minutes old): `yes` runs it (step 5), `no` cancels it, and any other input drops it and goes on. A lone yes or no with nothing held says `nothing_held`.
2. Match `draft` or `open`. If neither matches, this route passes and the other routes run.
3. Open: a listed app gets `open_app_preview`. If the target has a `page` word, pick a bank entry whose source is a web or file link: the best match for any named words, otherwise the Canvas assignment due soonest, otherwise the newest link. Show `open_page_preview` and hold the action.
4. Draft: offline says `needs_net`. Otherwise take the sender's newest email in the bank, have the model write the body with the prompt below, show `draft_preview`, and hold the action.
5. On yes, run it with the partner's tools. An app goes through `app_open` (allow list, block list, log). A page goes through `open_path`, logged as `Browser open_url`. A draft first checks that the Gmail tab title shows `ilovelocalai@gmail.com`, then runs `email_search` by the sender's address, picks the thread with the same subject, and calls `draft.reply`.

## May look

The bank (the sender's newest email; entries with a link). Gmail in the hidden harness browser, only after a yes, and only in the test account.

## May not look

Any other Gmail account, the web, apps not on the list, the model's own knowledge.

## Wording

- ask_yes: Say or type yes to go ahead, no to cancel.
- cancelled: Cancelled. Nothing was done.
- open_app_preview: I'll open {app}.
- opened_app: Opened {app}.
- open_app_failed: I couldn't open {app}: {why}
- open_page_preview: I'll open this page in your browser: {title} ({url})
- opened_page: Opened {url}.
- open_page_failed: I couldn't open {url}: {why}
- page_stopped: I couldn't open the page: {why}
- page_only_links: I only open web or file links.
- draft_preview_head: I'll save this reply as a draft in {account}. It won't be sent.
- draft_preview_to: To: {who} <{to}>
- draft_preview_subject: Subject: Re: {subject}
- draft_saved: Saved a reply draft to {to} in {account}'s Drafts. It was not sent.
- draft_warning: WARNING: Gmail addressed the draft to {got}, not {to}. Check it in Drafts.
- failed: That didn't work: {why}

Previews end with `ask_yes`. A draft preview shows the head, To and Subject lines, a blank line, then the body.

## Not found

- nothing_held: There's nothing waiting for a yes.
- only_apps: I can only open {apps}, or a page saved in the bank.
- no_link: I don't have a saved link for {target}.
- needs_net: Drafting a reply needs a connection, and the Mac is offline. Nothing was drafted.
- no_sender: I have nothing from {name}, so I can't find an email to reply to.
- cannot_write: I couldn't write that reply ({why}). Nothing was drafted.
- not_signed_in: Gmail isn't signed in, so nothing was drafted (run: harness login https://mail.google.com).
- wrong_account: Gmail is signed in as {account}, not {test}. I only save drafts in the test account, so nothing was drafted.
- no_thread: I couldn't find an email from {to} in Gmail, so nothing was drafted.
- draft_failed: The draft wasn't saved: {why}

## Never

- Never act without showing exactly what it will do and getting a yes.
- Never send mail. Draft only, and only in `ilovelocalai@gmail.com`.
- Never open an app that isn't on the list or is on the partner's block list.
- Never let the model choose the action, the recipient or the thread. The model only writes the draft body.

## Prompt

Step 4 only. Code fills in `{who}`, `{subject}`, `{summary}`, `{ask_line}` ("They asked: …" or empty), `{gist}` (what the user said, or "a short, friendly acknowledgement") and `{first}`. At most 200 tokens.

### draft_system
```text
You write short, plain email replies for a student. You write only the reply body. You never add facts that were not given.
```

### draft_prompt
```text
Write the student's reply to this email.

EMAIL FROM {who}
Subject: {subject}
Summary: {summary}
{ask_line}
WHAT THE REPLY SHOULD SAY: {gist}

Write one to three short sentences. Start with "Hi {first}," on its own line. No subject line, no signature, no placeholders.
```

## Examples

The checker blocks the network, so draft examples check the offline reply. No example says yes, so nothing is ever opened or drafted.

| question | route | answer contains |
|---|---|---|
| Open my calendar | act | I'll open Calendar; say or type yes |
| open Terminal | act | I can only open |
| Draft a reply to Felix saying yes in Gmail | act | needs a connection; Nothing was drafted |
| yes | act | nothing waiting |
| open the assignment page | act | |
| What did Felix ask me? | person | Felix |
