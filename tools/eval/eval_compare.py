#!/usr/bin/env python3
"""Typed comparison dataclasses and pass/fail comparison for eval runs (R2-B4c).

Defines data types for comparing two eval runs or two IR Run dicts, and
implements per-query pass/fail delta classification between EvalRun objects.

This module imports only eval_types (data layer). It does not import the
runtime eval module, any search module, eval_qrels, eval_run, or ranx.
"""

from __future__ import annotations

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
