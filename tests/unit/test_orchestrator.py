"""Deterministic smart-search orchestrator unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from tools.search_journals.orchestrator import SmartSearchOrchestrator


def _search_result(count: int = 2) -> dict[str, Any]:
    items = [
        {
            "path": f"Journals/2026/03/life-index_2026-03-0{index}_001.md",
            "rel_path": f"Journals/2026/03/life-index_2026-03-0{index}_001.md",
            "title": f"Test Entry {index}",
            "date": f"2026-03-0{index}",
            "snippet": f"snippet {index}",
            "source": "fts",
            "relevance": 90 - index * 10,
            "fts_score": float(90 - index * 10),
            "semantic_score": 0.0,
            "rrf_score": float(90 - index * 10),
            "final_score": float(90 - index * 10),
            "search_rank": index,
            "confidence": "high" if index == 1 else "medium",
            "metadata": {
                "topic": "test",
                "location": "Beijing",
                "abstract": f"Abstract for entry {index}.",
            },
        }
        for index in range(1, count + 1)
    ]
    return {
        "success": True,
        "query_params": {"query": "test", "expanded_query": "test expanded"},
        "merged_results": items,
        "semantic_results": [],
        "total_available": count,
        "has_more": False,
        "no_confident_match": count == 0,
        "performance": {"total_time_ms": 42.0},
    }


def _domain_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "performance"}


def test_orchestrator_exposes_only_deterministic_pipeline_boundary() -> None:
    orch = SmartSearchOrchestrator()
    assert hasattr(orch, "rewrite_query")
    assert hasattr(orch, "execute_search")
    assert hasattr(orch, "search")
    assert not hasattr(orch, "post_filter_and_summarize")
    assert not hasattr(orch, "synthesize_answer")


def test_data_minimization_limit_is_preserved() -> None:
    from tools.lib.search_constants import ORCHESTRATOR_MAX_CANDIDATES

    assert ORCHESTRATOR_MAX_CANDIDATES == 15


def test_search_returns_agent_ready_deterministic_schema() -> None:
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kwargs: _search_result(1),
    ):
        result = SmartSearchOrchestrator().search("晴岚")

    assert result["agent_unavailable"] is True
    assert result["smart_search_mode"] == "deterministic_scaffold"
    assert result["summary"] == ""
    assert result["citations"] == []
    assert result["agent_decisions"] == []
    assert result["agent_instructions"]["role"] == "calling_agent"
    assert result["answer_scaffold"]["citation_policy"] == "cite_only_returned_results"


def test_search_bounds_candidates_without_changing_order() -> None:
    raw = _search_result(20)
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kwargs: raw,
    ):
        result = SmartSearchOrchestrator().search("test")

    assert len(result["filtered_results"]) == 15
    assert result["filtered_results"] == raw["merged_results"][:15]
    assert result["performance"]["total_available"] == 20


def test_execute_search_fuses_bounded_deterministic_subqueries() -> None:
    calls: list[str] = []

    def search(query: str = "", **kwargs: Any) -> dict[str, Any]:
        calls.append(query)
        result = _search_result(1)
        result["merged_results"][0]["path"] = f"Journals/{query}.md"
        result["merged_results"][0]["rel_path"] = f"Journals/{query}.md"
        return result

    rewritten: Any = {
        "rewritten_query": "family",
        "sub_queries": ["daughter", "birthday", "school", "ignored"],
        "time_range": None,
    }
    with patch("tools.search_journals.orchestrator._get_search_fn", return_value=search):
        result = SmartSearchOrchestrator().execute_search(rewritten)

    assert calls == ["daughter", "birthday", "school"]
    assert result["strategy"] == "keyword_multi_pass"
    assert len(result["candidates"]) == 3


def test_multi_query_total_available_is_observed_unique_before_cap() -> None:
    all_items = _search_result(17)["merged_results"]

    def search(query: str = "", **kwargs: Any) -> dict[str, Any]:
        result = _search_result(0)
        result["merged_results"] = all_items[:10] if query == "first" else all_items[5:17]
        result["total_available"] = len(result["merged_results"])
        return result

    rewritten: Any = {
        "rewritten_query": "combined",
        "sub_queries": ["first", "second"],
        "time_range": None,
    }
    with patch("tools.search_journals.orchestrator._get_search_fn", return_value=search):
        result = SmartSearchOrchestrator().execute_search(rewritten)

    assert [item["rel_path"] for item in result["candidates"]] == [
        item["rel_path"] for item in all_items[:15]
    ]
    assert result["total_available"] == 17
    assert result["raw_results"]["total_available"] == 17
    assert result["raw_results"]["total_found"] == 15
    assert result["raw_results"]["has_more"] is True


def test_multi_query_child_has_more_marks_observed_total_as_lower_bound() -> None:
    item = _search_result(1)["merged_results"][0]

    def search(query: str = "", **kwargs: Any) -> dict[str, Any]:
        result = _search_result(1)
        result["merged_results"] = [item]
        result["total_available"] = 50 if query == "partial" else 1
        result["has_more"] = query == "partial"
        return result

    rewritten: Any = {
        "rewritten_query": "combined",
        "sub_queries": ["partial", "overlap"],
        "time_range": None,
    }
    with patch("tools.search_journals.orchestrator._get_search_fn", return_value=search):
        result = SmartSearchOrchestrator().execute_search(rewritten)

    assert result["total_available"] == 1
    assert result["raw_results"]["total_available"] == 1
    assert result["raw_results"]["has_more"] is True


def test_multi_query_child_failure_preserves_partial_results_and_incompleteness() -> None:
    success = _search_result(1)
    failure = {
        "success": False,
        "error": {"code": "search_failed", "message": "synthetic failure"},
        "merged_results": [],
        "total_available": 0,
        "has_more": False,
        "performance": {"total_time_ms": 1.0},
    }

    def search(query: str = "", **kwargs: Any) -> dict[str, Any]:
        return failure if query == "broken" else success

    rewritten: Any = {
        "rewritten_query": "combined",
        "sub_queries": ["working", "broken"],
        "time_range": None,
    }
    with patch("tools.search_journals.orchestrator._get_search_fn", return_value=search):
        result = SmartSearchOrchestrator().execute_search(rewritten)

    assert [item["rel_path"] for item in result["candidates"]] == [
        item["rel_path"] for item in success["merged_results"]
    ]
    assert result["total_available"] == 1
    assert result["raw_results"]["has_more"] is True
    assert result["raw_results"]["multi_query_results"][1]["result"] == failure
    assert any("broken" in warning for warning in result["raw_results"]["warnings"])


def test_multi_query_evidence_and_performance_share_observed_unique_lower_bound() -> None:
    all_items = _search_result(17)["merged_results"]

    def search(query: str = "", **kwargs: Any) -> dict[str, Any]:
        result = _search_result(0)
        result["merged_results"] = all_items[:10] if query == "first" else all_items[5:17]
        result["total_available"] = len(result["merged_results"])
        return result

    rewritten: Any = {
        "rewritten_query": "combined",
        "sub_queries": ["first", "second"],
        "time_range": None,
    }
    with (
        patch.object(SmartSearchOrchestrator, "rewrite_query", return_value=rewritten),
        patch("tools.search_journals.orchestrator._get_search_fn", return_value=search),
    ):
        result = SmartSearchOrchestrator().search("combined", include_evidence=True)

    assert len(result["filtered_results"]) == 15
    assert result["performance"]["total_available"] == 17
    assert result["evidence_pack"]["total_available"] == 17
    assert result["evidence_pack"]["has_more"] is True
    assert len(result["evidence_pack"]["items"]) == 15


@pytest.mark.parametrize("incomplete_kind", ["child_has_more", "child_failure"])
def test_multi_query_incomplete_evidence_never_claims_full_recall(
    incomplete_kind: str,
) -> None:
    success = _search_result(1)
    success["merged_results"][0]["confidence"] = "low"
    success["no_confident_match"] = False

    def search(query: str = "", **kwargs: Any) -> dict[str, Any]:
        if query == "first":
            return success
        if incomplete_kind == "child_has_more":
            partial = dict(success)
            partial["total_available"] = 10
            partial["has_more"] = True
            return partial
        return {
            "success": False,
            "error": {"code": "search_failed", "message": "synthetic failure"},
            "merged_results": [],
            "total_available": 0,
            "has_more": False,
            "performance": {"total_time_ms": 1.0},
        }

    rewritten: Any = {
        "rewritten_query": "combined",
        "sub_queries": ["first", "second"],
        "time_range": None,
    }
    with (
        patch.object(SmartSearchOrchestrator, "rewrite_query", return_value=rewritten),
        patch("tools.search_journals.orchestrator._get_search_fn", return_value=search),
    ):
        result = SmartSearchOrchestrator().search("combined", include_evidence=True)

    evidence = result["evidence_pack"]
    assert evidence["total_available"] == len(evidence["items"]) == 1
    assert evidence["has_more"] is True
    diagnostics = evidence["diagnostics"]
    assert diagnostics["outcome_reason"] == "low_confidence_with_potential_under_recall"
    assert all("full recall" not in note.lower() for note in diagnostics["notes"])
    assert any("incomplete" in note.lower() for note in diagnostics["notes"])


def test_multi_query_all_child_failures_report_incomplete_evidence() -> None:
    def search(query: str = "", **kwargs: Any) -> dict[str, Any]:
        return {
            "success": False,
            "error": {
                "code": "search_failed",
                "message": f"synthetic failure for {query}",
            },
            "merged_results": [],
            "total_available": 0,
            "has_more": False,
            "performance": {"total_time_ms": 1.0},
        }

    rewritten: Any = {
        "rewritten_query": "combined",
        "sub_queries": ["first", "second"],
        "time_range": None,
    }
    with (
        patch.object(SmartSearchOrchestrator, "rewrite_query", return_value=rewritten),
        patch("tools.search_journals.orchestrator._get_search_fn", return_value=search),
    ):
        result = SmartSearchOrchestrator().search("combined", include_evidence=True)

    evidence = result["evidence_pack"]
    assert evidence["items"] == []
    assert evidence["total_available"] == 0
    assert evidence["has_more"] is True
    diagnostics = evidence["diagnostics"]
    assert diagnostics["retrieval_outcome"] == "weak_results"
    assert diagnostics["outcome_reason"] == "low_confidence_with_potential_under_recall"
    assert diagnostics["outcome_reason"] != "no_matches_found"
    assert any("incomplete" in note.lower() for note in diagnostics["notes"])
    assert any("observed" in note.lower() for note in diagnostics["notes"])


def test_execute_search_applies_deterministic_time_range() -> None:
    captured: list[dict[str, str]] = []

    def search(query: str = "", **kwargs: Any) -> dict[str, Any]:
        captured.append(kwargs)
        return _search_result(0)

    rewritten: Any = {
        "rewritten_query": "family",
        "sub_queries": ["family"],
        "time_range": "2026-03",
    }
    with patch("tools.search_journals.orchestrator._get_search_fn", return_value=search):
        result = SmartSearchOrchestrator().execute_search(rewritten)

    assert captured == [{"date_from": "2026-03-01", "date_to": "2026-03-31"}]
    assert result["strategy"] == "keyword_temporal"


def test_default_search_has_no_evidence_pack_or_internal_raw_results() -> None:
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kwargs: _search_result(),
    ):
        result = SmartSearchOrchestrator().search("test")

    assert "evidence_pack" not in result
    assert "raw_results" not in result


def test_include_evidence_preserves_raw_candidate_evidence() -> None:
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kwargs: _search_result(5),
    ):
        result = SmartSearchOrchestrator().search("test", include_evidence=True)

    assert len(result["evidence_pack"]["items"]) == 5
    assert result["evidence_pack"]["total_available"] == 5
    assert result["performance"]["evidence_build_ms"] >= 0


def test_include_evidence_empty_results_produces_valid_empty_pack() -> None:
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kwargs: _search_result(0),
    ):
        result = SmartSearchOrchestrator().search("missing", include_evidence=True)

    assert result["evidence_pack"]["items"] == []
    assert result["evidence_pack"]["total_available"] == 0
    assert result["evidence_pack"]["no_confident_match"] is True


def test_evidence_build_failure_is_best_effort() -> None:
    with (
        patch(
            "tools.search_journals.orchestrator._get_search_fn",
            return_value=lambda **kwargs: _search_result(1),
        ),
        patch(
            "tools.evidence.adapter.extract_evidence_from_orchestrator",
            side_effect=RuntimeError("build failed"),
        ),
    ):
        result = SmartSearchOrchestrator().search("test", include_evidence=True)

    assert result["success"] is True
    assert "evidence_pack" not in result
    assert result["performance"]["evidence_error"] == "build failed"


def test_synthesize_compatibility_argument_is_exact_domain_noop() -> None:
    with patch(
        "tools.search_journals.orchestrator._get_search_fn",
        return_value=lambda **kwargs: _search_result(1),
    ):
        ordinary = SmartSearchOrchestrator().search("test")
        compatibility = SmartSearchOrchestrator().search("test", synthesize=True)

    assert _domain_payload(ordinary) == _domain_payload(compatibility)
    assert "answer" not in compatibility
    assert "synthesis_ms" not in compatibility["performance"]


def test_aggregate_delegation_preserves_public_scaffold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", "2026-05-13")
    aggregate = {
        "success": True,
        "command": "aggregate",
        "unit": "day",
        "predicate": {"type": "entry_time_after"},
        "result": {"count": 0},
    }
    with patch("tools.aggregate.core.run_aggregate", return_value=aggregate):
        result = SmartSearchOrchestrator().search("过去60天我有多少天晚睡")

    assert result["aggregate_result"] == aggregate
    assert result["smart_search_mode"] == "deterministic_aggregate"
    assert result["filtered_results"] == []
    assert result["agent_unavailable"] is True
    assert "answer" not in result


def test_aggregate_failure_falls_back_to_deterministic_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", "2026-05-13")
    with (
        patch("tools.aggregate.core.run_aggregate", side_effect=RuntimeError("boom")),
        patch(
            "tools.search_journals.orchestrator._get_search_fn",
            return_value=lambda **kwargs: _search_result(1),
        ),
    ):
        result = SmartSearchOrchestrator().search("过去60天我有多少天晚睡")

    assert "aggregate_result" not in result
    assert result["filtered_results"][0]["title"] == "Test Entry 1"
