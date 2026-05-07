#!/usr/bin/env python3
"""Typed loader helpers for golden query specifications (R2-B2).

Converts the untyped dict list from golden_queries.yaml (or post-overlay
dicts) into typed QuerySpec objects. Does not change eval behavior or
touch run_eval.py.

Usage:
    from tools.eval.eval_query_specs import dicts_to_query_specs, load_query_specs

    # From pre-loaded dicts:
    specs = dicts_to_query_specs(queries, applied_query_ids=applied_ids)

    # From YAML directly:
    specs = load_query_specs()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tools.eval.eval_types import QuerySpec

_GOLDEN_QUERIES_PATH = Path(__file__).with_name("golden_queries.yaml")


def dicts_to_query_specs(
    queries: list[dict[str, Any]],
    *,
    applied_query_ids: set[str] | None = None,
) -> list[QuerySpec]:
    """Convert a list of golden query dicts to typed QuerySpec objects."""
    return [QuerySpec.from_dict(q, applied_query_ids=applied_query_ids) for q in queries]


def load_query_specs(
    queries_path: Path | None = None,
    *,
    applied_query_ids: set[str] | None = None,
) -> list[QuerySpec]:
    """Load golden queries from YAML and convert to typed QuerySpec list."""
    path = queries_path or _GOLDEN_QUERIES_PATH
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    queries = payload.get("queries", []) if isinstance(payload, dict) else []
    return dicts_to_query_specs(queries, applied_query_ids=applied_query_ids)
