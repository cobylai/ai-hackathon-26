# Mock Canvas: sample coursework in the bank

Canvas works the same way as the Gmail page fixtures ("Demo bank" in `docs/integration.md`).
Three real Canvas pages are saved once. A generator rewrites them into made-up sample
coursework, and a reader files the fake assignments into the bank. The due route
(`reason/`, unchanged) then lists them alongside mail. The demo says it is **sample coursework**.

## Pieces

| File | What it does |
|---|---|
| `scripts/save_canvas_pages.py <canvas url>` | Opens a visible Chromium on a scratch profile (`data/canvas-profile`) and waits up to 5 minutes while you sign in (Duo push or passcode; Touch ID doesn't work there). It then saves `dashboard.html`, one course's `assignments.html` and one `assignment.html` to `data/canvas-templates/`. These hold real data: gitignored, never committed. |
| `scripts/make_test_canvas.py [--templates DIR] [--out DIR] [--today YYYY-MM-DD]` | Builds 24 assignments across 4 made-up courses (fixed list, seed 13). Due dates run from today-3 to today+14, and `--today` moves them. It writes them into copies of the real markup, then writes `dashboard.html`, `<course>/assignments.html`, `<course>/<id>.html` and `truth.json`. It drops scripts, styles, frames and images. It first collects the templates' real course names, assignment titles, user name, Canvas host and ids. It stops, writing nothing, if any of them (or any email address) is left in a page. |
| `canvas/read.py` | lxml reader for those pages (real Canvas classes and data-testids). `read_assignment_list`, `read_assignment`, `read_dashboard` -> course, title, due date/time (local, `$FLUX_TZ`, default America/New_York), `file://` link, description. Offline, no browser, no model. |
| `scripts/sync_test_canvas.py [DIR]` | Reads every course list and assignment page and files each assignment with `bank.ingest(kind="canvas", sender_name=course, subject=title, source=link, sent_date=truth's today, deadlines=[due date from the page])`. Bonsai writes only the summary and ask. It then checks course, title, due date/time and link against `truth.json`. It refuses any bank folder without "test" or "demo" in its name. |

Bank side: `bank.ingest` takes `kind="canvas"` and a `deadlines=` argument that replaces the model's deadlines.
Both are additive (see `docs/INTERFACES.md` §5).

## Add the fake Canvas to the demo bank (one command, Bonsai up)

The saved templates are in `~/flux-demo-canvas-templates/` (outside every checkout, real data).
The pages go to `~/flux-demo-canvas/`, which is where the bank's `file://` links point.

```bash
DAY=2026-11-15; uv run python scripts/make_test_canvas.py --today $DAY --templates ~/flux-demo-canvas-templates --out ~/flux-demo-canvas && FLUX_BANK_DIR=~/flux-demo-bank uv run python scripts/sync_test_canvas.py ~/flux-demo-canvas
```

Run it after the mail regeneration in `docs/integration.md`, which starts with `rm -rf ~/flux-demo-bank`.
Re-running only adds what's missing (same `source` = duplicate), but rebuilding for a new DAY
needs the bank rebuilt first, because the old entries keep their old due dates.

## Result (2026-11-14, Bonsai 4B, built for Sun 2026-11-15)

- `data/bank-canvas-test` (a copy of `~/flux-demo-bank` plus Canvas): 24 filed, **24/24 match**
  on course, title, due date/time and link, in 79 s.
- With all non-localhost network denied (`sandbox-exec`), `python -m reason --today 2026-11-15`
  answers "what's due this week" with 21 rows (Nov 15 to Nov 22). 14 are Canvas
  rows mixed in by date with the 7 mail rows, e.g. "Thu Nov 19 noon  Submit the revised essay 2 as a
  PDF with your peer review notes attached (HIST 2147 Maps and Empires, Nov 15)".
- The "Nov 15" in a Canvas row is the sync date: Canvas pages show no posted date.
- Known wrinkle: some summaries (from the model) start "This email ...".

Tests: `uv run python -m pytest -q canvas` (10, no model server), using hand-written templates
in `canvas/tests/templates/` with invented stand-ins for the real strings.
