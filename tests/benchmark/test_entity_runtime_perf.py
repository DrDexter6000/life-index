#!/usr/bin/env python3
"""
Entity Runtime View performance baseline tests — Round 7 Phase 1 Task 5.

Validates that runtime view construction and repeated lookup remain fast
relative to the existing entity graph performance thresholds.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import save_entity_graph
from tools.lib.entity_runtime import build_runtime_view, resolve_via_runtime


def _generate_entities(n: int) -> list[dict[str, Any]]:
    """Generate n entities with aliases and relationships."""
    entities = []
    for i in range(n):
        entities.append(
            {
                "id": f"entity_{i}",
                "type": "person",
                "primary_name": f"人物{i}",
                "aliases": [f"P{i}", f"别名{i}"],
                "attributes": {},
                "relationships": [
                    {
                        "target": f"entity_{(i + 1) % n}",
                        "relation": "friend",
                    }
                ],
            }
        )
    return entities


class TestEntityRuntimePerformance:
    """Performance baselines for runtime view construction + lookup."""

    def test_build_runtime_view_100_entities_under_50ms(self, tmp_path: Path) -> None:
        entities = _generate_entities(100)
        start = time.perf_counter()
        view = build_runtime_view(entities)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n[100 entities] Runtime view build: {elapsed_ms:.2f}ms")
        assert elapsed_ms < 50, f"Build time {elapsed_ms}ms exceeds 50ms"
        assert len(view.by_lookup) > 0

    def test_build_runtime_view_500_entities_under_200ms(self, tmp_path: Path) -> None:
        entities = _generate_entities(500)
        start = time.perf_counter()
        view = build_runtime_view(entities)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n[500 entities] Runtime view build: {elapsed_ms:.2f}ms")
        assert elapsed_ms < 200, f"Build time {elapsed_ms}ms exceeds 200ms"

    def test_resolve_via_runtime_100_entities_under_1ms(self, tmp_path: Path) -> None:
        entities = _generate_entities(100)
        view = build_runtime_view(entities)

        start = time.perf_counter()
        for _ in range(1000):
            resolve_via_runtime("人物50", view)
        elapsed_ms = (time.perf_counter() - start) * 1000

        per_lookup_ms = elapsed_ms / 1000
        print(f"\n[100 entities] Per-lookup: {per_lookup_ms:.4f}ms")
        assert per_lookup_ms < 1, f"Per-lookup {per_lookup_ms}ms exceeds 1ms"

    def test_resolve_via_runtime_500_entities_under_1ms(self, tmp_path: Path) -> None:
        entities = _generate_entities(500)
        view = build_runtime_view(entities)

        start = time.perf_counter()
        for _ in range(1000):
            resolve_via_runtime("人物250", view)
        elapsed_ms = (time.perf_counter() - start) * 1000

        per_lookup_ms = elapsed_ms / 1000
        print(f"\n[500 entities] Per-lookup: {per_lookup_ms:.4f}ms")
        assert per_lookup_ms < 1, f"Per-lookup {per_lookup_ms}ms exceeds 1ms"

    def test_runtime_view_reverse_lookup_correctness(self, tmp_path: Path) -> None:
        """Verify reverse relationships are correct under load."""
        entities = _generate_entities(100)
        view = build_runtime_view(entities)

        # entity_0 has relationship to entity_1
        assert "entity_1" in view.reverse_relationships
        reverse = view.reverse_relationships["entity_1"]
        assert ("entity_0", "friend") in reverse
