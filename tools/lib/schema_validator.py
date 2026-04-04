#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

REQUIRED_TOP_LEVEL_FIELDS = {
    "$schema",
    "name",
    "description",
    "version",
    "parameters",
    "returns",
    "examples",
}


def validate_tool_schema(schema_path: Path) -> list[str]:
    errors: list[str] = []
    if not schema_path.exists():
        return [f"schema file not found: {schema_path}"]

    try:
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid json: {exc}"]

    if not isinstance(payload, dict):
        return ["schema must be a JSON object"]

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in payload:
            errors.append(f"missing required field: {field}")

    if payload.get("$schema") != "https://json-schema.org/draft-07/schema#":
        errors.append("$schema must be JSON Schema Draft-07")

    parameters = payload.get("parameters")
    if not isinstance(parameters, dict) or parameters.get("type") != "object":
        errors.append("parameters must be an object schema")

    returns = payload.get("returns")
    if not isinstance(returns, dict) or returns.get("type") != "object":
        errors.append("returns must be an object schema")

    examples = payload.get("examples")
    if not isinstance(examples, list):
        errors.append("examples must be a list")

    return errors
