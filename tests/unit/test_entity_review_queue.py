#!/usr/bin/env python3
"""
Tests for Entity Review Hub — Round 7 Phase 2 Task 7.

Validates that:
- review_queue builds from audit issues with risk priority ordering
- Review items have machine-readable action choices
- Preview generation shows graph diff before commit
- Apply actions (merge as alias, keep separate, skip) produce correct outcomes
"""

from pathlib import Path

import pytest

from tools.lib.entity_graph import save_entity_graph


def _conflict_graph() -> list[dict]:
    """Graph with a duplicate-like scenario (edit-distance trigger).

    Uses names that are close enough to trigger audit's Levenshtein check,
    but different enough to pass entity_schema validation (no alias overlap).
    """
    return [
        {
            "id": "wife-001",
            "type": "person",
            "primary_name": "王晓丽",
            "aliases": ["团团妈"],
            "attributes": {},
            "relationships": [{"target": "author-self", "relation": "spouse_of"}],
        },
        {
            "id": "wife-002",
            "type": "person",
            "primary_name": "王晓里",  # edit distance 1 from 王晓丽
            "aliases": ["小王"],
            "attributes": {},
            "relationships": [{"target": "author-self", "relation": "spouse_of"}],
        },
        {
            "id": "author-self",
            "type": "person",
            "primary_name": "我",
            "aliases": [],
            "attributes": {},
            "relationships": [],
        },
    ]


def _save_graph(entities: list[dict], isolated_data_dir: Path) -> None:
    from tools.lib.entity_graph import save_entity_graph

    save_entity_graph(entities, isolated_data_dir / "entity_graph.yaml")


def _graph_path_for(isolated_data_dir: Path) -> Path:
    """Get the entity_graph.yaml path inside isolated data dir."""
    return isolated_data_dir / "entity_graph.yaml"


class TestReviewQueueBuilding:
    """Review queue aggregates audit issues + candidates."""

    def test_build_review_queue_from_audit(self, isolated_data_dir: Path) -> None:
        from tools.entity.review import build_review_queue

        _save_graph(_conflict_graph(), isolated_data_dir)

        queue = build_review_queue(graph_path=_graph_path_for(isolated_data_dir))

        assert isinstance(queue, list)
        assert len(queue) >= 1

    def test_review_queue_items_have_required_fields(
        self, isolated_data_dir: Path
    ) -> None:
        from tools.entity.review import build_review_queue

        _save_graph(_conflict_graph(), isolated_data_dir)

        queue = build_review_queue(graph_path=_graph_path_for(isolated_data_dir))

        required = {
            "item_id",
            "risk_level",
            "category",
            "description",
            "action_choices",
        }
        for item in queue:
            assert required.issubset(item.keys()), f"Missing: {required - item.keys()}"

    def test_review_queue_sorted_by_risk(self, isolated_data_dir: Path) -> None:
        from tools.entity.review import build_review_queue

        _save_graph(_conflict_graph(), isolated_data_dir)

        queue = build_review_queue(graph_path=_graph_path_for(isolated_data_dir))

        risk_order = {"high": 0, "medium": 1, "low": 2}
        for i in range(len(queue) - 1):
            current_risk = risk_order.get(queue[i]["risk_level"], 99)
            next_risk = risk_order.get(queue[i + 1]["risk_level"], 99)
            assert current_risk <= next_risk, (
                f"Queue not sorted: {queue[i]['risk_level']} before {queue[i + 1]['risk_level']}"
            )

    def test_high_risk_items_have_merge_action(self, isolated_data_dir: Path) -> None:
        from tools.entity.review import build_review_queue

        _save_graph(_conflict_graph(), isolated_data_dir)

        queue = build_review_queue(graph_path=_graph_path_for(isolated_data_dir))

        high_items = [i for i in queue if i["risk_level"] == "high"]

        if high_items:
            for item in high_items:
                assert (
                    "merge" in item["action_choices"]
                    or "merge_as_alias" in item["action_choices"]
                )




class TestReviewPreview:
    """Preview shows graph diff before commit."""

    def test_generate_preview(self, isolated_data_dir: Path) -> None:
        from tools.entity.review import generate_preview

        _save_graph(_conflict_graph(), isolated_data_dir)

        preview = generate_preview(
            item_id="test-1",
            action="keep_separate",
            graph_path=_graph_path_for(isolated_data_dir),
        )

        assert "action" in preview
        assert preview["action"] == "keep_separate"

    def test_preview_merge_as_alias(self, isolated_data_dir: Path) -> None:
        from tools.entity.review import generate_preview

        _save_graph(_conflict_graph(), isolated_data_dir)

        preview = generate_preview(
            item_id="test-merge",
            action="merge_as_alias",
            source_id="wife-002",
            target_id="wife-001",
            graph_path=_graph_path_for(isolated_data_dir),
        )

        assert "action" in preview
        assert preview["action"] == "merge_as_alias"


class TestReviewApplyAction:
    """Apply actions modify entity graph correctly."""

    def test_merge_as_alias(self, isolated_data_dir: Path) -> None:
        from tools.lib.entity_graph import load_entity_graph
        from tools.entity.review import apply_action

        _save_graph(_conflict_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        result = apply_action(
            action="merge_as_alias",
            source_id="wife-002",
            target_id="wife-001",
            graph_path=gp,
        )

        assert result["success"] is True

        # Verify: wife-002's aliases should now be on wife-001
        graph = load_entity_graph(gp)
        ids = {e["id"] for e in graph}
        assert "wife-002" not in ids  # source removed
        wife = next(e for e in graph if e["id"] == "wife-001")
        assert "王晓里" in wife["aliases"]
        assert "小王" in wife["aliases"]

    def test_keep_separate_no_change(self, isolated_data_dir: Path) -> None:
        from tools.lib.entity_graph import load_entity_graph
        from tools.entity.review import apply_action

        _save_graph(_conflict_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        result = apply_action(
            action="keep_separate",
            source_id="wife-002",
            graph_path=gp,
        )

        assert result["success"] is True

        # Verify: graph unchanged
        graph = load_entity_graph(gp)
        ids = {e["id"] for e in graph}
        assert "wife-002" in ids

    def test_skip_action(self, isolated_data_dir: Path) -> None:
        from tools.entity.review import apply_action

        _save_graph(_conflict_graph(), isolated_data_dir)

        result = apply_action(
            action="skip",
            source_id="wife-002",
            graph_path=_graph_path_for(isolated_data_dir),
        )

        assert result["success"] is True
        assert result.get("skipped") is True

    def test_apply_action_unknown_returns_error(self, isolated_data_dir: Path) -> None:
        from tools.entity.review import apply_action

        _save_graph(_conflict_graph(), isolated_data_dir)

        result = apply_action(
            action="unknown_action",
            source_id="wife-002",
            graph_path=_graph_path_for(isolated_data_dir),
        )

        assert result["success"] is False

    def test_apply_action_missing_source(self, isolated_data_dir: Path) -> None:
        from tools.entity.review import apply_action

        _save_graph(_conflict_graph(), isolated_data_dir)

        result = apply_action(
            action="merge_as_alias",
            source_id="nonexistent",
            target_id="wife-001",
            graph_path=_graph_path_for(isolated_data_dir),
        )

        assert result["success"] is False
