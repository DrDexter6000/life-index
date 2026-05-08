#!/usr/bin/env python3
"""Tests for eval_compare typed dataclasses (R2-B4b).

Covers:
  - classify_metric_direction: improved/regressed/unchanged, epsilon
  - MetricDelta: construction, round-trip
  - QueryDelta: defaults, round-trip, optional fields
  - EvalComparison: defaults, round-trip
  - RunComparison: defaults, round-trip
  - Safety: no title/query text in serialized output
  - No import of run_eval or search modules
"""

from __future__ import annotations

import importlib

from tools.eval.eval_compare import (
    EvalComparison,
    MetricDelta,
    QueryDelta,
    RunComparison,
    classify_metric_direction,
)

# ---------------------------------------------------------------------------
# classify_metric_direction
# ---------------------------------------------------------------------------


class TestClassifyMetricDirection:
    def test_positive_is_improved(self) -> None:
        assert classify_metric_direction(0.5) == "improved"

    def test_negative_is_regressed(self) -> None:
        assert classify_metric_direction(-0.3) == "regressed"

    def test_zero_is_unchanged(self) -> None:
        assert classify_metric_direction(0.0) == "unchanged"

    def test_within_epsilon_is_unchanged(self) -> None:
        assert classify_metric_direction(1e-13) == "unchanged"
        assert classify_metric_direction(-1e-13) == "unchanged"

    def test_at_epsilon_boundary(self) -> None:
        assert classify_metric_direction(1e-12) == "unchanged"
        assert classify_metric_direction(1e-11) == "improved"

    def test_custom_epsilon(self) -> None:
        assert classify_metric_direction(0.01, epsilon=0.1) == "unchanged"
        assert classify_metric_direction(0.2, epsilon=0.1) == "improved"


# ---------------------------------------------------------------------------
# MetricDelta
# ---------------------------------------------------------------------------


class TestMetricDelta:
    def test_construction(self) -> None:
        md = MetricDelta("mrr_at_5", 0.3, 0.5, 0.2, "improved")
        assert md.metric_name == "mrr_at_5"
        assert md.baseline_value == 0.3
        assert md.candidate_value == 0.5
        assert md.delta == 0.2
        assert md.direction == "improved"

    def test_round_trip(self) -> None:
        md = MetricDelta("recall_at_5", 0.0, 1.0, 1.0, "improved")
        d = md.to_dict()
        md2 = MetricDelta.from_dict(d)
        assert md2 == md

    def test_round_trip_preserves_direction(self) -> None:
        for direction in ("improved", "regressed", "unchanged"):
            md = MetricDelta("x", 0.0, 0.0, 0.0, direction)
            assert MetricDelta.from_dict(md.to_dict()).direction == direction

    def test_frozen(self) -> None:
        md = MetricDelta("x", 0.0, 0.0, 0.0, "unchanged")
        try:
            md.metric_name = "y"  # type: ignore[misc]
            assert False, "should raise"
        except AttributeError:
            pass


# ---------------------------------------------------------------------------
# QueryDelta
# ---------------------------------------------------------------------------


class TestQueryDelta:
    def test_default_metric_deltas_independent(self) -> None:
        q1 = QueryDelta(query_id="Q1", status="fixed")
        q2 = QueryDelta(query_id="Q2", status="regressed")
        q1.metric_deltas.append(MetricDelta("x", 0.0, 0.0, 0.0, "unchanged"))
        assert len(q2.metric_deltas) == 0

    def test_round_trip_minimal(self) -> None:
        qd = QueryDelta(query_id="Q1", status="still_passing")
        d = qd.to_dict()
        qd2 = QueryDelta.from_dict(d)
        assert qd2.query_id == "Q1"
        assert qd2.status == "still_passing"
        assert qd2.baseline_score is None
        assert qd2.candidate_score is None
        assert qd2.delta is None
        assert qd2.metric_deltas == []

    def test_round_trip_full(self) -> None:
        qd = QueryDelta(
            query_id="Q3",
            status="fixed",
            baseline_score=0.0,
            candidate_score=1.0,
            delta=1.0,
            metric_deltas=[
                MetricDelta("mrr_at_5", 0.0, 1.0, 1.0, "improved"),
            ],
        )
        d = qd.to_dict()
        qd2 = QueryDelta.from_dict(d)
        assert qd2 == qd

    def test_all_statuses(self) -> None:
        for status in (
            "fixed",
            "regressed",
            "still_failing",
            "still_passing",
            "new_in_candidate",
            "missing_from_candidate",
            "skipped_no_qrel",
        ):
            qd = QueryDelta(query_id="Q", status=status)
            d = qd.to_dict()
            assert QueryDelta.from_dict(d).status == status

    def test_none_scores_omitted_from_dict(self) -> None:
        qd = QueryDelta(query_id="Q1", status="still_passing")
        d = qd.to_dict()
        assert "baseline_score" not in d
        assert "candidate_score" not in d
        assert "delta" not in d
        assert "metric_deltas" not in d


