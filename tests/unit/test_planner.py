#!/usr/bin/env python3
"""TDD tests for M06 Option A: Additive Smart-Search Planner Recorder.

Covers:
- StageRecord frozen dataclass round-trip (to_dict / from_dict)
- PlannerRecord frozen dataclass round-trip
- PlannerRecord with multiple stages
- PlannerRecord version field
- Empty PlannerRecord (no stages)
- Extra fields survive round-trip
- EvidencePack round-trip preserves additive search_plan provenance
- Orchestrator output includes planner provenance when include_evidence=True
- Existing ranking behavior unchanged with planner provenance
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tools.evidence.builder import build_evidence_pack
from tools.evidence.types import EvidencePack
from tools.search_journals.orchestrator import SmartSearchOrchestrator

# ---------------------------------------------------------------------------
# StageRecord
# ---------------------------------------------------------------------------


class TestStageRecord:
    """StageRecord round-trips through to_dict / from_dict."""

    def test_import(self) -> None:
        from tools.smart_search.planner import StageRecord

        assert StageRecord is not None

    def test_round_trip(self) -> None:
        from tools.smart_search.planner import StageRecord

        stage = StageRecord(
            name="rewrite",
            status="success",
            latency_ms=12.5,
        )
        d = stage.to_dict()
        stage2 = StageRecord.from_dict(d)
        assert stage2 == stage
        assert stage2.name == "rewrite"
        assert stage2.status == "success"
        assert stage2.latency_ms == 12.5

    def test_round_trip_with_parameters(self) -> None:
        from tools.smart_search.planner import StageRecord

        stage = StageRecord(
            name="search",
            status="success",
            latency_ms=45.0,
            parameters={"query": "test query", "limit": 20},
        )
        d = stage.to_dict()
        stage2 = StageRecord.from_dict(d)
        assert stage2.parameters == {"query": "test query", "limit": 20}

    def test_defaults(self) -> None:
        from tools.smart_search.planner import StageRecord

        stage = StageRecord(name="search", status="success", latency_ms=0.0)
        assert stage.parameters is None or stage.parameters == {}
        assert isinstance(stage.extra, dict)

    def test_frozen(self) -> None:
        from tools.smart_search.planner import StageRecord

        stage = StageRecord(name="search", status="success", latency_ms=10.0)
        with pytest.raises(AttributeError):
            stage.name = "changed"  # type: ignore[misc]

    def test_extra_fields_survive(self) -> None:
        from tools.smart_search.planner import StageRecord

        stage = StageRecord(
            name="search",
            status="success",
            latency_ms=10.0,
            extra={"custom_field": 42},
        )
        d = stage.to_dict()
        assert d["custom_field"] == 42
        stage2 = StageRecord.from_dict(d)
        assert stage2.extra["custom_field"] == 42


# ---------------------------------------------------------------------------
# PlannerRecord
# ---------------------------------------------------------------------------


class TestPlannerRecord:
    """PlannerRecord round-trips through to_dict / from_dict."""

    def test_import(self) -> None:
        from tools.smart_search.planner import PlannerRecord

        assert PlannerRecord is not None

    def test_round_trip_empty(self) -> None:
        from tools.smart_search.planner import PlannerRecord

        record = PlannerRecord()
        d = record.to_dict()
        record2 = PlannerRecord.from_dict(d)
        assert record2 == record
        assert record2.planner_version == "0.1.0"
        assert record2.stages == []

    def test_round_trip_with_stages(self) -> None:
        from tools.smart_search.planner import PlannerRecord, StageRecord

        stages = [
            StageRecord(name="rewrite", status="success", latency_ms=5.0),
            StageRecord(name="search", status="success", latency_ms=20.0),
            StageRecord(name="filter", status="skipped", latency_ms=0.0),
        ]
        record = PlannerRecord(stages=stages)
        d = record.to_dict()
        record2 = PlannerRecord.from_dict(d)
        assert len(record2.stages) == 3
        assert record2.stages[0].name == "rewrite"
        assert record2.stages[1].name == "search"
        assert record2.stages[2].name == "filter"
        assert record2.stages[2].status == "skipped"

    def test_version_field(self) -> None:
        from tools.smart_search.planner import PlannerRecord

        record = PlannerRecord()
        assert record.planner_version == "0.1.0"
        d = record.to_dict()
        assert d["planner_version"] == "0.1.0"

    def test_frozen(self) -> None:
        from tools.smart_search.planner import PlannerRecord

        record = PlannerRecord()
        with pytest.raises(AttributeError):
            record.planner_version = "9.9.9"  # type: ignore[misc]

    def test_extra_fields_survive(self) -> None:
        from tools.smart_search.planner import PlannerRecord

        record = PlannerRecord(extra={"run_id": "abc123"})
        d = record.to_dict()
        assert d["run_id"] == "abc123"
        record2 = PlannerRecord.from_dict(d)
        assert record2.extra["run_id"] == "abc123"


# ---------------------------------------------------------------------------
# EvidencePack with additive planner provenance
# ---------------------------------------------------------------------------


def _make_search_result(**overrides: Any) -> dict[str, Any]:
    """Build a minimal search result dict for evidence pack tests."""
    base: dict[str, Any] = {
        "query_params": {"query": "test"},
        "merged_results": [
            {
                "title": "Test Entry",
                "date": "2026-03-01",
                "snippet": "test snippet",
                "source": "fts",
                "relevance": 80.0,
                "final_score": 80.0,
                "confidence": "high",
                "path": "Journals/2026/03/test.md",
            }
        ],
        "semantic_results": [],
        "total_available": 1,
        "has_more": False,
        "no_confident_match": False,
    }
    base.update(overrides)
    return base


class TestPlannerProvenanceInEvidencePack:
    """Planner provenance is additive in EvidencePack.query_context.search_plan."""

    def test_evidence_pack_preserves_existing_search_plan(self) -> None:
        """Existing search_plan from query preprocessor is preserved."""
        result = _make_search_result(
            search_plan={
                "intent_type": "recall",
                "query_mode": "natural_language",
            }
        )
        pack = build_evidence_pack(result)
        assert pack.query_context.search_plan is not None
        assert pack.query_context.search_plan["intent_type"] == "recall"

    def test_evidence_pack_round_trip_with_planner_provenance(self) -> None:
        """EvidencePack round-trips when search_plan contains planner provenance."""
        result = _make_search_result(
            search_plan={
                "intent_type": "recall",
                "query_mode": "keyword",
                "orchestrator_stages": [
                    {
                        "name": "rewrite",
                        "status": "success",
                        "latency_ms": 5.0,
                    },
                    {
                        "name": "search",
                        "status": "success",
                        "latency_ms": 20.0,
                    },
                ],
                "planner_version": "0.1.0",
            }
        )
        pack = build_evidence_pack(result)
        d = pack.to_dict()
        pack2 = EvidencePack.from_dict(d)
        sp = pack2.query_context.search_plan
        assert sp is not None
        assert "orchestrator_stages" in sp
        assert len(sp["orchestrator_stages"]) == 2
        assert sp["orchestrator_stages"][0]["name"] == "rewrite"

    def test_evidence_pack_without_planner_provenance(self) -> None:
        """EvidencePack without planner provenance still round-trips."""
        result = _make_search_result(search_plan=None)
        pack = build_evidence_pack(result)
        d = pack.to_dict()
        pack2 = EvidencePack.from_dict(d)
        assert pack2.query_context.search_plan is None

    def test_evidence_pack_empty_search_plan(self) -> None:
        """EvidencePack with empty search_plan dict still round-trips."""
        result = _make_search_result(search_plan={})
        pack = build_evidence_pack(result)
        d = pack.to_dict()
        pack2 = EvidencePack.from_dict(d)
        # Empty dict should be preserved
        assert pack2.query_context.search_plan == {}


# ---------------------------------------------------------------------------
# Orchestrator integration: planner recording is additive
# ---------------------------------------------------------------------------


class TestOrchestratorPlannerIntegration:
    """Orchestrator records planner provenance without changing behavior."""

    @patch("tools.search_journals.orchestrator._get_search_fn")
    def test_search_includes_planner_stages_with_evidence(self, mock_get_search: MagicMock) -> None:
        """When include_evidence=True, result includes planner provenance."""
        mock_get_search.return_value = lambda **kw: {
            "merged_results": [
                {
                    "title": "Test",
                    "date": "2026-03-01",
                    "snippet": "test",
                    "source": "fts",
                    "relevance": 80.0,
                    "final_score": 80.0,
                    "confidence": "high",
                    "path": "Journals/2026/03/test.md",
                }
            ],
            "semantic_results": [],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
            "performance": {"total_time_ms": 10.0},
            "query_params": {"query": "test"},
        }
        orch = SmartSearchOrchestrator()
        result = orch.search("test query", include_evidence=True)

        assert result["success"]
        # Evidence pack should exist
        assert "evidence_pack" in result
        ep = result["evidence_pack"]
        # search_plan should contain orchestrator_stages
        sp = ep.get("query_context", {}).get("search_plan")
        assert sp is not None
        assert "orchestrator_stages" in sp

    @patch("tools.search_journals.orchestrator._get_search_fn")
    def test_search_without_evidence_still_works(self, mock_get_search: MagicMock) -> None:
        """Without include_evidence, search still succeeds (no behavior change)."""
        mock_get_search.return_value = lambda **kw: {
            "merged_results": [
                {
                    "title": "Test",
                    "date": "2026-03-01",
                    "snippet": "test",
                    "source": "fts",
                    "relevance": 80.0,
                    "final_score": 80.0,
                    "confidence": "high",
                    "path": "Journals/2026/03/test.md",
                }
            ],
            "semantic_results": [],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
            "performance": {"total_time_ms": 10.0},
            "query_params": {"query": "test"},
        }
        orch = SmartSearchOrchestrator()
        result = orch.search("test query")

        assert result["success"]
        assert "evidence_pack" not in result
        # Filtered results should be present and unchanged
        assert len(result["filtered_results"]) == 1

    @patch("tools.search_journals.orchestrator._get_search_fn")
    def test_ranking_unchanged_with_planner(self, mock_get_search: MagicMock) -> None:
        """Planner recording does not change result ranking."""
        items = [
            {
                "title": f"Entry {i}",
                "date": "2026-03-01",
                "snippet": f"snippet {i}",
                "source": "fts",
                "relevance": float(90 - i * 10),
                "final_score": float(90 - i * 10),
                "confidence": "high" if i == 0 else "medium",
                "path": f"Journals/2026/03/test_{i}.md",
            }
            for i in range(3)
        ]
        mock_get_search.return_value = lambda **kw: {
            "merged_results": items,
            "semantic_results": [],
            "total_available": 3,
            "has_more": False,
            "no_confident_match": False,
            "performance": {"total_time_ms": 10.0},
            "query_params": {"query": "test"},
        }
        orch = SmartSearchOrchestrator()
        result = orch.search("test query", include_evidence=True)

        # Same order as input
        titles = [r["title"] for r in result["filtered_results"]]
        assert titles == ["Entry 0", "Entry 1", "Entry 2"]
