# ai-hackathon-26
AI hackathon 2026

## `harness`

Text tools that let a small local model drive a hidden browser and work with
Gmail. Plan: [docs/plan/00-overview.md](docs/plan/00-overview.md).
Email tools, one-time sign-in, and the no-send / draft-safety rules:
[docs/email.md](docs/email.md).

```bash
uv sync
uv run python -m harness login https://mail.google.com   # once, visibly
uv run pytest -q
```