# ---------------------------------------------------------------------------
# EvalComparison
# ---------------------------------------------------------------------------


class TestEvalComparison:
    def test_default_lists_independent(self) -> None:
        e1 = EvalComparison(
            baseline_commit="a",
            candidate_commit="b",
            baseline_anchor="2026-01-01",
            candidate_anchor="2026-01-02",
            total_shared_queries=10,
        )
        e2 = EvalComparison(
            baseline_commit="c",
            candidate_commit="d",
            baseline_anchor="2026-01-01",
            candidate_anchor="2026-01-02",
            total_shared_queries=5,
        )
        e1.fixed_query_ids.append("Q1")
        assert len(e2.fixed_query_ids) == 0

    def test_round_trip(self) -> None:
        ec = EvalComparison(
            baseline_commit="abc1234",
            candidate_commit="def5678",
            baseline_anchor="2026-05-01",
            candidate_anchor="2026-05-08",
            total_shared_queries=78,
            fixed_query_ids=["Q1", "Q2"],
            regressed_query_ids=["Q3"],
            failure_delta=-1,
        )
        d = ec.to_dict()
        ec2 = EvalComparison.from_dict(d)
        assert ec2 == ec

    def test_failure_delta_preserved(self) -> None:
        ec = EvalComparison(
            baseline_commit="a",
            candidate_commit="b",
            baseline_anchor="x",
            candidate_anchor="y",
            total_shared_queries=5,
            failure_delta=-3,
        )
        assert EvalComparison.from_dict(ec.to_dict()).failure_delta == -3

    def test_to_dict_copies_lists(self) -> None:
        ec = EvalComparison(
            baseline_commit="a",
            candidate_commit="b",
            baseline_anchor="x",
            candidate_anchor="y",
            total_shared_queries=5,
            fixed_query_ids=["Q1"],
        )
        d = ec.to_dict()
        d["fixed_query_ids"].append("Q99")
        assert ec.fixed_query_ids == ["Q1"]


# ---------------------------------------------------------------------------
# RunComparison
# ---------------------------------------------------------------------------


class TestRunComparison:
    def test_default_lists_independent(self) -> None:
        r1 = RunComparison()
        r2 = RunComparison()
        r1.metric_deltas.append(MetricDelta("x", 0.0, 0.0, 0.0, "unchanged"))
        assert len(r2.metric_deltas) == 0

    def test_round_trip_empty(self) -> None:
        rc = RunComparison()
        d = rc.to_dict()
        rc2 = RunComparison.from_dict(d)
        assert rc2 == rc

    def test_round_trip_full(self) -> None:
        rc = RunComparison(
            metric_deltas=[
                MetricDelta("mrr_at_5", 0.3, 0.5, 0.2, "improved"),
            ],
            per_query_deltas=[
                QueryDelta(query_id="Q1", status="fixed", delta=0.2),
            ],
            queries_compared=78,
            queries_skipped_no_qrel=5,
        )
        d = rc.to_dict()
        rc2 = RunComparison.from_dict(d)
        assert rc2 == rc

    def test_counts_preserved(self) -> None:
        rc = RunComparison(queries_compared=100, queries_skipped_no_qrel=10)
        d = rc.to_dict()
        assert d["queries_compared"] == 100
        assert d["queries_skipped_no_qrel"] == 10


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


class TestSafety:
    def test_no_title_in_serialized_output(self) -> None:
        md = MetricDelta("x", 0.0, 0.0, 0.0, "unchanged")
        qd = QueryDelta(query_id="Q1", status="fixed")
        ec = EvalComparison(
            baseline_commit="a",
            candidate_commit="b",
            baseline_anchor="x",
            candidate_anchor="y",
            total_shared_queries=1,
        )
        rc = RunComparison()
        for obj in (md, qd, ec, rc):
            d = obj.to_dict()
            serialized = str(d)
            assert "Secret Title" not in serialized
            assert "query text" not in serialized

    def test_no_query_text_field_in_dataclasses(self) -> None:
        qd = QueryDelta(query_id="Q1", status="fixed")
        assert not hasattr(qd, "query_text")
        assert not hasattr(qd, "title")
        ec = EvalComparison(
            baseline_commit="a",
            candidate_commit="b",
            baseline_anchor="x",
            candidate_anchor="y",
            total_shared_queries=1,
        )
        assert not hasattr(ec, "query_text")
        assert not hasattr(ec, "title")

    def test_module_does_not_import_run_eval(self) -> None:
        mod = importlib.import_module("tools.eval.eval_compare")
        source = open(mod.__file__, encoding="utf-8").read()
        import_lines = [
            line
            for line in source.splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        joined = "\n".join(import_lines)
        assert "run_eval" not in joined
        assert "search_journals" not in joined
