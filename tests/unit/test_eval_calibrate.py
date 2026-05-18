#!/usr/bin/env python3
"""Unit tests for tools.eval.calibrate - M05 internal calibration helper.

TDD RED phase: these tests define the contract for gather_calibration()
and related data structures.  They must fail until calibrate.py is
implemented (GREEN phase).

Covers:
  - Layer 0: keyword/default metrics copied from EvalRun.results.metrics
  - Layer 1: entity/query expansion diagnostics from RunResult.extra
  - Layer 2: semantic report summary when present
  - Layer 4: companion-route summaries from EvalRun.extra
  - Layer 5: policy comparison with a supplied candidate EvalRun
  - Data minimization: serialized report excludes query text, titles,
    doc IDs, absolute paths, or raw result titles
"""

from __future__ import annotations

from typing import Any

import pytest

from tools.eval.eval_types import (
    EvalRun,
    EvalRunConfig,
    EvalRunMetadata,
    EvalRunResults,
    RunResult,
    SemanticReport,
)

# ---------------------------------------------------------------------------
# Helpers to build test EvalRun objects
# ---------------------------------------------------------------------------


def _make_config(**overrides: Any) -> EvalRunConfig:
    defaults = dict(
        judge_mode="keyword",
        semantic_enabled=False,
        live_mode=False,
        overlay_enabled=False,
    )
    defaults.update(overrides)
    return EvalRunConfig(**defaults)


def _make_metadata(**overrides: Any) -> EvalRunMetadata:
    defaults = dict(
        timestamp="2026-05-18T12:00:00",
        frozen_at="2026-05-18",
        anchor_date="2026-05-18",
        commit="abc1234",
        python_version="3.12.0",
        tokenizer_version=2,
    )
    defaults.update(overrides)
    return EvalRunMetadata(**defaults)


def _make_run_result(**overrides: Any) -> RunResult:
    defaults = dict(
        query_id="Q001",
        query="SYNTHETIC_QUERY_TEXT",
        category="family",
        results_found=2,
        top_titles=["SYNTHETIC_TITLE_A", "SYNTHETIC_TITLE_B"],
        first_relevant_rank=1,
        first_relevant_rank_at_10=1,
        reciprocal_rank=1.0,
        precision_at_5=0.4,
        ndcg_at_5=1.0,
        expected_min_results=1,
        passed=True,
        eval_mode="exact_mrr",
    )
    defaults.update(overrides)
    return RunResult(**defaults)


def _make_eval_run(
    *,
    per_query: list[RunResult] | None = None,
    metrics: dict[str, float] | None = None,
    semantic_report: SemanticReport | None = None,
    extra: dict[str, Any] | None = None,
    config: EvalRunConfig | None = None,
    metadata: EvalRunMetadata | None = None,
) -> EvalRun:
    if per_query is None:
        per_query = [_make_run_result()]
    if metrics is None:
        metrics = {"mrr_at_5": 0.27, "recall_at_5": 0.38, "precision_at_5": 0.30}
    if config is None:
        config = _make_config()
    if metadata is None:
        metadata = _make_metadata()
    return EvalRun(
        config=config,
        metadata=metadata,
        results=EvalRunResults(
            total_queries=len(per_query),
            skipped_queries=0,
            metrics=metrics,
            by_category={},
            per_query=per_query,
            failures=[],
            semantic_report=semantic_report,
        ),
        extra=extra or {},
    )


# ---------------------------------------------------------------------------
# Layer 0: keyword/default metrics
# ---------------------------------------------------------------------------


