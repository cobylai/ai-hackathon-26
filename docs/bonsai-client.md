# Bonsai client

Every LLM call in Flux goes through `llm/client.py`, which talks only to the local Bonsai 2 server. It has no other provider and no fallback. It only uses the standard library, plus the `tokenizers` package (already in the Bonsai venv) for counting tokens.

## Start the server

```bash
scripts/serve_bonsai.sh        # BONSAI_SIZE, else 4B
scripts/serve_bonsai.sh 9B     # 2B | 4B | 9B
```

- It uses the models and venv in the main checkout (`samples/bonsai-models/mlx/models`, `.venv`), including when run from a worktree. You can override them with `BONSAI_MODELS_DIR` and `BONSAI_VENV`.
- It is headless. It never opens the chat page and never downloads. If a model is missing, it stops and prints the one-time download command.
- It sets `HF_HUB_OFFLINE=1` and refuses to start if port 8080 is already taken. Run only one server at a time.
- The 4B model loads in about 2 seconds. Stop it with Ctrl-C or `pkill -f mlx_vlm.server`.

## Call it

Run with the venv's Python (`samples/bonsai-models/mlx/.venv/bin/python`) from the repo root.

```python
from llm import complete, complete_json, chat, split_to_budget, BudgetError, ServerDown

text = complete("Summarise this email: ...", system="Be brief.", max_tokens=300)

data = complete_json("Extract the fields from this email: ...",
                     json_schema_hint='{"sender": str, "deadlines": [str]}')
# Parses the reply, tolerating code fences. On invalid JSON it retries once
# (showing the model its bad reply), then raises JSONReplyError.

r = chat(messages, max_tokens=400, thinking=False)  # Reply: .text .prompt_tokens .seconds .reasoning
```

- **Sampling presets** come from the model card and are sent on every request: temperature, top_p, top_k, min_p, presence_penalty and repetition_penalty. Without them the server decodes greedily.
- **Thinking** is off by default. Pass `thinking=True` to turn it on. The default output reservation then rises to 8192 tokens, as the model card advises. The reasoning text goes in `Reply.reasoning` and is kept out of `.text`.
- **The model id** is read from the server's loaded entry. The client checks that it matches `BONSAI_SIZE` and raises an error if it does not, so you can't benchmark the wrong size by mistake.
- **If the server is down**, `ServerDown` tells you the command that starts it. `BONSAI_BASE_URL` must point at localhost; anything else raises an error.

## Budget rules (32k)

- `CONTEXT_TOKENS = 32768`, following the hackathon rule. The model card says 262k, but we hold to 32k.
- Before every send, the client checks that the prompt tokens plus `max_tokens` fit in 32,768. If they don't, it raises `BudgetError` with the numbers. It never truncates silently.
- For long input such as scraped pages, call `split_to_budget(text, n)`. It splits into chunks of at most `n` tokens, breaking at blank lines first, then lines, then sentences, then raw tokens. `trim_to_budget(text, n)` returns only the first chunk.
- **Token counting** uses the model's own `tokenizer.json`, through `tokenizers`, and works offline. All three sizes share one tokenizer file, and they have the same md5. Each message adds 6 tokens of chat-template overhead, plus 8 for the reply primer. Checked against the server's reported `prompt_tokens`, it counted 23 against 21 for a short prompt and 3024 against 3020 for a 3k one. So it overcounts slightly, which is the safe direction. If `tokenizers` can't be imported, it falls back to len/2.5, which is a conservative estimate.

## Switch size

There is one setting: the `BONSAI_SIZE` env var (2B | 4B | 9B, default 4B), defined in `llm/config.py`. Both the serve script and the client read it.

```bash
BONSAI_SIZE=9B scripts/serve_bonsai.sh
BONSAI_SIZE=9B python -m your_app
```

## Model check: 4B vs 9B

Fixtures are in `llm/eval/fixtures/` and are all synthetic: 10 student emails and 8 question-and-page pairs, 4 that answer and 4 that don't. Run the check with `BONSAI_SIZE=<size> python -m llm.eval.run_check` against a server of that size. Results go to `llm/eval/results/<size>.json`. Both sizes got identical prompts with non-thinking presets, and only one model was loaded at a time.

| | 4B | 9B |
|---|---|---|
| Extraction correct (all 4 fields) | 6/10 | 6/10 |
| Extraction JSON valid first try | 10/10 | 10/10 |
| Field: sender / date / ask / deadlines | 9 / 10 / 8 / 9 | 10 / 10 / 9 / 7 |
| Extraction median s/call | 1.15–1.22 | 1.94 |
| Sufficiency correct | 5/8 | 5/8 |
| Sufficiency valid label | 8/8 | 8/8 |
| Sufficiency median s/call | 0.37–0.39 | 0.57 |
| Peak server memory (phys footprint) | 2.2 GB | 3.8 GB |

The 4B range comes from two runs. Sampling is not greedy (temperature 0.7), so expect small differences between runs.

What the misses were:
- **Sufficiency:** both sizes answered "not enough" for the same three pages that do answer the question: weather, course due dates and gym hours. Both got all four "not enough" pages right. Because the miss is identical across sizes, the prompt probably leans toward "not enough". Model size doesn't seem to be the cause.
- **4B extraction:** it missed a "tomorrow" deadline (e04). It gave a "Visit the website" line as the ask in a newsletter (e05). It returned the sender's name instead of their address in the long, messy email (e07). It missed the "pay" ask in an automated bursar email (e09).
- **9B extraction:** 3 of its 4 misses came from turning weekday deadlines into ISO dates when the prompt asked for them as written. One of those dates was correct ("tomorrow" became 2026-11-13). Two were wrong: Monday became 11-15, and Thursday became 11-14. The scorer checks for the deadline words as written. It also missed the bursar ask (e09), as 4B did.
- The scoring is strict keyword matching (see `score_extraction` in `llm/eval/run_check.py`).
