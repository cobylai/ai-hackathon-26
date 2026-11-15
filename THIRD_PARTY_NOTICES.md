# Third-party notices

Code copied into this repository from other projects, with its source, commit and license.
Other agents may add sections; extend this file, do not overwrite it.

## OpenJarvis (Apache-2.0)

- Source: https://github.com/open-jarvis/OpenJarvis
- File: `src/openjarvis/agents/native_react.py` at commit `77bff2548ad155ffd29a4d2e0d9c56c1eaaa754b`
- Copied to: `third_party/openjarvis/strict_json.py`
- What: `_unique_json_object` and `_reject_json_constant` (strict JSON parsing: duplicate keys
  and NaN/Infinity rejected) and the rule of `_parse_json_response` that a reply is one whole
  JSON object and a partial tool call is never salvaged.
- Changes: only those helpers kept; a new `parse_object()` wraps them, accepts one optional
  ```` ```json ```` fence and returns `None` on any failure. Change note in the file header.
- License: Apache License 2.0, full text in `third_party/openjarvis/LICENSE`.

## Ideas used, no code copied

- smolagents (Apache-2.0, https://github.com/huggingface/smolagents @ `96f33faaf028479119ec8d34507b47694cf14e34`,
  `src/smolagents/memory.py`): step records with action, observation, tokens and timing, and
  "summary mode" for older steps. Re-implemented in `reason/agent.py`.
- OpenHuman (GPL-3.0, https://github.com/tinyhumansai/openhuman @ `f52ec22161503edbf04ebb42e50ec31b141a8523`):
  looked at the shape of its approval cards only. No code copied, so nothing here is GPL.