class TestLayer0KeywordMetrics:
    """Layer 0 must copy keyword/default metrics from EvalRun.results.metrics."""

    def test_layer0_copies_eval_metrics(self) -> None:
        from tools.eval.calibrate import gather_calibration

        eval_run = _make_eval_run(
            metrics={
                "mrr_at_5": 0.2716,
                "recall_at_5": 0.3836,
                "precision_at_5": 0.30,
                "ndcg_at_5": 0.45,
            }
        )
        report = gather_calibration(eval_run)

        layer0 = report.layers["keyword_default"]
        assert layer0.present is True
        assert layer0.metrics["mrr_at_5"] == 0.2716
        assert layer0.metrics["recall_at_5"] == 0.3836
        assert layer0.metrics["precision_at_5"] == 0.30
        assert layer0.metrics["ndcg_at_5"] == 0.45

    def test_layer0_present_even_with_empty_metrics(self) -> None:
        from tools.eval.calibrate import gather_calibration

        eval_run = _make_eval_run(metrics={})
        report = gather_calibration(eval_run)

        layer0 = report.layers["keyword_default"]
        assert layer0.present is True
        assert layer0.metrics == {}


# ---------------------------------------------------------------------------
# Layer 1: entity/query expansion diagnostics
# ---------------------------------------------------------------------------


class TestLayer1EntityExpansion:
    """Layer 1 must report entity/query expansion diagnostics from
    RunResult.extra without requiring search pipeline changes."""

    def test_layer1_detects_entity_expansion(self) -> None:
        from tools.eval.calibrate import gather_calibration

        per_query = [
            _make_run_result(
                query_id="Q001",
                extra={
                    "expanded_query": "ENTITY_ALPHA ENTITY_BETA ENTITY_GAMMA",
                    "raw_query": "ENTITY_ALPHA",
                    "entity_hints": ["ENTITY_BETA", "ENTITY_GAMMA"],
                },
            ),
            _make_run_result(
                query_id="Q002",
                extra={},
            ),
            _make_run_result(
                query_id="Q003",
                extra={
                    "expanded_query": "ENTITY_ALPHA ENTITY_DELTA",
                    "raw_query": "ENTITY_ALPHA",
                    "entity_hints": ["ENTITY_DELTA"],
                },
            ),
        ]
        eval_run = _make_eval_run(per_query=per_query)
        report = gather_calibration(eval_run)

        layer1 = report.layers["entity_expansion"]
        assert layer1.present is True
        # 2 out of 3 queries had entity expansion
        assert layer1.metrics["expansion_applied_count"] == 2
        assert layer1.metrics["expansion_rate"] == pytest.approx(2.0 / 3.0)

    def test_layer1_no_expansion_data(self) -> None:
        from tools.eval.calibrate import gather_calibration

        per_query = [
            _make_run_result(query_id="Q001", extra={}),
            _make_run_result(query_id="Q002", extra={}),
        ]
        eval_run = _make_eval_run(per_query=per_query)
        report = gather_calibration(eval_run)

        layer1 = report.layers["entity_expansion"]
        assert layer1.present is True
        assert layer1.metrics["expansion_applied_count"] == 0
        assert layer1.metrics["expansion_rate"] == 0.0

    def test_layer1_nested_query_params_shape(self) -> None:
        """Layer 1 must read expansion from nested query_params shape."""
        from tools.eval.calibrate import gather_calibration

        per_query = [
            _make_run_result(
                query_id="Q001",
                extra={
                    "query_params": {
                        "raw_query": "ENTITY_ALPHA",
                        "expanded_query": "ENTITY_ALPHA ENTITY_BETA",
                    },
                },
            ),
            _make_run_result(
                query_id="Q002",
                extra={
                    "query_params": {
                        "raw_query": "ENTITY_GAMMA",
                        "expanded_query": "ENTITY_GAMMA",
                    },
                },
            ),
        ]
        eval_run = _make_eval_run(per_query=per_query)
        report = gather_calibration(eval_run)

        layer1 = report.layers["entity_expansion"]
        assert layer1.present is True
        assert layer1.metrics["expansion_applied_count"] == 1
        assert layer1.metrics["expansion_rate"] == 0.5

    def test_layer1_nested_search_plan_shape(self) -> None:
        """Layer 1 must read expansion from nested search_plan shape."""
        from tools.eval.calibrate import gather_calibration

        per_query = [
            _make_run_result(
                query_id="Q001",
                extra={
                    "search_plan": {
                        "raw_query": "ENTITY_DELTA",
                        "expanded_query": "ENTITY_DELTA ENTITY_ALPHA ENTITY_BETA",
                    },
                },
            ),
        ]
        eval_run = _make_eval_run(per_query=per_query)
        report = gather_calibration(eval_run)

        layer1 = report.layers["entity_expansion"]
        assert layer1.present is True
        assert layer1.metrics["expansion_applied_count"] == 1
        assert layer1.metrics["expansion_rate"] == 1.0

    def test_layer1_flat_takes_precedence_over_nested(self) -> None:
        """Flat raw_query/expanded_query takes precedence over nested shapes."""
        from tools.eval.calibrate import gather_calibration

        per_query = [
            _make_run_result(
                query_id="Q001",
                extra={
                    "raw_query": "FLAT_QUERY",
                    "expanded_query": "FLAT_QUERY FLAT_EXPANSION",
                    "query_params": {
                        "raw_query": "NESTED_QUERY",
                        "expanded_query": "NESTED_QUERY NESTED_EXPANSION",
                    },
                },
            ),
        ]
        eval_run = _make_eval_run(per_query=per_query)
        report = gather_calibration(eval_run)

        layer1 = report.layers["entity_expansion"]
        assert layer1.metrics["expansion_applied_count"] == 1


