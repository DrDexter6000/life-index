#!/usr/bin/env python3
"""Typed comparison dataclasses, pass/fail comparison, and IR metrics (R2-B4e).

Defines data types for comparing two eval runs or two IR Run dicts, implements
per-query pass/fail delta classification, computes MRR@5 / Recall@5
against qrels without ranx, unifies deltas, and exports text reports.

This module imports only eval_types (data layer). It does not import the
runtime eval module, any search module, eval_qrels, eval_run, or ranx.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from tools.eval.eval_types import EvalRun, RunResult

# ---------------------------------------------------------------------------
# Direction helper
# ---------------------------------------------------------------------------


def classify_metric_direction(
    delta: float,
    *,
    epsilon: float = 1e-12,
) -> Literal["improved", "regressed", "unchanged"]:
    """Classify a numeric delta into a direction.

    Positive delta = improved, negative = regressed, within epsilon = unchanged.
    """
    if delta > epsilon:
        return "improved"
    if delta < -epsilon:
        return "regressed"
    return "unchanged"


# ---------------------------------------------------------------------------
# MetricDelta
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricDelta:
    """Change in a single metric between two runs."""

    metric_name: str
    baseline_value: float
    candidate_value: float
    delta: float
    direction: Literal["improved", "regressed", "unchanged"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "baseline_value": self.baseline_value,
            "candidate_value": self.candidate_value,
            "delta": self.delta,
            "direction": self.direction,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricDelta:
        return cls(
            metric_name=str(data["metric_name"]),
            baseline_value=float(data["baseline_value"]),
            candidate_value=float(data["candidate_value"]),
            delta=float(data["delta"]),
            direction=cast(
                Literal["improved", "regressed", "unchanged"],
                str(data["direction"]),
            ),
        )


# ---------------------------------------------------------------------------
# QueryDelta
# ---------------------------------------------------------------------------

_QUERY_DELTA_STATUSES = frozenset(
    {
        "fixed",
        "regressed",
        "still_failing",
        "still_passing",
        "new_in_candidate",
        "missing_from_candidate",
        "skipped_no_qrel",
    }
)


@dataclass(frozen=True)
class QueryDelta:
    """Per-query comparison row."""

    query_id: str
    status: Literal[
        "fixed",
        "regressed",
        "still_failing",
        "still_passing",
        "new_in_candidate",
        "missing_from_candidate",
        "skipped_no_qrel",
    ]
    baseline_score: float | None = None
    candidate_score: float | None = None
    delta: float | None = None
    metric_deltas: list[MetricDelta] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "query_id": self.query_id,
            "status": self.status,
        }
        if self.baseline_score is not None:
            d["baseline_score"] = self.baseline_score
        if self.candidate_score is not None:
            d["candidate_score"] = self.candidate_score
        if self.delta is not None:
            d["delta"] = self.delta
        if self.metric_deltas:
            d["metric_deltas"] = [md.to_dict() for md in self.metric_deltas]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryDelta:
        raw_deltas = data.get("metric_deltas", [])
        return cls(
            query_id=str(data["query_id"]),
            status=cast(
                Literal[
                    "fixed",
                    "regressed",
                    "still_failing",
                    "still_passing",
                    "new_in_candidate",
                    "missing_from_candidate",
                    "skipped_no_qrel",
                ],
                str(data["status"]),
            ),
            baseline_score=(float(data["baseline_score"]) if "baseline_score" in data else None),
            candidate_score=(float(data["candidate_score"]) if "candidate_score" in data else None),
            delta=float(data["delta"]) if "delta" in data else None,
            metric_deltas=[MetricDelta.from_dict(md) for md in raw_deltas],
        )


# ---------------------------------------------------------------------------
# EvalComparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalComparison:
    """Top-level comparison of two EvalRun objects."""

    baseline_commit: str
    candidate_commit: str
    baseline_anchor: str
    candidate_anchor: str
    total_shared_queries: int
    fixed_query_ids: list[str] = field(default_factory=list)
    regressed_query_ids: list[str] = field(default_factory=list)
    still_failing_ids: list[str] = field(default_factory=list)
    still_passing_ids: list[str] = field(default_factory=list)
    new_in_candidate: list[str] = field(default_factory=list)
    missing_from_candidate: list[str] = field(default_factory=list)
    failure_delta: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_commit": self.baseline_commit,
            "candidate_commit": self.candidate_commit,
            "baseline_anchor": self.baseline_anchor,
            "candidate_anchor": self.candidate_anchor,
            "total_shared_queries": self.total_shared_queries,
            "fixed_query_ids": list(self.fixed_query_ids),
            "regressed_query_ids": list(self.regressed_query_ids),
            "still_failing_ids": list(self.still_failing_ids),
            "still_passing_ids": list(self.still_passing_ids),
            "new_in_candidate": list(self.new_in_candidate),
            "missing_from_candidate": list(self.missing_from_candidate),
            "failure_delta": self.failure_delta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalComparison:
        return cls(
            baseline_commit=str(data["baseline_commit"]),
            candidate_commit=str(data["candidate_commit"]),
            baseline_anchor=str(data["baseline_anchor"]),
            candidate_anchor=str(data["candidate_anchor"]),
            total_shared_queries=int(data["total_shared_queries"]),
            fixed_query_ids=list(data.get("fixed_query_ids", [])),
            regressed_query_ids=list(data.get("regressed_query_ids", [])),
            still_failing_ids=list(data.get("still_failing_ids", [])),
            still_passing_ids=list(data.get("still_passing_ids", [])),
            new_in_candidate=list(data.get("new_in_candidate", [])),
            missing_from_candidate=list(data.get("missing_from_candidate", [])),
            failure_delta=int(data.get("failure_delta", 0)),
        )


# ---------------------------------------------------------------------------
# RunComparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunComparison:
    """IR-metric comparison of two Run dicts against shared qrels."""

    metric_deltas: list[MetricDelta] = field(default_factory=list)
    per_query_deltas: list[QueryDelta] = field(default_factory=list)
    queries_compared: int = 0
    queries_skipped_no_qrel: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_deltas": [md.to_dict() for md in self.metric_deltas],
            "per_query_deltas": [qd.to_dict() for qd in self.per_query_deltas],
            "queries_compared": self.queries_compared,
            "queries_skipped_no_qrel": self.queries_skipped_no_qrel,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunComparison:
        return cls(
            metric_deltas=[MetricDelta.from_dict(md) for md in data.get("metric_deltas", [])],
            per_query_deltas=[QueryDelta.from_dict(qd) for qd in data.get("per_query_deltas", [])],
            queries_compared=int(data.get("queries_compared", 0)),
            queries_skipped_no_qrel=int(data.get("queries_skipped_no_qrel", 0)),
        )


# ---------------------------------------------------------------------------
# Pass/fail comparison functions
# ---------------------------------------------------------------------------


def compare_eval_runs(
    baseline: EvalRun,
    candidate: EvalRun,
) -> EvalComparison:
    """Compare two EvalRun objects at the per-query pass/fail level.

    Classifies each shared query_id as fixed, regressed, still_failing, or
    still_passing based on the RunResult.passed field. Also identifies
    queries present in only one run.

    failure_delta counts across the entire run (not only shared queries).
    """
    baseline_map: dict[str, RunResult] = {r.query_id: r for r in baseline.results.per_query}
    candidate_map: dict[str, RunResult] = {r.query_id: r for r in candidate.results.per_query}

    shared_ids = sorted(set(baseline_map) & set(candidate_map))
    new_in_candidate = sorted(set(candidate_map) - set(baseline_map))
    missing_from_candidate = sorted(set(baseline_map) - set(candidate_map))

    fixed: list[str] = []
    regressed: list[str] = []
    still_failing: list[str] = []
    still_passing: list[str] = []

    for qid in shared_ids:
        b_passed = baseline_map[qid].passed
        c_passed = candidate_map[qid].passed
        if not b_passed and c_passed:
            fixed.append(qid)
        elif b_passed and not c_passed:
            regressed.append(qid)
        elif not b_passed and not c_passed:
            still_failing.append(qid)
        else:
            still_passing.append(qid)

    baseline_failures = sum(1 for r in baseline.results.per_query if not r.passed)
    candidate_failures = sum(1 for r in candidate.results.per_query if not r.passed)

    return EvalComparison(
        baseline_commit=baseline.metadata.commit,
        candidate_commit=candidate.metadata.commit,
        baseline_anchor=baseline.metadata.anchor_date,
        candidate_anchor=candidate.metadata.anchor_date,
        total_shared_queries=len(shared_ids),
        fixed_query_ids=fixed,
        regressed_query_ids=regressed,
        still_failing_ids=still_failing,
        still_passing_ids=still_passing,
        new_in_candidate=new_in_candidate,
        missing_from_candidate=missing_from_candidate,
        failure_delta=candidate_failures - baseline_failures,
    )


def classify_eval_query_deltas(
    baseline: EvalRun,
    candidate: EvalRun,
) -> list[QueryDelta]:
    """Produce per-query delta rows combining pass/fail status and reciprocal_rank.

    Returns one QueryDelta per union query_id, sorted by query_id.
    Uses reciprocal_rank as the score field.
    """
    baseline_map: dict[str, RunResult] = {r.query_id: r for r in baseline.results.per_query}
    candidate_map: dict[str, RunResult] = {r.query_id: r for r in candidate.results.per_query}

    all_ids = sorted(set(baseline_map) | set(candidate_map))
    deltas: list[QueryDelta] = []

    for qid in all_ids:
        b = baseline_map.get(qid)
        c = candidate_map.get(qid)

        if b is not None and c is not None:
            b_passed = b.passed
            c_passed = c.passed
            if not b_passed and c_passed:
                status: Literal[
                    "fixed",
                    "regressed",
                    "still_failing",
                    "still_passing",
                    "new_in_candidate",
                    "missing_from_candidate",
                    "skipped_no_qrel",
                ] = "fixed"
            elif b_passed and not c_passed:
                status = "regressed"
            elif not b_passed and not c_passed:
                status = "still_failing"
            else:
                status = "still_passing"
            b_score = b.reciprocal_rank
            c_score = c.reciprocal_rank
            deltas.append(
                QueryDelta(
                    query_id=qid,
                    status=status,
                    baseline_score=b_score,
                    candidate_score=c_score,
                    delta=c_score - b_score,
                )
            )
        elif c is not None:
            deltas.append(
                QueryDelta(
                    query_id=qid,
                    status="new_in_candidate",
                    baseline_score=None,
                    candidate_score=c.reciprocal_rank,
                    delta=None,
                )
            )
        else:
            assert b is not None  # qid is in union, c is None, so b must exist
            deltas.append(
                QueryDelta(
                    query_id=qid,
                    status="missing_from_candidate",
                    baseline_score=b.reciprocal_rank,
                    candidate_score=None,
                    delta=None,
                )
            )

    return deltas


# ---------------------------------------------------------------------------
# IR metric helpers
# ---------------------------------------------------------------------------


def _ranked_doc_ids(run_for_query: Mapping[str, float]) -> list[str]:
    """Sort doc_ids by score descending, then doc_id ascending for ties."""
    return [
        doc_id
        for doc_id, _score in sorted(
            run_for_query.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _mrr_at_k(
    qrels_for_query: Mapping[str, int],
    run_for_query: Mapping[str, float],
    k: int = 5,
) -> float:
    """Mean Reciprocal Rank at k for a single query."""
    if not qrels_for_query or not run_for_query:
        return 0.0
    relevant = {did for did, rel in qrels_for_query.items() if rel > 0}
    if not relevant:
        return 0.0
    ranked = _ranked_doc_ids(run_for_query)
    for i, doc_id in enumerate(ranked[:k], start=1):
        if doc_id in relevant:
            return 1.0 / i
    return 0.0


def _recall_at_k(
    qrels_for_query: Mapping[str, int],
    run_for_query: Mapping[str, float],
    k: int = 5,
) -> float:
    """Recall at k for a single query."""
    if not qrels_for_query:
        return 0.0
    relevant = {did for did, rel in qrels_for_query.items() if rel > 0}
    if not relevant:
        return 0.0
    ranked = _ranked_doc_ids(run_for_query)
    top_k = set(ranked[:k])
    return len(top_k & relevant) / len(relevant)


# ---------------------------------------------------------------------------
# Run comparison function
# ---------------------------------------------------------------------------

_QueryStatus = Literal[
    "fixed",
    "regressed",
    "still_failing",
    "still_passing",
    "new_in_candidate",
    "missing_from_candidate",
    "skipped_no_qrel",
]


def compare_runs(
    qrels: Mapping[str, Mapping[str, int]],
    run_a: Mapping[str, Mapping[str, float]],
    run_b: Mapping[str, Mapping[str, float]],
) -> RunComparison:
    """Compare two Run dicts against shared qrels using MRR@5 and Recall@5.

    Iterates over query_ids present in qrels. Queries with no relevant docs
    are skipped (counted in queries_skipped_no_qrel). Missing run entries
    count as empty runs (all metrics = 0.0).
    """
    query_ids = sorted(qrels.keys())
    per_query: list[QueryDelta] = []
    queries_compared = 0
    queries_skipped = 0

    mrr_a_sum = 0.0
    mrr_b_sum = 0.0
    recall_a_sum = 0.0
    recall_b_sum = 0.0

    for qid in query_ids:
        qrels_q = qrels[qid]
        relevant = {did for did, rel in qrels_q.items() if rel > 0}
        if not relevant:
            per_query.append(QueryDelta(query_id=qid, status="skipped_no_qrel"))
            queries_skipped += 1
            continue

        run_a_q = run_a.get(qid, {})
        run_b_q = run_b.get(qid, {})

        mrr_a = _mrr_at_k(qrels_q, run_a_q)
        mrr_b = _mrr_at_k(qrels_q, run_b_q)
        recall_a = _recall_at_k(qrels_q, run_a_q)
        recall_b = _recall_at_k(qrels_q, run_b_q)

        mrr_delta_val = mrr_b - mrr_a
        recall_delta_val = recall_b - recall_a

        if mrr_a < 1e-12 and mrr_b > 1e-12:
            status: _QueryStatus = "fixed"
        elif mrr_a > 1e-12 and mrr_b < 1e-12:
            status = "regressed"
        elif mrr_a < 1e-12 and mrr_b < 1e-12:
            status = "still_failing"
        else:
            status = "still_passing"

        metric_deltas = [
            MetricDelta(
                metric_name="mrr_at_5",
                baseline_value=mrr_a,
                candidate_value=mrr_b,
                delta=mrr_delta_val,
                direction=classify_metric_direction(mrr_delta_val),
            ),
            MetricDelta(
                metric_name="recall_at_5",
                baseline_value=recall_a,
                candidate_value=recall_b,
                delta=recall_delta_val,
                direction=classify_metric_direction(recall_delta_val),
            ),
        ]

        per_query.append(
            QueryDelta(
                query_id=qid,
                status=status,
                baseline_score=mrr_a,
                candidate_score=mrr_b,
                delta=mrr_delta_val,
                metric_deltas=metric_deltas,
            )
        )

        mrr_a_sum += mrr_a
        mrr_b_sum += mrr_b
        recall_a_sum += recall_a
        recall_b_sum += recall_b
        queries_compared += 1

    aggregate_deltas: list[MetricDelta] = []
    if queries_compared > 0:
        mean_mrr_a = mrr_a_sum / queries_compared
        mean_mrr_b = mrr_b_sum / queries_compared
        mean_recall_a = recall_a_sum / queries_compared
        mean_recall_b = recall_b_sum / queries_compared

        mrr_agg_delta = mean_mrr_b - mean_mrr_a
        recall_agg_delta = mean_recall_b - mean_recall_a

        aggregate_deltas = [
            MetricDelta(
                metric_name="mrr_at_5",
                baseline_value=mean_mrr_a,
                candidate_value=mean_mrr_b,
                delta=mrr_agg_delta,
                direction=classify_metric_direction(mrr_agg_delta),
            ),
            MetricDelta(
                metric_name="recall_at_5",
                baseline_value=mean_recall_a,
                candidate_value=mean_recall_b,
                delta=recall_agg_delta,
                direction=classify_metric_direction(recall_agg_delta),
            ),
        ]

    return RunComparison(
        metric_deltas=aggregate_deltas,
        per_query_deltas=per_query,
        queries_compared=queries_compared,
        queries_skipped_no_qrel=queries_skipped,
    )


# ---------------------------------------------------------------------------
# Unified comparison
# ---------------------------------------------------------------------------

_PassFailStatus = Literal[
    "fixed",
    "regressed",
    "still_failing",
    "still_passing",
    "new_in_candidate",
    "missing_from_candidate",
]


def classify_query_deltas(
    baseline: EvalRun,
    candidate: EvalRun,
    qrels: Mapping[str, Mapping[str, int]] | None = None,
    run_a: Mapping[str, Mapping[str, float]] | None = None,
    run_b: Mapping[str, Mapping[str, float]] | None = None,
) -> list[QueryDelta]:
    """Unify pass/fail deltas with optional IR metric deltas per query.

    Primary query set = union of baseline/candidate EvalRun per_query query_ids.
    Primary status from pass/fail. If qrels + run_a + run_b all provided,
    attaches per-query mrr_at_5 / recall_at_5 MetricDeltas from compare_runs()
    for matching query_ids. Queries skipped by compare_runs (no relevant docs)
    keep their pass/fail status without IR metric_deltas.
    """
    baseline_map: dict[str, RunResult] = {r.query_id: r for r in baseline.results.per_query}
    candidate_map: dict[str, RunResult] = {r.query_id: r for r in candidate.results.per_query}

    all_ids = sorted(set(baseline_map) | set(candidate_map))

    ir_lookup: dict[str, list[MetricDelta]] = {}
    has_ir = qrels is not None and run_a is not None and run_b is not None
    if has_ir:
        assert qrels is not None and run_a is not None and run_b is not None
        rc = compare_runs(qrels, run_a, run_b)
        for pq in rc.per_query_deltas:
            if pq.status != "skipped_no_qrel" and pq.metric_deltas:
                ir_lookup[pq.query_id] = pq.metric_deltas

    deltas: list[QueryDelta] = []
    for qid in all_ids:
        b = baseline_map.get(qid)
        c = candidate_map.get(qid)

        if b is not None and c is not None:
            b_passed = b.passed
            c_passed = c.passed
            if not b_passed and c_passed:
                status: _PassFailStatus = "fixed"
            elif b_passed and not c_passed:
                status = "regressed"
            elif not b_passed and not c_passed:
                status = "still_failing"
            else:
                status = "still_passing"
            b_score = b.reciprocal_rank
            c_score = c.reciprocal_rank
            deltas.append(
                QueryDelta(
                    query_id=qid,
                    status=status,
                    baseline_score=b_score,
                    candidate_score=c_score,
                    delta=c_score - b_score,
                    metric_deltas=ir_lookup.get(qid, []),
                )
            )
        elif c is not None:
            deltas.append(
                QueryDelta(
                    query_id=qid,
                    status="new_in_candidate",
                    baseline_score=None,
                    candidate_score=c.reciprocal_rank,
                    delta=None,
                    metric_deltas=[],
                )
            )
        else:
            assert b is not None
            deltas.append(
                QueryDelta(
                    query_id=qid,
                    status="missing_from_candidate",
                    baseline_score=b.reciprocal_rank,
                    candidate_score=None,
                    delta=None,
                    metric_deltas=[],
                )
            )

    return deltas


# ---------------------------------------------------------------------------
# Text report export
# ---------------------------------------------------------------------------


def export_comparison_report(
    eval_comparison: EvalComparison,
    run_comparison: RunComparison | None = None,
    query_deltas: Sequence[QueryDelta] | None = None,
) -> str:
    """Export a deterministic plain-text comparison report.

    Contains failure_delta, fixed/regressed/still counts, aggregate
    MRR@5/Recall@5 deltas (if run_comparison provided), and per-query
    summaries (query_id/status/metric deltas only).

    Never includes query text, journal title, doc_id, or absolute path.
    """
    lines: list[str] = []

    lines.append("=== Eval Comparison Report ===")
    lines.append(f"baseline: {eval_comparison.baseline_commit}")
    lines.append(f"candidate: {eval_comparison.candidate_commit}")
    lines.append(f"shared_queries: {eval_comparison.total_shared_queries}")
    lines.append(f"failure_delta: {eval_comparison.failure_delta}")
    lines.append(
        f"fixed: {len(eval_comparison.fixed_query_ids)} "
        f"regressed: {len(eval_comparison.regressed_query_ids)} "
        f"still_failing: {len(eval_comparison.still_failing_ids)} "
        f"still_passing: {len(eval_comparison.still_passing_ids)}"
    )

    if run_comparison is not None:
        lines.append("")
        lines.append("--- IR Metrics ---")
        for md in run_comparison.metric_deltas:
            lines.append(
                f"{md.metric_name}: "
                f"{md.baseline_value:.4f} -> {md.candidate_value:.4f} "
                f"(delta={md.delta:+.4f}, {md.direction})"
            )
        lines.append(
            f"queries_compared: {run_comparison.queries_compared} "
            f"skipped_no_qrel: {run_comparison.queries_skipped_no_qrel}"
        )

    if query_deltas:
        lines.append("")
        lines.append("--- Per-Query Deltas ---")
        for qd in query_deltas:
            parts = [qd.query_id, qd.status]
            if qd.delta is not None:
                parts.append(f"delta={qd.delta:+.4f}")
            if qd.metric_deltas:
                metric_parts = [f"{m.metric_name}={m.delta:+.4f}" for m in qd.metric_deltas]
                parts.append(f"[{', '.join(metric_parts)}]")
            lines.append(" ".join(parts))

    lines.append("")
    lines.append("=== End Report ===")
    return "\n".join(lines)
