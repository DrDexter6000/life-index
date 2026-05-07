#!/usr/bin/env python3
"""Tests for eval data model typed primitives and round-trip serialization (R2-B1).

Covers 5 fixture types:
  1. Baseline JSON round-trip (round-19-phase1d-baseline-v4.json)
  2. Synthetic semantic_report result
  3. Broad_eval per_query entry
  4. LLM-scores per_query entry
  5. Unknown future field preservation
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from tools.eval.eval_serialization import (
    assert_semantic_equal,
    canonicalize,
    load_eval_run,
    save_eval_run,
)
from tools.eval.eval_types import (
    CategoryMetrics,
    EvalRun,
    FailureRecord,
    RunResult,
)

BASELINE_PATH = Path("tests/eval/baselines/round-19-phase1d-baseline-v4.json")


# ---------------------------------------------------------------------------
# Fixture 1: Baseline JSON round-trip
# ---------------------------------------------------------------------------


class TestBaselineRoundTrip:
    """Round-trip the real baseline through EvalRun.from_dict / to_dict."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        with open(BASELINE_PATH, encoding="utf-8") as f:
            self.original: dict = json.load(f)
        self.roundtripped: dict = EvalRun.from_dict(self.original).to_dict()

    def test_semantic_equality(self) -> None:
        assert_semantic_equal(self.original, self.roundtripped)

    def test_config_fields(self) -> None:
        run = EvalRun.from_dict(self.original)
        cfg = run.config
        assert cfg.judge_mode == "keyword"
        assert cfg.semantic_enabled is False
        assert cfg.live_mode is True
        assert cfg.overlay_enabled is False

    def test_metadata_fields(self) -> None:
        run = EvalRun.from_dict(self.original)
        meta = run.metadata
        assert meta.run_id == "round-19-phase1d-baseline-v4"
        assert meta.commit == "32fad4b"
        assert meta.anchor_date == "2026-05-04"
        assert meta.python_version == "3.12.10"
        assert meta.tokenizer_version == 2
        assert meta.frozen_by == "main reviewer (Opus 4.7) under Mode A subtask M-1"

    def test_results_counts(self) -> None:
        run = EvalRun.from_dict(self.original)
        r = run.results
        assert r.total_queries == 104
        assert r.skipped_queries == 29
        assert len(r.per_query) == 104
        assert len(r.failures) == 22

    def test_by_category_roundtrip(self) -> None:
        run = EvalRun.from_dict(self.original)
        cats = run.results.by_category
        assert "entity_expansion" in cats
        assert cats["entity_expansion"].query_count == 20
        assert abs(cats["entity_expansion"].mrr_at_5 - 0.8167) < 1e-6

    def test_metrics_roundtrip(self) -> None:
        run = EvalRun.from_dict(self.original)
        m = run.results.metrics
        assert abs(m["mrr_at_5"] - 0.5559) < 1e-6

    def test_failure_roundtrip(self) -> None:
        run = EvalRun.from_dict(self.original)
        failures = run.results.failures
        assert len(failures) == 22
        f0 = failures[0]
        assert f0.query_id == "GQ09"
        assert f0.reason == "Expected >= 1 results, got 0"

    def test_baseline_meta_preserved(self) -> None:
        run = EvalRun.from_dict(self.original)
        assert run.baseline_meta is not None
        assert run.baseline_meta["source_commit"] == "32fad4b"

    def test_defaults_for_missing_fields(self) -> None:
        run = EvalRun.from_dict(self.original)
        r = run.results
        assert r.overlay_applied_count is None
        assert r.overlay_warnings is None
        assert r.broad_eval_metrics is None
        assert r.semantic_report is None
        assert r.recall_gaps == []
        assert len(r.summary_lines) == 11

    def test_per_query_defaults(self) -> None:
        run = EvalRun.from_dict(self.original)
        pq = run.results.per_query[0]
        assert pq.eval_mode == "exact_mrr"
        assert pq.overlay_applied is None
        assert pq.predicate_precision is None


# ---------------------------------------------------------------------------
# Fixture 2: Synthetic semantic_report result
# ---------------------------------------------------------------------------


