# Why Flux is built this way: outside evidence, our evidence, and the limits

Written 2026-11-15. This is a support document for the pitch, not proof. It separates what other people have published, what we measured ourselves, and what neither shows. The outside sources were read as search summaries, not as full papers, so check a claim in the source before quoting it.

## Short version

Published work on small models and tools agrees with the design choices in `docs/plan/00-overview.md`: few tools, short names, flat arguments, numbered choices, and code (not the model) doing whatever code can do. That makes the design reasonable. It does not show the product is worth building or that it works as well as we hope. Our own demo numbers are the stronger argument, and they have limits too.

## Outside evidence

| Source | What it says | Which of our choices it supports |
|---|---|---|
| [Don't Adapt Small Language Models for Tools; Adapt Tool Schemas to the Models](https://arxiv.org/abs/2510.07248) (Lee, Song, Han, Pyun, Jo; Seoul National University; also in the [ACL Anthology](https://aclanthology.org/2026.acl-long.948/)) | Small models often invent plausible tool names that are not in the tool list, because they follow naming habits from pretraining. The fix is to reshape the schemas to match what the model already knows (the method is called PA-Tool). Smaller models gain the most. | Short, obvious tool names; at most 5 tools per group; numbered choices so the model never has to invent a name. |
| [Respan: agent tools best practices](https://www.respan.ai/articles/agent-tools-best-practices) | Many small tools beat one tool with a long, conditional schema; a model can compose small tools but cannot reason about a 12-argument schema. | Tools take at most 3 flat arguments (strings or ints). |
| [Notes on Building Agentic Tools Using Local LLMs](https://rdrn.dev/ai-agents) | Tool ergonomics make small local models workable, and without a verification step small mistakes propagate. | Code does routing, ranking, due dates and "what did X ask"; the model only picks or summarises; every tool returns a status line first. |
| [Can Small Agent Collaboration Beat a Single Big LLM?](https://arxiv.org/html/2601.11327v1) | On one benchmark (GAIA), 4B models with tools beat 32B models without tools. | Small local model plus tools is a defensible bet. One benchmark and one setup, so it does not transfer automatically. |
| [Rethinking Scale: Deployment Trade-offs of Small Language Models under Agent Paradigms](https://arxiv.org/pdf/2604.19299) | Agent-centric design matters for deploying small models under resource limits. | General support for building around the agent layer, not just the model. |

What these sources do not say: that a bundle of browser, search, email and computer control is something people want, or that our specific system is accurate.

## Our own evidence (measured on this project)

| Area | Result | Source file |
|---|---|---|
| Web search | 4/12 on the first live run (search engines blocked the browser), then 12/12 after five fixes with pacing; median 19 s, median 2,842 prompt tokens. | `docs/plan/notes-search-eval.md` on `feature/web-search` |
| Computer control | 5/5 live TextEdit jobs, about 1.6 s total, 1,901 characters to the model, zero confirmations needed. | `docs/plan/notes-computer-eval.md` on `feature/computer-control` |
| Email | Search plus read about 7 s, 1,809 characters per flow; `email_asks` 28.5 s then 6.4 s after clicking rows instead of reloading. | `docs/plan/notes-email-eval.md` on `feature/email-gmail` |
| Merged app (partner test) | Tests pass (274 pytest, 30/49/41 unittest); demo bank 37/38; all typed demo questions as expected; the same answers with real Wi-Fi off; spoken questions routed correctly. | `docs/PARTNER-TEST-REPORT.md` on `partner-testing` |

## Limits we should say out loud

- The questions were ours and the samples are small (12 search questions, 5 computer jobs, one email flow).
- The search eval used Qwen 9B through LM Studio, not Bonsai 4B.
- The strongest results (people, due dates) come from plain code, so they show the routing works, not that a small model is smart.
- One search run had no live bot-wall events, so the wall handling was only tested on fixtures.
- The partner test found a real bug: a Reddit "Prove your humanity" page was saved into the bank as an answer. It is fixed in the phrase list on `partner-testing`; the web route should also refuse to save any blocked page.
- Voice was only tested online. Spoken names can be misheard, and a misheard name goes to the web route.

## How we differ from a similar project

[CopilotKit/openfuse](https://github.com/CopilotKit/openfuse) is a self-hosted personal agent with a browser, Gmail and Calendar, and a Docker terminal. From its README (we read the front page only): it defaults to cloud models (gpt-5), needs a CopilotKit Intelligence project key in every mode, uses a hosted search service (queries leave the machine), has no desktop control, and sends telemetry to PostHog by default. Flux runs on a local model, works offline from a local bank, controls macOS apps, and only saves email drafts (it has no send function). Worth borrowing: its reviewed-action pattern for external effects and its "take control" handoff for sign-in.

## Suggested way to use this

Use the outside sources to explain why the tools look the way they do. Use the numbers and the offline demo to show it works. State the limits above before anyone else does.
