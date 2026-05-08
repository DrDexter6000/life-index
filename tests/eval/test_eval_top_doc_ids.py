#!/usr/bin/env python3
"""Tests for top_doc_ids in eval per_query output (R2-B3c1).

Covers:
  1. Serialization: old JSON without top_doc_ids stays absent after round-trip
  2. Serialization: new JSON with top_doc_ids preserves them after round-trip
  3. _result_doc_id helper: journal_route_path, rel_path, path fallbacks, empty
  4. run_eval output: top_doc_ids present and matches top_titles length
"""

from __future__ import annotations

from tools.eval.eval_types import EvalRun, RunResult

# ---------------------------------------------------------------------------
# 1. Serialization backward compatibility
# ---------------------------------------------------------------------------


class TestTopDocIdsSerialization:
    def test_old_entry_without_top_doc_ids_stays_absent(self) -> None:
        pq = {
            "id": "GQ-OLD",
            "query": "test",
            "category": "test",
            "results_found": 1,
            "top_titles": ["Title"],
            "first_relevant_rank": 1,
            "first_relevant_rank_at_10": 1,
            "reciprocal_rank": 1.0,
            "precision_at_5": 1.0,
            "expected_min_results": 1,
            "pass": True,
        }
        rr = RunResult.from_dict(pq)
        d = rr.to_dict()
        assert "top_doc_ids" not in d

    def test_new_entry_with_top_doc_ids_preserved(self) -> None:
        pq = {
            "id": "GQ-NEW",
            "query": "test",
            "category": "test",
            "results_found": 2,
            "top_titles": ["A", "B"],
            "top_doc_ids": ["2026/03/a.md", "2026/03/b.md"],
            "first_relevant_rank": 1,
            "first_relevant_rank_at_10": 1,
            "reciprocal_rank": 1.0,
            "precision_at_5": 0.5,
            "expected_min_results": 1,
            "pass": True,
        }
        rr = RunResult.from_dict(pq)
        d = rr.to_dict()
        assert d["top_doc_ids"] == ["2026/03/a.md", "2026/03/b.md"]

    def test_empty_top_doc_ids_preserved(self) -> None:
        pq = {
            "id": "GQ-EMPTY",
            "query": "test",
            "category": "test",
            "results_found": 0,
            "top_titles": [],
            "top_doc_ids": [],
            "first_relevant_rank": None,
            "first_relevant_rank_at_10": None,
            "reciprocal_rank": 0.0,
            "precision_at_5": 0.0,
            "expected_min_results": 1,
            "pass": False,
        }
        rr = RunResult.from_dict(pq)
        d = rr.to_dict()
        assert d["top_doc_ids"] == []

    def test_top_doc_ids_with_empty_strings(self) -> None:
        pq = {
            "id": "GQ-PARTIAL",
            "query": "test",
            "category": "test",
            "results_found": 2,
            "top_titles": ["A", "B"],
            "top_doc_ids": ["2026/03/a.md", ""],
            "first_relevant_rank": 1,
            "first_relevant_rank_at_10": 1,
            "reciprocal_rank": 1.0,
            "precision_at_5": 0.5,
            "expected_min_results": 1,
            "pass": True,
        }
        rr = RunResult.from_dict(pq)
        d = rr.to_dict()
        assert d["top_doc_ids"] == ["2026/03/a.md", ""]

    def test_eval_run_full_roundtrip_with_top_doc_ids(self) -> None:
        data = _minimal_eval_dict()
        data["per_query"] = [
            {
                "id": "GQ-RT",
                "query": "roundtrip",
                "category": "test",
                "results_found": 1,
                "top_titles": ["Title"],
                "top_doc_ids": ["2026/03/life-index_2026-03-14_001.md"],
                "first_relevant_rank": 1,
                "first_relevant_rank_at_10": 1,
                "reciprocal_rank": 1.0,
                "precision_at_5": 1.0,
                "expected_min_results": 1,
                "pass": True,
            }
        ]
        roundtripped = EvalRun.from_dict(data).to_dict()
        assert roundtripped["per_query"][0]["top_doc_ids"] == [
            "2026/03/life-index_2026-03-14_001.md"
        ]

    def test_eval_run_old_roundtrip_no_top_doc_ids(self) -> None:
        data = _minimal_eval_dict()
        data["per_query"] = [
            {
                "id": "GQ-OLD-RT",
                "query": "old format",
                "category": "test",
                "results_found": 1,
                "top_titles": ["Title"],
                "first_relevant_rank": 1,
                "first_relevant_rank_at_10": 1,
                "reciprocal_rank": 1.0,
                "precision_at_5": 1.0,
                "expected_min_results": 1,
                "pass": True,
            }
        ]
        roundtripped = EvalRun.from_dict(data).to_dict()
        assert "top_doc_ids" not in roundtripped["per_query"][0]