class TestSemanticReportRoundTrip:
    """Round-trip a synthetic semantic_report through EvalRun."""

    def _make_data(self) -> dict:
        base = _minimal_eval_dict()
        base["semantic_report"] = {
            "enabled": True,
            "metrics": {
                "mrr_at_5": 0.6294,
                "recall_at_5": 0.8495,
                "failure_count": 8,
            },
            "failure_count": 8,
            "failure_ids": ["GQ51", "GQ57", "GQ61", "GQ65", "GQ69", "GQ82", "GQ68", "GQ09"],
            "fixed_by_semantic": ["GQ51", "GQ57", "GQ61", "GQ65", "GQ69", "GQ82"],
            "regressed_by_semantic": ["GQ99", "GQ80"],
            "still_failing_both": ["GQ68", "GQ09"],
            "delta": {
                "mrr_at_5": 0.0618,
                "recall_at_5": 0.054,
            },
        }
        return base

    def test_semantic_equality(self) -> None:
        original = self._make_data()
        roundtripped = EvalRun.from_dict(original).to_dict()
        assert_semantic_equal(original, roundtripped)

    def test_semantic_report_fields(self) -> None:
        run = EvalRun.from_dict(self._make_data())
        sr = run.results.semantic_report
        assert sr is not None
        assert sr.enabled is True
        assert sr.failure_count == 8
        assert len(sr.fixed_by_semantic) == 6
        assert len(sr.regressed_by_semantic) == 2
        assert abs(sr.metrics["mrr_at_5"] - 0.6294) < 1e-6


# ---------------------------------------------------------------------------
# Fixture 3: Broad_eval per_query entry
# ---------------------------------------------------------------------------


class TestBroadEvalRoundTrip:
    """Round-trip a per_query entry with broad_eval fields."""

    def _make_data(self) -> dict:
        base = _minimal_eval_dict()
        base["per_query"] = [
            {
                "id": "GQ-BROAD-01",
                "query": "test broad eval",
                "category": "broad",
                "results_found": 5,
                "top_titles": ["Title A", "Title B"],
                "first_relevant_rank": 2,
                "first_relevant_rank_at_10": 2,
                "reciprocal_rank": 0.5,
                "precision_at_5": 0.4,
                "ndcg_at_5": 0.45,
                "expected_min_results": 3,
                "pass": True,
                "eval_mode": "broad",
                "overlay_applied": False,
                "predicate_precision": 0.8,
                "global_matched_count": 10,
                "returned_count": 5,
                "matched_count": 4,
                "min_results_ok": True,
                "strict_pass": True,
                "soft_pass": True,
                "broad_eval_error": None,
            }
        ]
        return base

    def test_semantic_equality(self) -> None:
        original = self._make_data()
        roundtripped = EvalRun.from_dict(original).to_dict()
        assert_semantic_equal(original, roundtripped)

    def test_broad_eval_fields(self) -> None:
        run = EvalRun.from_dict(self._make_data())
        pq = run.results.per_query[0]
        assert pq.eval_mode == "broad"
        assert pq.predicate_precision == 0.8
        assert pq.global_matched_count == 10
        assert pq.returned_count == 5
        assert pq.matched_count == 4
        assert pq.min_results_ok is True
        assert pq.strict_pass is True
        assert pq.soft_pass is True


# ---------------------------------------------------------------------------
# Fixture 4: LLM-scores per_query entry
# ---------------------------------------------------------------------------


class TestLlmScoresRoundTrip:
    """Round-trip a per_query entry with llm_scores."""

    def _make_data(self) -> dict:
        base = _minimal_eval_dict()
        base["per_query"] = [
            {
                "id": "GQ-LLM-01",
                "query": "test llm scores",
                "category": "complex_query",
                "results_found": 3,
                "top_titles": ["X", "Y", "Z"],
                "first_relevant_rank": 1,
                "first_relevant_rank_at_10": 1,
                "reciprocal_rank": 1.0,
                "precision_at_5": 0.6,
                "ndcg_at_5": 0.85,
                "expected_min_results": 1,
                "pass": True,
                "eval_mode": "llm",
                "overlay_applied": False,
                "llm_scores": [5, 4, 3],
            }
        ]
        return base

    def test_semantic_equality(self) -> None:
        original = self._make_data()
        roundtripped = EvalRun.from_dict(original).to_dict()
        assert_semantic_equal(original, roundtripped)

    def test_llm_scores_field(self) -> None:
        run = EvalRun.from_dict(self._make_data())
        pq = run.results.per_query[0]
        assert pq.llm_scores == [5, 4, 3]
        assert pq.eval_mode == "llm"


