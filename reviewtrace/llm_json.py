"""Shared safe JSON parser for LLM outputs.

LLMs frequently add markdown fences, preamble text, or trailing commentary
around JSON. This module provides a single extraction helper used by all
pipeline stages that parse LLM output as JSON.
"""

from __future__ import annotations

import json
from typing import Any


def parse_llm_json(raw: str | None) -> Any:
    """Parse JSON from raw LLM output, tolerating common formatting issues.

    Handles:
    - None or empty string → raises ValueError
    - Leading/trailing whitespace
    - Markdown code fences (```json ... ``` or ``` ... ```)
    - Prose before/after the JSON value

    Raises ValueError with a concise message if parsing fails.
    """
    if not raw or not raw.strip():
        raise ValueError("LLM returned empty output")

    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        inner: list[str] = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            inner.append(line)
        text = "\n".join(inner).strip()

    # Fast path: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Locate the outermost JSON object or array
    first_curly = text.find("{")
    first_bracket = text.find("[")

    if first_curly == -1 and first_bracket == -1:
        raise ValueError("No JSON object or array found in LLM output")

    if first_curly != -1 and (first_bracket == -1 or first_curly <= first_bracket):
        start = first_curly
        end = text.rfind("}") + 1
    else:
        start = first_bracket
        end = text.rfind("]") + 1

    if end <= start:
        raise ValueError("Could not locate JSON boundaries in LLM output")

    extracted = text[start:end]
    try:
        return json.loads(extracted)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse failed: {exc}") from exc