# ---------------------------------------------------------------------------
# Layer 2: semantic report summary
# ---------------------------------------------------------------------------


class TestLayer2SemanticReport:
    """Layer 2 must summarize eval_run.results.semantic_report when present."""

    def test_layer2_with_semantic_report(self) -> None:
        from tools.eval.calibrate import gather_calibration

        sr = SemanticReport(
            enabled=True,
            metrics={"mrr_at_5": 0.35, "recall_at_5": 0.50},
            failure_count=2,
            failure_ids=["Q001", "Q002"],
            fixed_by_semantic=["Q003"],
            regressed_by_semantic=[],
            still_failing_both=["Q001"],
            delta={"mrr_at_5": 0.08, "recall_at_5": 0.12},
        )
        eval_run = _make_eval_run(semantic_report=sr)
        report = gather_calibration(eval_run)

        layer2 = report.layers["semantic"]
        assert layer2.present is True
        assert layer2.metrics["mrr_at_5"] == 0.35
        assert layer2.metrics["recall_at_5"] == 0.50
        assert layer2.metrics["fixed_count"] == 1
        assert layer2.metrics["regressed_count"] == 0

    def test_layer2_without_semantic_report(self) -> None:
        from tools.eval.calibrate import gather_calibration

        eval_run = _make_eval_run(semantic_report=None)
        report = gather_calibration(eval_run)

        layer2 = report.layers["semantic"]
        assert layer2.present is False


# ---------------------------------------------------------------------------
# Layer 4: companion-route summaries
# ---------------------------------------------------------------------------


class TestLayer4CompanionRoutes:
    """Layer 4 must surface companion-route sections stored in EvalRun.extra."""

    def test_layer4_with_companion_data(self) -> None:
        from tools.eval.calibrate import gather_calibration

        extra = {
            "aggregate_eval": {
                "total_queries": 4,
                "passed_queries": 4,
                "failed_queries": 0,
            },
            "smart_aggregate_eval": {
                "total_queries": 2,
                "passed_queries": 2,
                "failed_queries": 0,
            },
            "timeline_eval": {
                "total_queries": 3,
                "passed_queries": 3,
                "failed_queries": 0,
            },
        }
        eval_run = _make_eval_run(extra=extra)
        report = gather_calibration(eval_run)

        layer4 = report.layers["companion_routes"]
        assert layer4.present is True
        assert layer4.metrics["aggregate_total"] == 4
        assert layer4.metrics["aggregate_passed"] == 4
        assert layer4.metrics["smart_aggregate_total"] == 2
        assert layer4.metrics["timeline_total"] == 3

    def test_layer4_without_companion_data(self) -> None:
        from tools.eval.calibrate import gather_calibration

        eval_run = _make_eval_run(extra={})
        report = gather_calibration(eval_run)

        layer4 = report.layers["companion_routes"]
        assert layer4.present is False


