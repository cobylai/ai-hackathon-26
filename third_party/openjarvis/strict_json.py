# Copyright OpenJarvis contributors.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use
# this file except in compliance with the License. You may obtain a copy of the
# License at http://www.apache.org/licenses/LICENSE-2.0 (full text: ./LICENSE).
#
# Source: https://github.com/open-jarvis/OpenJarvis
#   src/openjarvis/agents/native_react.py @ 77bff2548ad155ffd29a4d2e0d9c56c1eaaa754b
#   (_unique_json_object, _reject_json_constant, and the "one whole JSON object, never
#   salvage a partial tool call" rule of _parse_json_response).
# Modified for Flux (2026-11-15): kept only the strict-parse helpers; parse_object()
# wraps them, accepts one optional ```json fence, and returns None instead of a ReAct
# dict. No network, no model calls.
"""Strict JSON parsing for a small model's one-object replies."""
from __future__ import annotations

import json
import re
from typing import Any


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise ValueError("Non-JSON numeric constant")


def parse_object(text: str) -> dict | None:
    """One complete JSON object, or None. Duplicate keys, NaN/Infinity, trailing prose
    and partial objects are rejected rather than repaired (OpenJarvis's rule: do not
    salvage a partial action)."""
    t = (text or "").strip()
    fenced = re.fullmatch(r"```(?:json)?[ \t]*\r?\n?(.*?)\r?\n?```", t, re.DOTALL | re.IGNORECASE)
    if fenced:
        t = fenced.group(1).strip()
    try:
        payload = json.loads(t, object_pairs_hook=_unique_json_object,
                             parse_constant=_reject_json_constant)
    except (ValueError, RecursionError):
        return None
    return payload if isinstance(payload, dict) else None