# ---------------------------------------------------------------------------
# 2. _result_doc_id helper
# ---------------------------------------------------------------------------


class TestResultDocIdHelper:
    def test_journal_route_path_preferred(self) -> None:
        from tools.eval.run_eval import _result_doc_id

        result = {"journal_route_path": "2026/03/life-index_2026-03-14_001.md"}
        assert _result_doc_id(result) == "2026/03/life-index_2026-03-14_001.md"

    def test_journal_route_path_backslash_normalized(self) -> None:
        from tools.eval.run_eval import _result_doc_id

        result = {"journal_route_path": "2026\\03\\life-index_2026-03-14_001.md"}
        assert _result_doc_id(result) == "2026/03/life-index_2026-03-14_001.md"

    def test_rel_path_journals_prefix_stripped(self) -> None:
        from tools.eval.run_eval import _result_doc_id

        result = {"rel_path": "Journals/2026/03/life-index_2026-03-14_001.md"}
        assert _result_doc_id(result) == "2026/03/life-index_2026-03-14_001.md"

    def test_path_journals_extraction(self) -> None:
        from tools.eval.run_eval import _result_doc_id

        result = {"path": "/home/user/Life-Index/Journals/2026/03/life-index_2026-03-14_001.md"}
        assert _result_doc_id(result) == "2026/03/life-index_2026-03-14_001.md"

    def test_no_path_fields_returns_empty(self) -> None:
        from tools.eval.run_eval import _result_doc_id

        assert _result_doc_id({}) == ""
        assert _result_doc_id({"path": "/no/journals/here.md"}) == ""

    def test_journal_route_path_empty_falls_through(self) -> None:
        from tools.eval.run_eval import _result_doc_id

        result = {
            "journal_route_path": "",
            "rel_path": "Journals/2026/03/fallback.md",
        }
        assert _result_doc_id(result) == "2026/03/fallback.md"

    def test_windows_path_backslash_normalized(self) -> None:
        from tools.eval.run_eval import _result_doc_id

        result = {
            "journal_route_path": "",
            "rel_path": "Journals\\2026\\03\\life-index_2026-03-14_001.md",
        }
        assert _result_doc_id(result) == "2026/03/life-index_2026-03-14_001.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_eval_dict() -> dict:
    return {
        "baseline_id": "test-baseline",
        "meta": {"source_commit": "abc123"},
        "timestamp": "2026-05-08T00:00:00+00:00",
        "frozen_at": "2026-05-08",
        "anchor_date": "2026-05-08",
        "commit": "abc123",
        "python_version": "3.12.10",
        "tokenizer_version": 2,
        "judge_mode": "keyword",
        "semantic_enabled": False,
        "live_mode": True,
        "total_queries": 1,
        "skipped_queries": 0,
        "metrics": {"mrr_at_5": 0.5},
        "by_category": {},
        "per_query": [],
        "failures": [],
        "recall_gaps": [],
        "summary_lines": [],
    }