# ---------------------------------------------------------------------------
# Layer 5: policy comparison
# ---------------------------------------------------------------------------


class TestLayer5PolicyComparison:
    """Layer 5 must compare an explicitly supplied policy eval run using
    existing typed comparison helpers."""

    def test_layer5_with_policy_run(self) -> None:
        from tools.eval.calibrate import gather_calibration

        baseline_run = _make_eval_run(
            per_query=[
                _make_run_result(
                    query_id="Q001",
                    passed=True,
                    reciprocal_rank=1.0,
                ),
                _make_run_result(
                    query_id="Q002",
                    passed=False,
                    reciprocal_rank=0.0,
                ),
            ],
            metadata=_make_metadata(commit="baseline_commit"),
        )
        policy_run = _make_eval_run(
            per_query=[
                _make_run_result(
                    query_id="Q001",
                    passed=True,
                    reciprocal_rank=0.5,
                ),
                _make_run_result(
                    query_id="Q002",
                    passed=True,
                    reciprocal_rank=0.5,
                ),
            ],
            metadata=_make_metadata(commit="policy_commit"),
        )

        report = gather_calibration(baseline_run, policy_eval_run=policy_run)

        layer5 = report.layers["policy_comparison"]
        assert layer5.present is True
        assert layer5.metrics["fixed_count"] == 1
        assert layer5.metrics["regressed_count"] == 0
        assert layer5.metrics["still_failing_count"] == 0
        assert layer5.metrics["still_passing_count"] == 1
        assert layer5.metrics["failure_delta"] == -1

    def test_layer5_without_policy_run(self) -> None:
        from tools.eval.calibrate import gather_calibration

        eval_run = _make_eval_run()
        report = gather_calibration(eval_run)

        layer5 = report.layers["policy_comparison"]
        assert layer5.present is False


# ---------------------------------------------------------------------------
# CalibrationReport structure
# ---------------------------------------------------------------------------


class TestCalibrationReportStructure:
    """CalibrationReport must carry metadata and be serializable."""

    def test_report_has_provenance_fields(self) -> None:
        from tools.eval.calibrate import gather_calibration

        eval_run = _make_eval_run(
            metadata=_make_metadata(
                timestamp="2026-05-18T14:30:00",
                anchor_date="2026-05-18",
                commit="deadbeef",
            )
        )
        report = gather_calibration(eval_run)

        assert report.timestamp == "2026-05-18T14:30:00"
        assert report.anchor_date == "2026-05-18"
        assert report.commit == "deadbeef"

    def test_report_to_dict_round_trip(self) -> None:
        from tools.eval.calibrate import gather_calibration

        eval_run = _make_eval_run()
        report = gather_calibration(eval_run)

        serialized = report.to_dict()
        assert isinstance(serialized, dict)
        assert "layers" in serialized
        assert "timestamp" in serialized
        assert "commit" in serialized

    def test_report_from_dict_round_trip(self) -> None:
        from tools.eval.calibrate import CalibrationReport, gather_calibration

        eval_run = _make_eval_run()
        report = gather_calibration(eval_run)
        serialized = report.to_dict()

        restored = CalibrationReport.from_dict(serialized)
        assert restored.timestamp == report.timestamp
        assert restored.commit == report.commit
        assert set(restored.layers.keys()) == set(report.layers.keys())


# ---------------------------------------------------------------------------
# Data minimization
# ---------------------------------------------------------------------------