# ---------------------------------------------------------------------------
# Fixture 5: Unknown future field preservation
# ---------------------------------------------------------------------------


class TestUnknownFieldPreservation:
    """Unknown top-level and per_query fields must survive round-trip."""

    def test_top_level_unknown_field(self) -> None:
        original = _minimal_eval_dict()
        original["future_new_top_level_field"] = {"nested": True, "value": 42}
        original["another_future_field"] = [1, 2, 3]
        roundtripped = EvalRun.from_dict(original).to_dict()
        assert_semantic_equal(original, roundtripped)

    def test_per_query_unknown_field(self) -> None:
        original = _minimal_eval_dict()
        original["per_query"] = [
            {
                "id": "GQ-FUTURE",
                "query": "test",
                "category": "test",
                "results_found": 1,
                "top_titles": ["T"],
                "first_relevant_rank": 1,
                "first_relevant_rank_at_10": 1,
                "reciprocal_rank": 1.0,
                "precision_at_5": 1.0,
                "ndcg_at_5": 1.0,
                "expected_min_results": 1,
                "pass": True,
                "future_score_component": 0.99,
                "future_reranker_signal": {"type": "neural", "weight": 0.3},
            }
        ]
        roundtripped = EvalRun.from_dict(original).to_dict()
        assert_semantic_equal(original, roundtripped)

    def test_category_unknown_field(self) -> None:
        original = _minimal_eval_dict()
        original["by_category"]["test_cat"] = {
            "mrr_at_5": 0.5,
            "recall_at_5": 0.6,
            "recall_at_10": 0.7,
            "precision_at_5": 0.4,
            "ndcg_at_5": 0.5,
            "query_count": 5,
            "future_metric": 0.88,
        }
        roundtripped = EvalRun.from_dict(original).to_dict()
        assert_semantic_equal(original, roundtripped)

    def test_failure_unknown_field(self) -> None:
        original = _minimal_eval_dict()
        original["failures"] = [
            {
                "id": "GQ-FAIL",
                "query": "test fail",
                "reason": "no results",
                "diagnosis_code": "ZERO_RESULTS",
            }
        ]
        roundtripped = EvalRun.from_dict(original).to_dict()
        assert_semantic_equal(original, roundtripped)


# ---------------------------------------------------------------------------
# File I/O round-trip via eval_serialization
# ---------------------------------------------------------------------------


class TestFileIORoundTrip:
    """Test load_eval_run / save_eval_run with a temp file."""

    def test_save_load_roundtrip(self) -> None:
        original = _minimal_eval_dict()
        original["per_query"] = [
            {
                "id": "GQ-IO",
                "query": "io test",
                "category": "test",
                "results_found": 2,
                "top_titles": ["A", "B"],
                "first_relevant_rank": 1,
                "first_relevant_rank_at_10": 1,
                "reciprocal_rank": 1.0,
                "precision_at_5": 1.0,
                "ndcg_at_5": 1.0,
                "expected_min_results": 1,
                "pass": True,
            }
        ]
        fd, tmp = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            run = EvalRun.from_dict(original)
            save_eval_run(run, tmp)
            loaded = load_eval_run(tmp)
            assert_semantic_equal(original, loaded.to_dict())
        finally:
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Unit tests for individual types
# ---------------------------------------------------------------------------


