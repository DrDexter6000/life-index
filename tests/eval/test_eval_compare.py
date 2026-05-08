#!/usr/bin/env python3
"""Tests for eval_compare dataclasses and comparison functions (R2-B4c).

Covers:
  - classify_metric_direction: improved/regressed/unchanged, epsilon
  - MetricDelta: construction, round-trip
  - QueryDelta: defaults, round-trip, optional fields
  - EvalComparison: defaults, round-trip
  - RunComparison: defaults, round-trip
  - compare_eval_runs: identical, fixed, regressed, still, new, missing, failure_delta
  - classify_eval_query_deltas: scores, sorting, status classification
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
    _mrr_at_k,
    _ranked_doc_ids,
    _recall_at_k,
    classify_eval_query_deltas,
    classify_metric_direction,
    classify_query_deltas,
    compare_eval_runs,
    compare_runs,
    export_comparison_report,
)
from tools.eval.eval_types import (
    EvalRun,
    EvalRunConfig,
    EvalRunMetadata,
    EvalRunResults,
    RunResult,
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
        assert "eval_qrels" not in joined
        assert "ranx" not in joined


# ---------------------------------------------------------------------------
# Helpers for constructing minimal EvalRun fixtures
# ---------------------------------------------------------------------------


def _make_run_result(
    query_id: str,
    *,
    passed: bool,
    reciprocal_rank: float = 0.0,
) -> RunResult:
    return RunResult(
        query_id=query_id,
        query=f"query for {query_id}",
        category="test",
        results_found=5,
        top_titles=[],
        first_relevant_rank=None,
        first_relevant_rank_at_10=None,
        reciprocal_rank=reciprocal_rank,
        precision_at_5=0.0,
        ndcg_at_5=None,
        expected_min_results=1,
        passed=passed,
        eval_mode="exact_mrr",
    )


def _make_eval_run(
    *,
    commit: str = "abc1234",
    anchor_date: str = "2026-05-01",
    per_query: list[RunResult] | None = None,
) -> EvalRun:
    return EvalRun(
        config=EvalRunConfig(
            judge_mode="keyword",
            semantic_enabled=False,
            live_mode=False,
            overlay_enabled=False,
        ),
        metadata=EvalRunMetadata(
            timestamp="2026-05-01T00:00:00",
            frozen_at="2026-05-01T00:00:00",
            anchor_date=anchor_date,
            commit=commit,
            python_version="3.12",
            tokenizer_version=1,
        ),
        results=EvalRunResults(
            total_queries=len(per_query) if per_query else 0,
            skipped_queries=0,
            metrics={},
            by_category={},
            per_query=per_query or [],
            failures=[],
        ),
    )


# ---------------------------------------------------------------------------
# compare_eval_runs
# ---------------------------------------------------------------------------


class TestCompareEvalRunsIdentical:
    def test_no_fixed_or_regressed(self) -> None:
        run = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
                _make_run_result("Q2", passed=False, reciprocal_rank=0.0),
            ]
        )
        comp = compare_eval_runs(run, run)
        assert comp.fixed_query_ids == []
        assert comp.regressed_query_ids == []
        assert comp.failure_delta == 0

    def test_still_lists_correct(self) -> None:
        run = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
                _make_run_result("Q2", passed=False, reciprocal_rank=0.0),
            ]
        )
        comp = compare_eval_runs(run, run)
        assert comp.still_passing_ids == ["Q1"]
        assert comp.still_failing_ids == ["Q2"]
        assert comp.total_shared_queries == 2


class TestCompareEvalRunsFixed:
    def test_one_fixed(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=False, reciprocal_rank=0.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        comp = compare_eval_runs(baseline, candidate)
        assert comp.fixed_query_ids == ["Q1"]
        assert comp.regressed_query_ids == []
        assert comp.still_failing_ids == []
        assert comp.still_passing_ids == []


class TestCompareEvalRunsRegressed:
    def test_one_regressed(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=False, reciprocal_rank=0.0),
            ]
        )
        comp = compare_eval_runs(baseline, candidate)
        assert comp.regressed_query_ids == ["Q1"]
        assert comp.fixed_query_ids == []


class TestCompareEvalRunsStill:
    def test_still_failing_and_still_passing(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
                _make_run_result("Q2", passed=False, reciprocal_rank=0.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=0.5),
                _make_run_result("Q2", passed=False, reciprocal_rank=0.2),
            ]
        )
        comp = compare_eval_runs(baseline, candidate)
        assert comp.still_passing_ids == ["Q1"]
        assert comp.still_failing_ids == ["Q2"]


class TestCompareEvalRunsNewMissing:
    def test_candidate_only_is_new(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
                _make_run_result("Q2", passed=True, reciprocal_rank=0.5),
            ]
        )
        comp = compare_eval_runs(baseline, candidate)
        assert comp.new_in_candidate == ["Q2"]
        assert comp.missing_from_candidate == []

    def test_baseline_only_is_missing(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
                _make_run_result("Q2", passed=False, reciprocal_rank=0.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        comp = compare_eval_runs(baseline, candidate)
        assert comp.missing_from_candidate == ["Q2"]
        assert comp.new_in_candidate == []


class TestCompareEvalRunsFailureDelta:
    def test_failure_delta_counts_whole_runs(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
                _make_run_result("Q2", passed=False, reciprocal_rank=0.0),
                _make_run_result("Q3", passed=False, reciprocal_rank=0.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
                _make_run_result("Q3", passed=True, reciprocal_rank=0.5),
            ]
        )
        comp = compare_eval_runs(baseline, candidate)
        assert comp.failure_delta == -2  # 0 candidate failures - 2 baseline failures

    def test_failure_delta_includes_non_shared(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
                _make_run_result("Q2", passed=False, reciprocal_rank=0.0),
            ]
        )
        comp = compare_eval_runs(baseline, candidate)
        assert comp.failure_delta == 1  # 1 candidate failure - 0 baseline failures


class TestCompareEvalRunsCommitAnchor:
    def test_fills_commit_and_anchor(self) -> None:
        baseline = _make_eval_run(commit="aaa1111", anchor_date="2026-04-01")
        candidate = _make_eval_run(commit="bbb2222", anchor_date="2026-05-01")
        comp = compare_eval_runs(baseline, candidate)
        assert comp.baseline_commit == "aaa1111"
        assert comp.candidate_commit == "bbb2222"
        assert comp.baseline_anchor == "2026-04-01"
        assert comp.candidate_anchor == "2026-05-01"


# ---------------------------------------------------------------------------
# classify_eval_query_deltas
# ---------------------------------------------------------------------------


class TestClassifyEvalQueryDeltas:
    def test_sorted_by_query_id(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q3", passed=True, reciprocal_rank=1.0),
                _make_run_result("Q1", passed=False, reciprocal_rank=0.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=0.5),
                _make_run_result("Q3", passed=True, reciprocal_rank=0.3),
            ]
        )
        deltas = classify_eval_query_deltas(baseline, candidate)
        ids = [d.query_id for d in deltas]
        assert ids == ["Q1", "Q3"]

    def test_scores_use_reciprocal_rank(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=False, reciprocal_rank=0.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=0.5),
            ]
        )
        deltas = classify_eval_query_deltas(baseline, candidate)
        assert deltas[0].baseline_score == 0.0
        assert deltas[0].candidate_score == 0.5
        assert deltas[0].delta == 0.5

    def test_new_in_candidate_has_no_baseline_score(self) -> None:
        baseline = _make_eval_run(per_query=[])
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        deltas = classify_eval_query_deltas(baseline, candidate)
        assert len(deltas) == 1
        assert deltas[0].status == "new_in_candidate"
        assert deltas[0].baseline_score is None
        assert deltas[0].candidate_score == 1.0
        assert deltas[0].delta is None

    def test_missing_from_candidate_has_no_candidate_score(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=0.5),
            ]
        )
        candidate = _make_eval_run(per_query=[])
        deltas = classify_eval_query_deltas(baseline, candidate)
        assert len(deltas) == 1
        assert deltas[0].status == "missing_from_candidate"
        assert deltas[0].baseline_score == 0.5
        assert deltas[0].candidate_score is None
        assert deltas[0].delta is None

    def test_no_title_or_query_text_in_deltas(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=False, reciprocal_rank=0.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        deltas = classify_eval_query_deltas(baseline, candidate)
        for d in deltas:
            serialized = str(d.to_dict())
            assert "query for" not in serialized
            assert "Secret Title" not in serialized


# ---------------------------------------------------------------------------
# _ranked_doc_ids
# ---------------------------------------------------------------------------


class TestRankedDocIds:
    def test_sorted_by_score_desc(self) -> None:
        run: dict[str, float] = {"D1": 0.3, "D2": 0.8, "D3": 0.1}
        assert _ranked_doc_ids(run) == ["D2", "D1", "D3"]

    def test_tiebreak_by_doc_id_asc(self) -> None:
        run: dict[str, float] = {"D3": 1.0, "D1": 1.0, "D2": 1.0}
        assert _ranked_doc_ids(run) == ["D1", "D2", "D3"]

    def test_empty_run(self) -> None:
        assert _ranked_doc_ids({}) == []


# ---------------------------------------------------------------------------
# _mrr_at_k
# ---------------------------------------------------------------------------


class TestMrrAtK:
    def test_relevant_at_rank_1(self) -> None:
        qrels: dict[str, int] = {"D1": 1}
        run: dict[str, float] = {"D1": 2.0, "D2": 1.0}
        assert _mrr_at_k(qrels, run, k=5) == 1.0

    def test_relevant_at_rank_2(self) -> None:
        qrels: dict[str, int] = {"D2": 1}
        run: dict[str, float] = {"D1": 2.0, "D2": 1.0}
        assert _mrr_at_k(qrels, run, k=5) == 0.5

    def test_relevant_outside_top_k(self) -> None:
        qrels: dict[str, int] = {"D6": 1}
        run: dict[str, float] = {
            "D1": 6.0,
            "D2": 5.0,
            "D3": 4.0,
            "D4": 3.0,
            "D5": 2.0,
            "D6": 1.0,
        }
        assert _mrr_at_k(qrels, run, k=5) == 0.0

    def test_no_relevant_docs(self) -> None:
        qrels: dict[str, int] = {"D1": 0}
        run: dict[str, float] = {"D1": 1.0}
        assert _mrr_at_k(qrels, run, k=5) == 0.0

    def test_empty_qrels(self) -> None:
        assert _mrr_at_k({}, {"D1": 1.0}, k=5) == 0.0

    def test_empty_run(self) -> None:
        assert _mrr_at_k({"D1": 1}, {}, k=5) == 0.0


# ---------------------------------------------------------------------------
# _recall_at_k
# ---------------------------------------------------------------------------


class TestRecallAtK:
    def test_two_relevant_one_hit(self) -> None:
        qrels: dict[str, int] = {"D1": 1, "D2": 1}
        run: dict[str, float] = {"D1": 2.0, "D3": 1.0}
        assert _recall_at_k(qrels, run, k=5) == 0.5

    def test_all_relevant_found(self) -> None:
        qrels: dict[str, int] = {"D1": 1, "D2": 1}
        run: dict[str, float] = {"D1": 2.0, "D2": 1.0}
        assert _recall_at_k(qrels, run, k=5) == 1.0

    def test_none_found(self) -> None:
        qrels: dict[str, int] = {"D1": 1, "D2": 1}
        run: dict[str, float] = {"D3": 2.0, "D4": 1.0}
        assert _recall_at_k(qrels, run, k=5) == 0.0

    def test_empty_qrels(self) -> None:
        assert _recall_at_k({}, {"D1": 1.0}, k=5) == 0.0


# ---------------------------------------------------------------------------
# compare_runs
# ---------------------------------------------------------------------------


class TestCompareRunsStatusFixed:
    def test_fixed_when_a_zero_b_positive(self) -> None:
        qrels = {"Q1": {"D1": 1}}
        run_a: dict[str, dict[str, float]] = {"Q1": {"D2": 1.0}}
        run_b: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        rc = compare_runs(qrels, run_a, run_b)
        assert rc.per_query_deltas[0].status == "fixed"


class TestCompareRunsStatusRegressed:
    def test_regressed_when_a_positive_b_zero(self) -> None:
        qrels = {"Q1": {"D1": 1}}
        run_a: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        run_b: dict[str, dict[str, float]] = {"Q1": {"D2": 1.0}}
        rc = compare_runs(qrels, run_a, run_b)
        assert rc.per_query_deltas[0].status == "regressed"


class TestCompareRunsStatusStillFailing:
    def test_still_failing_when_both_zero(self) -> None:
        qrels = {"Q1": {"D1": 1}}
        run_a: dict[str, dict[str, float]] = {"Q1": {"D2": 1.0}}
        run_b: dict[str, dict[str, float]] = {"Q1": {"D3": 1.0}}
        rc = compare_runs(qrels, run_a, run_b)
        assert rc.per_query_deltas[0].status == "still_failing"


class TestCompareRunsStatusStillPassing:
    def test_still_passing_when_both_positive(self) -> None:
        qrels = {"Q1": {"D1": 1}}
        run_a: dict[str, dict[str, float]] = {"Q1": {"D1": 2.0, "D2": 1.0}}
        run_b: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        rc = compare_runs(qrels, run_a, run_b)
        assert rc.per_query_deltas[0].status == "still_passing"


class TestCompareRunsSkipNoRelevant:
    def test_skip_qrels_with_no_relevant_docs(self) -> None:
        qrels = {"Q1": {"D1": 0}}
        run_a: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        run_b: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        rc = compare_runs(qrels, run_a, run_b)
        assert rc.queries_skipped_no_qrel == 1
        assert rc.queries_compared == 0
        assert rc.per_query_deltas[0].status == "skipped_no_qrel"


class TestCompareRunsMissingRunQuery:
    def test_missing_run_query_counts_as_zero(self) -> None:
        qrels = {"Q1": {"D1": 1}, "Q2": {"D2": 1}}
        run_a: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        run_b: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        rc = compare_runs(qrels, run_a, run_b)
        assert rc.queries_compared == 2
        q2_delta = [d for d in rc.per_query_deltas if d.query_id == "Q2"][0]
        assert q2_delta.baseline_score == 0.0
        assert q2_delta.candidate_score == 0.0
        assert q2_delta.delta == 0.0


class TestCompareRunsAggregateDeltas:
    def test_aggregate_metric_deltas_correct(self) -> None:
        qrels = {"Q1": {"D1": 1}, "Q2": {"D2": 1}}
        run_a: dict[str, dict[str, float]] = {
            "Q1": {"D1": 1.0},
            "Q2": {"D3": 1.0},
        }
        run_b: dict[str, dict[str, float]] = {
            "Q1": {"D1": 1.0},
            "Q2": {"D2": 1.0},
        }
        rc = compare_runs(qrels, run_a, run_b)
        assert len(rc.metric_deltas) == 2
        mrr_delta = [m for m in rc.metric_deltas if m.metric_name == "mrr_at_5"][0]
        recall_delta = [m for m in rc.metric_deltas if m.metric_name == "recall_at_5"][0]
        # Q1: both mrr=1.0, delta=0. Q2: a=0.0, b=1.0, delta=1.0. Mean delta=0.5
        assert mrr_delta.delta == 0.5
        assert mrr_delta.direction == "improved"
        # Q1: both recall=1.0. Q2: a=0.0, b=1.0. Mean delta=0.5
        assert recall_delta.delta == 0.5


class TestCompareRunsPerQueryDeltas:
    def test_per_query_includes_both_metrics(self) -> None:
        qrels = {"Q1": {"D1": 1}}
        run_a: dict[str, dict[str, float]] = {"Q1": {"D2": 1.0}}
        run_b: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        rc = compare_runs(qrels, run_a, run_b)
        pq = rc.per_query_deltas[0]
        names = [m.metric_name for m in pq.metric_deltas]
        assert "mrr_at_5" in names
        assert "recall_at_5" in names


class TestCompareRunsNoLeakage:
    def test_no_title_query_text_in_comparison(self) -> None:
        qrels = {"Q1": {"D1": 1}}
        run_a: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        run_b: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        rc = compare_runs(qrels, run_a, run_b)
        serialized = str(rc.to_dict())
        assert "Secret Title" not in serialized
        assert "query text" not in serialized

    def test_module_does_not_import_ranx(self) -> None:
        mod = importlib.import_module("tools.eval.eval_compare")
        source = open(mod.__file__, encoding="utf-8").read()
        import_lines = [
            line
            for line in source.splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        joined = "\n".join(import_lines)
        assert "ranx" not in joined


# ---------------------------------------------------------------------------
# classify_query_deltas
# ---------------------------------------------------------------------------


class TestClassifyQueryDeltasNoIR:
    def test_equivalent_to_pass_fail_without_qrels(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=False, reciprocal_rank=0.0),
                _make_run_result("Q2", passed=True, reciprocal_rank=1.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=0.5),
                _make_run_result("Q2", passed=False, reciprocal_rank=0.0),
            ]
        )
        deltas = classify_query_deltas(baseline, candidate)
        assert len(deltas) == 2
        q1 = [d for d in deltas if d.query_id == "Q1"][0]
        q2 = [d for d in deltas if d.query_id == "Q2"][0]
        assert q1.status == "fixed"
        assert q2.status == "regressed"
        assert q1.metric_deltas == []
        assert q2.metric_deltas == []


class TestClassifyQueryDeltasWithIR:
    def test_attaches_mrr_and_recall(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=False, reciprocal_rank=0.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        qrels: dict[str, dict[str, int]] = {"Q1": {"D1": 1}}
        run_a: dict[str, dict[str, float]] = {"Q1": {"D2": 1.0}}
        run_b: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        deltas = classify_query_deltas(baseline, candidate, qrels=qrels, run_a=run_a, run_b=run_b)
        assert len(deltas) == 1
        q1 = deltas[0]
        assert q1.status == "fixed"
        names = [m.metric_name for m in q1.metric_deltas]
        assert "mrr_at_5" in names
        assert "recall_at_5" in names

    def test_skipped_no_qrel_keeps_pass_fail_status(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        qrels: dict[str, dict[str, int]] = {"Q1": {"D1": 0}}
        run_a: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        run_b: dict[str, dict[str, float]] = {"Q1": {"D1": 1.0}}
        deltas = classify_query_deltas(baseline, candidate, qrels=qrels, run_a=run_a, run_b=run_b)
        assert len(deltas) == 1
        assert deltas[0].status == "still_passing"
        assert deltas[0].metric_deltas == []


class TestClassifyQueryDeltasQrelsOnlyInQrels:
    def test_qrels_only_queries_not_in_output(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        qrels: dict[str, dict[str, int]] = {
            "Q1": {"D1": 1},
            "Q2": {"D2": 1},
        }
        run_a: dict[str, dict[str, float]] = {
            "Q1": {"D1": 1.0},
            "Q2": {"D2": 1.0},
        }
        run_b: dict[str, dict[str, float]] = {
            "Q1": {"D1": 1.0},
            "Q2": {"D2": 1.0},
        }
        deltas = classify_query_deltas(baseline, candidate, qrels=qrels, run_a=run_a, run_b=run_b)
        ids = [d.query_id for d in deltas]
        assert "Q2" not in ids
        assert "Q1" in ids


class TestClassifyQueryDeltasNewMissing:
    def test_new_in_candidate_keeps_status(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
                _make_run_result("Q2", passed=True, reciprocal_rank=0.5),
            ]
        )
        deltas = classify_query_deltas(baseline, candidate)
        q2 = [d for d in deltas if d.query_id == "Q2"][0]
        assert q2.status == "new_in_candidate"
        assert q2.metric_deltas == []

    def test_missing_from_candidate_keeps_status(self) -> None:
        baseline = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
                _make_run_result("Q2", passed=False, reciprocal_rank=0.0),
            ]
        )
        candidate = _make_eval_run(
            per_query=[
                _make_run_result("Q1", passed=True, reciprocal_rank=1.0),
            ]
        )
        deltas = classify_query_deltas(baseline, candidate)
        q2 = [d for d in deltas if d.query_id == "Q2"][0]
        assert q2.status == "missing_from_candidate"
        assert q2.metric_deltas == []


# ---------------------------------------------------------------------------
# export_comparison_report
# ---------------------------------------------------------------------------


class TestExportComparisonReportDeterministic:
    def test_deterministic_output(self) -> None:
        ec = EvalComparison(
            baseline_commit="aaa1111",
            candidate_commit="bbb2222",
            baseline_anchor="2026-05-01",
            candidate_anchor="2026-05-08",
            total_shared_queries=10,
            fixed_query_ids=["Q1"],
            regressed_query_ids=["Q2"],
            still_failing_ids=["Q3"],
            still_passing_ids=["Q4"],
            failure_delta=-1,
        )
        report = export_comparison_report(ec)
        assert "baseline: aaa1111" in report
        assert "candidate: bbb2222" in report
        assert "shared_queries: 10" in report
        assert "failure_delta: -1" in report
        assert "fixed: 1 regressed: 1 still_failing: 1 still_passing: 1" in report
        assert "=== End Report ===" in report

    def test_with_run_comparison(self) -> None:
        ec = EvalComparison(
            baseline_commit="a",
            candidate_commit="b",
            baseline_anchor="x",
            candidate_anchor="y",
            total_shared_queries=5,
        )
        rc = RunComparison(
            metric_deltas=[
                MetricDelta("mrr_at_5", 0.3, 0.5, 0.2, "improved"),
                MetricDelta("recall_at_5", 0.4, 0.6, 0.2, "improved"),
            ],
            queries_compared=5,
            queries_skipped_no_qrel=1,
        )
        report = export_comparison_report(ec, run_comparison=rc)
        assert "--- IR Metrics ---" in report
        assert "mrr_at_5:" in report
        assert "recall_at_5:" in report
        assert "queries_compared: 5" in report

    def test_with_query_deltas(self) -> None:
        ec = EvalComparison(
            baseline_commit="a",
            candidate_commit="b",
            baseline_anchor="x",
            candidate_anchor="y",
            total_shared_queries=1,
            fixed_query_ids=["Q1"],
        )
        qd = QueryDelta(
            query_id="Q1",
            status="fixed",
            baseline_score=0.0,
            candidate_score=1.0,
            delta=1.0,
            metric_deltas=[
                MetricDelta("mrr_at_5", 0.0, 1.0, 1.0, "improved"),
            ],
        )
        report = export_comparison_report(ec, query_deltas=[qd])
        assert "--- Per-Query Deltas ---" in report
        assert "Q1 fixed delta=+1.0000" in report
        assert "[mrr_at_5=+1.0000]" in report


class TestExportComparisonReportNoLeakage:
    def test_no_query_text_title_doc_id_path(self) -> None:
        ec = EvalComparison(
            baseline_commit="a",
            candidate_commit="b",
            baseline_anchor="x",
            candidate_anchor="y",
            total_shared_queries=1,
        )
        qd = QueryDelta(
            query_id="Q1",
            status="fixed",
            baseline_score=0.0,
            candidate_score=1.0,
            delta=1.0,
        )
        report = export_comparison_report(ec, query_deltas=[qd])
        assert "Secret Title" not in report
        assert "query text" not in report
        assert "doc_" not in report
        assert "C:\\" not in report
        assert "/" not in report.replace("delta=", "").replace("mrr_at_5", "")


class TestExportComparisonReportSafety:
    def test_module_does_not_import_run_eval_or_search(self) -> None:
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
        assert "ranx" not in joined
