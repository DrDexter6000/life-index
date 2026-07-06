#!/usr/bin/env python3
"""TDD tests for Evidence Pack runtime adapter (R2-C2).

Covers:
- extract_evidence_from_search_result: valid extraction, missing keys
- extract_evidence_from_orchestrator: smart-result rewrite overlay, no smart-result
- Edge cases: semantic disabled, empty/no-confident-match, missing optional fields,
  duplicate semantic exclusion, input immutability
"""

from __future__ import annotations

import copy

import pytest

from tools.evidence.types import EvidencePack


def _synthetic_search_result() -> dict:
    """Synthetic hierarchical_search() output for testing."""
    return {
        "success": True,
        "query_params": {
            "query": "family day out",
            "expanded_query": "family day out 小云",
            "level": 3,
        },
        "merged_results": [
            {
                "path": "Journals/2026/03/life-index_2026-03-07_001.md",
                "title": "Family Day",
                "date": "2026-03-07",
                "snippet": "We went to the park with 小云",
                "source": "fts",
                "relevance": 90,
                "fts_score": 90.0,
                "semantic_score": 0.0,
                "rrf_score": 0.0,
                "final_score": 90.0,
                "search_rank": 1,
                "confidence": "high",
                "metadata": {
                    "topic": "family",
                    "tags": ["weekend"],
                    "location": "Beijing",
                    "abstract": "A beautiful family day.",
                },
            },
        ],
        "semantic_results": [
            {
                "path": "Journals/2026/02/life-index_2026-02-14_001.md",
                "title": "Valentine's Day",
                "date": "2026-02-14",
                "snippet": "A romantic evening",
                "similarity": 0.62,
                "source": "semantic",
                "metadata": {"topic": "love"},
            },
        ],
        "total_available": 1,
        "has_more": False,
        "no_confident_match": False,
        "semantic_effective_policy": "hybrid",
        "entity_hints": [
            {"matched_term": "小云", "entity_id": "tuan_tuan", "entity_type": "actor"},
        ],
        "search_plan": {"intent_type": "recall"},
        "warnings": [],
        "performance": {"total_time_ms": 110.5},
    }


# ---------------------------------------------------------------------------
# extract_evidence_from_search_result
# ---------------------------------------------------------------------------