class TestRunResultOptionalFields:
    """RunResult should omit eval_mode and optional None fields in to_dict."""

    def test_eval_mode_exact_mrr_omitted(self) -> None:
        rr = RunResult(
            query_id="T1",
            query="test",
            category="test",
            results_found=1,
            top_titles=["X"],
            first_relevant_rank=1,
            first_relevant_rank_at_10=1,
            reciprocal_rank=1.0,
            precision_at_5=1.0,
            ndcg_at_5=1.0,
            expected_min_results=1,
            passed=True,
            eval_mode="exact_mrr",
            overlay_applied=False,
        )
        d = rr.to_dict()
        assert "eval_mode" not in d
        assert "predicate_precision" not in d

    def test_eval_mode_broad_included(self) -> None:
        rr = RunResult(
            query_id="T2",
            query="test",
            category="test",
            results_found=1,
            top_titles=["X"],
            first_relevant_rank=1,
            first_relevant_rank_at_10=1,
            reciprocal_rank=1.0,
            precision_at_5=1.0,
            ndcg_at_5=1.0,
            expected_min_results=1,
            passed=True,
            eval_mode="broad",
            overlay_applied=False,
        )
        d = rr.to_dict()
        assert d["eval_mode"] == "broad"

    def test_public_query_preserved(self) -> None:
        rr = RunResult(
            query_id="T3",
            query="test",
            category="test",
            results_found=1,
            top_titles=["X"],
            first_relevant_rank=1,
            first_relevant_rank_at_10=1,
            reciprocal_rank=1.0,
            precision_at_5=1.0,
            ndcg_at_5=1.0,
            expected_min_results=1,
            passed=True,
            eval_mode="exact_mrr",
            overlay_applied=True,
            public_query="real name query",
        )
        d = rr.to_dict()
        assert d["public_query"] == "real name query"
        assert d["overlay_applied"] is True


class TestNdcgNullPreservation:
    """Regression: ndcg_at_5: null must survive round-trip (P1 review fix)."""

    def test_ndcg_null_roundtrip(self) -> None:
        original = _minimal_eval_dict()
        original["per_query"] = [
            {
                "id": "GQ-NDCG-NULL",
                "query": "test ndcg null",
                "category": "edge_case",
                "results_found": 0,
                "top_titles": [],
                "first_relevant_rank": None,
                "first_relevant_rank_at_10": None,
                "reciprocal_rank": 0.0,
                "precision_at_5": 0.0,
                "ndcg_at_5": None,
                "expected_min_results": 1,
                "pass": False,
            }
        ]
        roundtripped = EvalRun.from_dict(original).to_dict()
        assert_semantic_equal(original, roundtripped)
        assert "ndcg_at_5" in roundtripped["per_query"][0]
        assert roundtripped["per_query"][0]["ndcg_at_5"] is None

    def test_ndcg_absent_stays_absent(self) -> None:
        """Old baselines that lack ndcg_at_5 should not gain it."""
        pq = {
            "id": "GQ-NO-NDCG",
            "query": "test",
            "category": "test",
            "results_found": 1,
            "top_titles": ["X"],
            "first_relevant_rank": 1,
            "first_relevant_rank_at_10": 1,
            "reciprocal_rank": 1.0,
            "precision_at_5": 1.0,
            "expected_min_results": 1,
            "pass": True,
        }
        rr = RunResult.from_dict(pq)
        d = rr.to_dict()
        assert "ndcg_at_5" not in d


class TestCategoryMetricsRoundTrip:
    """CategoryMetrics preserves known and unknown fields."""

    def test_known_fields_only(self) -> None:
        data = {
            "mrr_at_5": 0.5,
            "recall_at_5": 0.6,
            "recall_at_10": 0.7,
            "precision_at_5": 0.4,
            "ndcg_at_5": 0.5,
            "query_count": 10,
        }
        cm = CategoryMetrics.from_dict(data)
        assert_semantic_equal(cm.to_dict(), data)

    def test_with_extra(self) -> None:
        data = {
            "mrr_at_5": 0.5,
            "recall_at_5": 0.6,
            "recall_at_10": 0.7,
            "precision_at_5": 0.4,
            "ndcg_at_5": 0.5,
            "query_count": 10,
            "future_agg_metric": 0.99,
        }
        cm = CategoryMetrics.from_dict(data)
        assert_semantic_equal(cm.to_dict(), data)


class TestFailureRecordRoundTrip:
    def test_basic(self) -> None:
        data = {"id": "F1", "query": "q", "reason": "fail"}
        fr = FailureRecord.from_dict(data)
        assert_semantic_equal(fr.to_dict(), data)


class TestCanonicalize:
    def test_ordering(self) -> None:
        a = {"z": 1, "a": 2}
        b = {"a": 2, "z": 1}
        assert canonicalize(a) == canonicalize(b)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_eval_dict() -> dict:
    """Return a minimal valid eval dict for testing."""
    return {
        "baseline_id": "test-baseline",
        "meta": {"source_commit": "abc123"},
        "timestamp": "2026-05-07T00:00:00+00:00",
        "frozen_at": "2026-05-07",
        "anchor_date": "2026-05-07",
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
