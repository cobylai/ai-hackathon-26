# Log: reasoning-layer

- 2026-11-14: `reason/` built: `answer(question, today)`, with due, person and bank-then-web/offline routes picked in code, plus the `python -m reason` chat loop. 18 tests pass with no model server. Live results are in docs/reasoning-layer.md.
- 2026-11-14 ruling (thinker, via helper 0c): accepted that the web route files the question, answer and quoted line (subject "<question> <answer>") instead of the whole page, because the bank's summary of a whole page lost the answer offline.
- 2026-11-14 known miss, no fix (thinker ruling): "What year was Cornell University founded?" went through the web route and answered 1868, quoting an Ezra Cornell line dated 1868 on cornell.edu. Cornell was founded in 1865 and opened in 1868. The demo and video use only web questions that have been run and checked beforehand.
- 2026-11-14: merged into integration (brief J step 1). The reason (18), bank (49), sufficiency (41) and harness (271 passed, 3 skipped) test sets all pass. `python -m reason` answered the due, person and bank example questions.
