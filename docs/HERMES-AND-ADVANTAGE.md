# Flux vs Hermes Agent: where Flux wins, and what to borrow (2026-11-15)

Written for Antranig and Coby. Hermes facts come from secondary write-ups
(Better Stack, Jimmy Song, OrcaRouter; official docs are at
hermes-agent.nousresearch.com). **Nobody has read the Hermes source yet.** The
"borrow" list below should be checked against the repo before building.

## What Hermes Agent is (MIT, Nous Research)

- A general agent that runs tools for you, built around a **learning loop**.
- **Skills**: after a multi-step task or a correction, it writes the workflow
  to a `SKILL.md` file and refines it on later use. Follows the open
  agentskills.io format.
- **Memory**: plain Markdown files (`memory.md`, `user.md`), plus full-text
  search over past sessions (SQLite FTS5) with the model summarizing hits.
- **Self-review**: every ~10 turns it asks itself whether anything belongs in
  memory or should become a skill.
- Works with any provider (Nous, OpenRouter, OpenAI, Anthropic). It is built for
  strong models and long open-ended tasks.

## Where Flux has a real advantage

| | Hermes (general agent) | Flux |
|---|---|---|
| Where the model runs | Mostly cloud models | Local Bonsai 4B only; works with Wi-Fi off (proven) |
| Your data | Sent to the provider as context | Mail, calendar and notes stay on the Mac |
| Who does the work | The model plans and calls tools | **Code** finds, dates, sorts; the model only picks or judges |
| Speed on routine asks | Seconds, model-bound | 0.0 s for due / person / calendar (no model) |
| Answer you can check | Free-form | Every answer lists its source; refuses instead of guessing ("I have nothing from X") |
| Acting | Broad tool use | Narrow, allowlisted, always asks yes, **never sends** |
| Hardware | Needs a strong model | Runs on an 8 GB MacBook Air |

Short version: **Flux is a private, offline, cited answer engine for your own
mail, calendar and coursework that runs on a small model.** Hermes is a capable
general agent. Flux should not try to out-reason it. It wins on privacy,
offline, speed, trust and cost. The danger is the opposite: on anything it can't
answer, Flux must say so, not guess (see `docs/ROUTING-REDESIGN.md`).

## What to borrow (with the small-model constraint)

1. **Corrections become examples** (Hermes: skills from corrections). When the
   user says "no, I meant my calendar", log `{question, right route}` on the Mac
   and add it to the router's few-shot examples and to the eval set. Confirm
   first. Never let it edit rules or code on its own.
2. **Markdown memory the user can read.** Flux already keeps notes
   (`remember`, Discover). Keep them as plain files and show "what I learned" in
   the window so the user can delete a line. Hermes's `user.md` is the model.
3. **Search past chats.** `~/flux-chats` exists. Add full-text search so
   "what did we decide about the cabin trip" can find an earlier chat. Local
   SQLite FTS5, no model needed.
4. **Skills as files = our playbooks.** Playbooks are already Hermes-style
   skills (markdown with triggers, wording, examples). The borrow is
   *generating* a new playbook row from a confirmed correction, not new
   machinery. Consider agentskills.io compatibility only if it is cheap.
5. **Periodic self-review, offline.** A nightly job (not every 10 turns, since
   Bonsai is slow and busy) that lists misroutes and low-confidence answers for
   the user to approve.

**Not worth borrowing:** model-planned multi-step tool use, cloud providers,
RL trajectory tooling. They need a stronger model and break the privacy story.

## Testing with an outside model (agreed rule)

An outside model (DeepSeek) may write **test data and prompts at build time**.
The app, and every run that checks whether the app works, uses local Bonsai
only. Send outside models made-up questions only, never real mail or calendar.

- `scripts/gen_routing_eval.py` writes `reason/tests/routing_eval.jsonl`.
  Set `DEEPSEEK_API_KEY` for DeepSeek, otherwise it uses LM Studio. The local
  Qwen 9B thinking model timed out (180 s for 4 lines), so use DeepSeek.
- `python -m reason.route_eval` scores it. Baseline on the 125 seed questions
  (no paraphrases yet, follow-ups and open/draft/sync questions skipped):
  **101/102 right, 1 wrongly sent to the web** ("what did I forget").
  Those seeds are the rules' own examples, so the high score is expected. The
  real test is the paraphrases.
