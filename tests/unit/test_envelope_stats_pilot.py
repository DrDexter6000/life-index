#!/usr/bin/env python3
"""
Envelope contract tests for the entity --stats pilot (ADR-018).

These tests verify that the pilot tool produces output conforming to the
unified success envelope schema defined in ADR-018:

    {ok: true, data: {...}, _trace: {...}, events: [...]}

This file is the golden/contract test for the envelope migration pilot.
Other tools migrated in Round 17+ should follow this same pattern.
"""

from __future__ import annotations

from pathlib import Path


def _rich_graph() -> list[dict]:
    """Graph with multiple types, relationships, and aliases."""
    return [
        {
            "id": "person-a",
            "type": "person",
            "primary_name": "张三",
            "aliases": ["老张", "张哥"],
            "attributes": {},
            "relationships": [
                {"target": "person-b", "relation": "colleague_of"},
                {"target": "place-001", "relation": "lives_in"},
            ],
        },
        {
            "id": "person-b",
            "type": "person",
            "primary_name": "李四",
            "aliases": [],
            "attributes": {},
            "relationships": [
                {"target": "person-a", "relation": "colleague_of"},
            ],
        },
        {
            "id": "place-001",
            "type": "place",
            "primary_name": "拉各斯",
            "aliases": ["Lagos"],
            "attributes": {},
            "relationships": [],
        },
    ]


def _save_graph(entities: list[dict], path: Path) -> None:
    from tools.lib.entity_graph import save_entity_graph

    save_entity_graph(entities, path)


class TestEnvelopeSchemaContract:
    """Verify the pilot tool output matches the ADR-018 envelope schema."""

    def test_envelope_has_ok_true(self, isolated_data_dir: Path) -> None:
        from tools.entity.stats import compute_stats

        _save_graph(_rich_graph(), isolated_data_dir / "entity_graph.yaml")

        result = compute_stats(graph_path=isolated_data_dir / "entity_graph.yaml")

        assert "ok" in result
        assert result["ok"] is True

    def test_envelope_has_data_key(self, isolated_data_dir: Path) -> None:
        from tools.entity.stats import compute_stats

        _save_graph(_rich_graph(), isolated_data_dir / "entity_graph.yaml")

        result = compute_stats(graph_path=isolated_data_dir / "entity_graph.yaml")

        assert "data" in result
        assert isinstance(result["data"], dict)

    def test_envelope_has_trace_key(self, isolated_data_dir: Path) -> None:
        from tools.entity.stats import compute_stats

        _save_graph(_rich_graph(), isolated_data_dir / "entity_graph.yaml")

        result = compute_stats(graph_path=isolated_data_dir / "entity_graph.yaml")

        assert "_trace" in result
        assert isinstance(result["_trace"], dict)

    def test_envelope_has_events_key(self, isolated_data_dir: Path) -> None:
        from tools.entity.stats import compute_stats

        _save_graph(_rich_graph(), isolated_data_dir / "entity_graph.yaml")

        result = compute_stats(graph_path=isolated_data_dir / "entity_graph.yaml")

        assert "events" in result
        assert isinstance(result["events"], list)

    def test_original_payload_nested_in_data(self, isolated_data_dir: Path) -> None:
        """The original stats payload fields are nested inside result['data']."""
        from tools.entity.stats import compute_stats

        _save_graph(_rich_graph(), isolated_data_dir / "entity_graph.yaml")

        result = compute_stats(graph_path=isolated_data_dir / "entity_graph.yaml")

        data = result["data"]
        assert "total_entities" in data
        assert "by_type" in data
        assert "total_aliases" in data
        assert "total_relationships" in data
        assert "top_referenced" in data
        assert "top_cooccurrence" in data

    def test_data_payload_values_correct(self, isolated_data_dir: Path) -> None:
        """Verify actual data values are preserved through envelope wrapping."""
        from tools.entity.stats import compute_stats

        _save_graph(_rich_graph(), isolated_data_dir / "entity_graph.yaml")

        result = compute_stats(graph_path=isolated_data_dir / "entity_graph.yaml")

        data = result["data"]
        assert data["total_entities"] == 3
        assert data["by_type"]["person"] == 2
        assert data["by_type"]["place"] == 1

    def test_envelope_defaults_empty_graph(self, isolated_data_dir: Path) -> None:
        """Empty graph still produces valid envelope with empty defaults."""
        from tools.entity.stats import compute_stats

        result = compute_stats(graph_path=isolated_data_dir / "entity_graph.yaml")

        assert result["ok"] is True
        assert result["data"]["total_entities"] == 0
        assert result["_trace"] == {}
        assert result["events"] == []


class TestEnvelopeHelperUnit:
    """Unit tests for tools.lib.envelope.success() helper."""

    def test_success_basic(self) -> None:
        from tools.lib.envelope import success

        result = success({"count": 42})

        assert result["ok"] is True
        assert result["data"] == {"count": 42}
        assert result["_trace"] == {}
        assert result["events"] == []

    def test_success_with_trace(self) -> None:
        from tools.lib.envelope import success

        trace = {"trace_id": "abc12345", "total_ms": 12.3}
        result = success({"entries": []}, trace=trace)

        assert result["_trace"] == trace

    def test_success_with_events(self) -> None:
        from tools.lib.envelope import success

        events = [{"type": "index_stale", "severity": "low"}]
        result = success({"status": "ok"}, events=events)

        assert result["events"] == events

    def test_success_trace_never_none(self) -> None:
        from tools.lib.envelope import success

        result = success({})
        assert result["_trace"] is not None
        assert result["_trace"] == {}

    def test_success_events_never_none(self) -> None:
        from tools.lib.envelope import success

        result = success({})
        assert result["events"] is not None
        assert result["events"] == []
