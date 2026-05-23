"""Cycle2 multi-signal fixture loader.

Loads per-category JSON query files from a cycle2-multi-signal gold fixture
directory and returns them in the standard eval query format.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CYCLE2_CATEGORIES = (
    "C1_keyword_exact",
    "C2_paraphrase",
    "C3_temporal",
    "C4_entity_heavy",
)


def load_cycle2_queries(fixture_dir: Path) -> list[dict[str, Any]]:
    """Load cycle2 multi-signal queries from per-category JSON files.

    Expected fixture layout::

        fixture_dir/
            C1_keyword_exact.json
            C2_paraphrase.json
            C3_temporal.json
            C4_entity_heavy.json

    Each JSON file contains a list of query objects with at least:
    ``id``, ``query``, ``category``, ``expected`` (dict with ``min_results``).
    """
    fixture_dir = Path(fixture_dir)
    if not fixture_dir.exists():
        raise FileNotFoundError(f"Cycle2 fixture directory not found: {fixture_dir}")

    queries: list[dict[str, Any]] = []
    json_files = sorted(fixture_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in cycle2 fixture dir: {fixture_dir}")

    for json_file in json_files:
        data = json.loads(json_file.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"Cycle2 fixture {json_file.name} must contain a JSON list")
        for item in data:
            if not isinstance(item, dict):
                raise ValueError(f"Cycle2 fixture {json_file.name} contains non-dict item")
            queries.append(item)

    return queries