class TestExtractFromSearchResult:
    """extract_evidence_from_search_result tests."""

    def test_valid_extraction(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_search_result

        result = _synthetic_search_result()
        pack = extract_evidence_from_search_result(result)

        assert isinstance(pack, EvidencePack)
        assert pack.query_context.query == "family day out"
        assert len(pack.items) == 1
        assert pack.items[0].document.title == "Family Day"
        assert pack.total_available == 1
        assert pack.has_more is False

    def test_raises_on_missing_query_params(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_search_result

        result = {"merged_results": [], "success": True}
        with pytest.raises(ValueError, match="query_params"):
            extract_evidence_from_search_result(result)

    def test_raises_on_missing_merged_results(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_search_result

        result = {"query_params": {"query": "test"}, "success": True}
        with pytest.raises(ValueError, match="merged_results"):
            extract_evidence_from_search_result(result)

    def test_raises_on_empty_dict(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_search_result

        with pytest.raises(ValueError):
            extract_evidence_from_search_result({})

    def test_matches_build_evidence_pack_output(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_search_result
        from tools.evidence.builder import build_evidence_pack

        result = _synthetic_search_result()
        adapter_pack = extract_evidence_from_search_result(result)
        builder_pack = build_evidence_pack(result)

        assert adapter_pack == builder_pack


# ---------------------------------------------------------------------------
# extract_evidence_from_orchestrator
# ---------------------------------------------------------------------------


class TestExtractFromOrchestrator:
    """extract_evidence_from_orchestrator tests."""

    def test_smart_result_rewrite_overlay(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_orchestrator

        raw = _synthetic_search_result()
        smart = {"rewritten_query": "what did I do with family"}
        pack = extract_evidence_from_orchestrator(raw, smart_result=smart)

        assert pack.query_context.extra.get("rewritten_query") == "what did I do with family"
        # expanded_query must NOT be overwritten — it's entity expansion, not LLM rewrite
        assert pack.query_context.expanded_query == "family day out 小云"

    def test_no_smart_result(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_orchestrator

        raw = _synthetic_search_result()
        pack = extract_evidence_from_orchestrator(raw, smart_result=None)

        assert "rewritten_query" not in pack.query_context.extra
        assert pack.query_context.query == "family day out"

    def test_smart_result_same_as_original_query_no_overlay(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_orchestrator

        raw = _synthetic_search_result()
        smart = {"rewritten_query": "family day out"}
        pack = extract_evidence_from_orchestrator(raw, smart_result=smart)

        assert "rewritten_query" not in pack.query_context.extra

    def test_smart_result_empty_rewritten_query_no_overlay(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_orchestrator

        raw = _synthetic_search_result()
        smart = {"rewritten_query": ""}
        pack = extract_evidence_from_orchestrator(raw, smart_result=smart)

        assert "rewritten_query" not in pack.query_context.extra

    def test_smart_result_missing_rewritten_query_key(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_orchestrator

        raw = _synthetic_search_result()
        smart = {"agent_unavailable": True}
        pack = extract_evidence_from_orchestrator(raw, smart_result=smart)

        assert "rewritten_query" not in pack.query_context.extra

    def test_raises_on_missing_required_keys(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_orchestrator

        with pytest.raises(ValueError, match="query_params"):
            extract_evidence_from_orchestrator({"success": True})

    def test_smart_result_original_query_overrides_comparison(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_orchestrator

        raw = _synthetic_search_result()
        # raw.query_params.query == "family day out"
        # Simulate orchestrator flow: rewritten == query_params.query, but
        # original_query differs
        smart = {
            "rewritten_query": "family day out",
            "original_query": "what did we do as a family",
        }
        pack = extract_evidence_from_orchestrator(raw, smart_result=smart)

        # rewritten_query equals query_context.query, but differs from original_query
        # → overlay should still trigger
        assert pack.query_context.extra.get("rewritten_query") == "family day out"

    def test_smart_result_original_query_same_no_overlay(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_orchestrator

        raw = _synthetic_search_result()
        smart = {
            "rewritten_query": "family day out",
            "original_query": "family day out",
        }
        pack = extract_evidence_from_orchestrator(raw, smart_result=smart)

        assert "rewritten_query" not in pack.query_context.extra


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestAdapterEdgeCases:
    """Edge cases for both adapter functions."""

    def test_semantic_disabled(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_search_result

        result = _synthetic_search_result()
        result["semantic_results"] = []
        result["semantic_effective_policy"] = "off"

        pack = extract_evidence_from_search_result(result)
        assert len(pack.semantic_candidates) == 0
        assert pack.query_context.semantic_policy == "off"

    def test_empty_no_confident_match(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_search_result

        result = {
            "query_params": {"query": "nonexistent"},
            "merged_results": [],
            "total_available": 0,
            "has_more": False,
            "no_confident_match": True,
        }
        pack = extract_evidence_from_search_result(result)

        assert len(pack.items) == 0
        assert len(pack.semantic_candidates) == 0
        assert pack.no_confident_match is True
        assert pack.total_available == 0

    def test_missing_optional_fields(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_search_result

        result = {
            "query_params": {"query": "minimal"},
            "merged_results": [
                {
                    "path": "Journals/2026/01/life-index_2026-01-01_001.md",
                    "title": "Minimal",
                    "date": "2026-01-01",
                    # No snippet, source, metadata, abstract, etc.
                },
            ],
            "total_available": 1,
            "has_more": False,
            "no_confident_match": False,
        }
        pack = extract_evidence_from_search_result(result)

        assert len(pack.items) == 1
        assert pack.items[0].snippet == ""
        assert pack.items[0].scores.source == "none"
        assert pack.items[0].abstract is None

    def test_duplicate_semantic_exclusion(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_search_result

        result = _synthetic_search_result()
        # Add a semantic result that duplicates the merged item
        dup = {
            "path": "Journals/2026/03/life-index_2026-03-07_001.md",
            "title": "Family Day",
            "date": "2026-03-07",
            "snippet": "duplicate",
            "similarity": 0.55,
            "source": "semantic",
        }
        result["semantic_results"].append(dup)

        pack = extract_evidence_from_search_result(result)

        semantic_ids = {sc.document.doc_id for sc in pack.semantic_candidates}
        item_ids = {item.document.doc_id for item in pack.items}
        assert semantic_ids.isdisjoint(item_ids)

    def test_input_immutability_search_result(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_search_result

        result = _synthetic_search_result()
        original = copy.deepcopy(result)
        extract_evidence_from_search_result(result)
        assert result == original

    def test_input_immutability_orchestrator(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_orchestrator

        raw = _synthetic_search_result()
        smart = {"rewritten_query": "new query"}
        raw_copy = copy.deepcopy(raw)
        smart_copy = copy.deepcopy(smart)

        extract_evidence_from_orchestrator(raw, smart_result=smart)

        assert raw == raw_copy
        assert smart == smart_copy

    def test_round_trip_through_adapter(self) -> None:
        from tools.evidence.adapter import extract_evidence_from_search_result

        result = _synthetic_search_result()
        pack = extract_evidence_from_search_result(result)
        d = pack.to_dict()
        pack2 = EvidencePack.from_dict(d)
        assert pack2 == pack