class TestDataMinimization:
    """Serialized report must not contain query text, titles, doc IDs,
    absolute paths, or raw result titles."""

    FORBIDDEN_STRINGS = [
        "SYNTHETIC_QUERY_TEXT",  # query text
        "SYNTHETIC_TITLE_A",  # raw result title
        "SYNTHETIC_TITLE_B",  # raw result title
        "SYNTHETIC_TITLE_C",  # synthetic title variant
        "ENTITY_ALPHA",  # entity name in query
        "ENTITY_BETA",  # entity alias
        "C:\\",  # absolute path prefix (Windows)
        "/home/",  # absolute path prefix (Linux)
        "synthetic_doc_001.md",  # doc ID / filename
    ]

    def test_no_query_text_or_titles_in_serialized_report(self) -> None:
        from tools.eval.calibrate import gather_calibration

        per_query = [
            _make_run_result(
                query_id="Q001",
                query="SYNTHETIC_QUERY_TEXT ENTITY_ALPHA",
                top_titles=["SYNTHETIC_TITLE_A", "SYNTHETIC_TITLE_C"],
                extra={
                    "expanded_query": "ENTITY_ALPHA ENTITY_BETA ENTITY_GAMMA",
                    "raw_query": "ENTITY_ALPHA",
                    "entity_hints": ["ENTITY_BETA", "ENTITY_GAMMA"],
                },
            ),
        ]
        eval_run = _make_eval_run(per_query=per_query)
        report = gather_calibration(eval_run)

        serialized = report.to_dict()
        serialized_str = str(serialized)

        for forbidden in self.FORBIDDEN_STRINGS:
            assert forbidden not in serialized_str, (
                f"Data minimization violation: '{forbidden}' found in " f"serialized report"
            )

    def test_no_doc_ids_in_serialized_report(self) -> None:
        import json

        from tools.eval.calibrate import gather_calibration

        per_query = [
            _make_run_result(
                query_id="Q001",
                top_doc_ids=["synthetic_doc_001.md"],
            ),
        ]
        eval_run = _make_eval_run(per_query=per_query)
        report = gather_calibration(eval_run)

        serialized_str = json.dumps(report.to_dict())

        assert (
            "synthetic_doc_001.md" not in serialized_str
        ), "Data minimization violation: doc ID found in serialized report"

    def test_comprehensive_minimization_excludes_all_sensitive_data(self) -> None:
        """Full minimization proof: supply every sensitive field and verify
        the serialized report contains none of them."""
        import json

        from tools.eval.calibrate import gather_calibration

        per_query = [
            _make_run_result(
                query_id="Q001",
                query="SYNTHETIC_QUERY_TEXT about ENTITY_ALPHA",
                top_titles=["SYNTHETIC_TITLE_A", "SYNTHETIC_TITLE_B"],
                top_doc_ids=[
                    "synthetic_doc_001.md",
                    "C:\\Users\\someone\\Documents\\synthetic_doc_002.md",
                    "/home/user/synthetic_doc_003.md",
                ],
                extra={
                    "expanded_query": "ENTITY_ALPHA ENTITY_BETA ENTITY_GAMMA",
                    "raw_query": "ENTITY_ALPHA",
                    "entity_hints": ["ENTITY_BETA", "ENTITY_GAMMA"],
                },
            ),
        ]
        eval_run = _make_eval_run(per_query=per_query)
        report = gather_calibration(eval_run)
        serialized_str = json.dumps(report.to_dict())

        sensitive_values = [
            "SYNTHETIC_QUERY_TEXT",
            "SYNTHETIC_TITLE_A",
            "SYNTHETIC_TITLE_B",
            "ENTITY_ALPHA",
            "ENTITY_BETA",
            "ENTITY_GAMMA",
            "synthetic_doc_001.md",
            "synthetic_doc_002.md",
            "synthetic_doc_003.md",
            "C:\\Users\\someone",
            "/home/user/",
        ]
        for sensitive in sensitive_values:
            assert sensitive not in serialized_str, (
                f"Data minimization violation: '{sensitive}' " f"leaked into serialized report"
            )
