#!/usr/bin/env python3
"""Entity Graph performance baseline tests (Task 2.3).

Goal: Establish performance baseline to decide if SQLite caching is needed.

Decision threshold:
- If 500 entities load time < 100ms → YAML is sufficient
- If > 500ms → Start SQLite caching project
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import yaml


def generate_entity_graph(num_entities: int) -> dict:
    """Generate a test entity graph with N entities."""
    entities = []
    for i in range(num_entities):
        entities.append(
            {
                "id": f"entity_{i}",
                "type": "person",
                "primary_name": f"Person {i}",
                "aliases": [f"P{i}", f"人物{i}"],
                "relationships": [
                    {"target": f"entity_{(i + 1) % num_entities}", "relation": "friend"}
                ],
            }
        )
    return {"entities": entities}


def benchmark_load_entity_graph(graph_path: Path) -> float:
    """Load entity graph from YAML and return time in ms."""
    start = time.perf_counter()
    with open(graph_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms


def benchmark_resolve_entity(graph: dict, entity_id: str) -> float:
    """Resolve an entity and return time in ms."""
    from tools.lib.entity_graph import resolve_entity

    start = time.perf_counter()
    _ = resolve_entity(entity_id, graph)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms


class TestEntityGraphPerformance:
    """Performance baseline tests for entity graph."""

    def test_load_100_entities(self, tmp_path: Path) -> None:
        """100 entities YAML load time."""
        graph_path = tmp_path / "entity_graph.yaml"
        graph = generate_entity_graph(100)
        with open(graph_path, "w", encoding="utf-8") as f:
            yaml.dump(graph, f, allow_unicode=True)

        load_time = benchmark_load_entity_graph(graph_path)

        print(f"\n[100 entities] Load time: {load_time:.2f}ms")

        # Decision: < 100ms is acceptable
        assert load_time < 100, f"Load time {load_time}ms exceeds 100ms threshold"

    def test_load_500_entities(self, tmp_path: Path) -> None:
        """500 entities YAML load time."""
        graph_path = tmp_path / "entity_graph.yaml"
        graph = generate_entity_graph(500)
        with open(graph_path, "w", encoding="utf-8") as f:
            yaml.dump(graph, f, allow_unicode=True)

        load_time = benchmark_load_entity_graph(graph_path)

        print(f"\n[500 entities] Load time: {load_time:.2f}ms")

        # Decision: < 100ms is acceptable, > 500ms needs SQLite
        if load_time > 500:
            print("  ⚠️ Exceeds 500ms threshold - SQLite caching recommended")

        assert load_time < 1000, f"Load time {load_time}ms is too slow"

    def test_resolve_entity_100(self, tmp_path: Path) -> None:
        """Resolve entity in 100-entity graph."""
        from tools.lib.entity_graph import load_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        graph = generate_entity_graph(100)
        with open(graph_path, "w", encoding="utf-8") as f:
            yaml.dump(graph, f, allow_unicode=True)

        loaded_graph = load_entity_graph(graph_path)
        resolve_time = benchmark_resolve_entity(loaded_graph, "entity_50")

        print(f"\n[100 entities] Resolve time: {resolve_time:.4f}ms")

        assert resolve_time < 10, f"Resolve time {resolve_time}ms is too slow"

    def test_resolve_entity_500(self, tmp_path: Path) -> None:
        """Resolve entity in 500-entity graph."""
        from tools.lib.entity_graph import load_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        graph = generate_entity_graph(500)
        with open(graph_path, "w", encoding="utf-8") as f:
            yaml.dump(graph, f, allow_unicode=True)

        loaded_graph = load_entity_graph(graph_path)
        resolve_time = benchmark_resolve_entity(loaded_graph, "entity_250")

        print(f"\n[500 entities] Resolve time: {resolve_time:.4f}ms")

        assert resolve_time < 50, f"Resolve time {resolve_time}ms is too slow"
