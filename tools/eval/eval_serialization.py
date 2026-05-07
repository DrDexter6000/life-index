#!/usr/bin/env python3
"""Serialization adapters for eval data model (R2-B1).

Thin I/O layer on top of eval_types dataclasses:
  load_eval_run(path) -> EvalRun
  save_eval_run(eval_run, path)

These are the public entry points for reading/writing baseline JSONs.
No serving-path changes. No eval behavior changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.eval.eval_types import EvalRun


def load_eval_run(path: str | Path) -> EvalRun:
    """Load a baseline JSON and return a typed EvalRun."""
    with open(path, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return EvalRun.from_dict(data)


def save_eval_run(eval_run: EvalRun, path: str | Path) -> None:
    """Serialize an EvalRun to JSON, creating parent dirs if needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(eval_run.to_dict(), f, ensure_ascii=False, indent=2)
        f.write("\n")


def canonicalize(data: dict[str, Any]) -> dict[str, Any]:
    """Return a canonical JSON-safe dict for semantic equality comparison."""
    return dict(json.loads(json.dumps(data, sort_keys=True)))


def assert_semantic_equal(a: dict[str, Any], b: dict[str, Any]) -> None:
    """Assert two dicts are semantically equal after canonical JSON round-trip."""
    assert canonicalize(a) == canonicalize(b)
