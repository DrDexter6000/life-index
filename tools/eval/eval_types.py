#!/usr/bin/env python3
"""Typed primitives for eval data model (R2-B1).

These dataclasses wrap the untyped dict structures produced by
run_evaluation() and stored in baseline JSONs. They add type safety,
IDE navigation, and forward-compatible round-trip via extra dicts.

No serving-path changes. No ranx dependency. No eval behavior changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Namespace-scoped types (have their own extra dicts for unknown fields)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FailureRecord:
    """A single eval failure entry."""

    query_id: str
    query: str
    reason: str
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailureRecord:
        return cls(
            query_id=str(data.get("id", "")),
            query=str(data.get("query", "")),
            reason=str(data.get("reason", "")),
            extra={k: v for k, v in data.items() if k not in ("id", "query", "reason")},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.query_id, "query": self.query, "reason": self.reason}
        d.update(self.extra)
        return d


@dataclass(frozen=True)
class CategoryMetrics:
    """Aggregate metrics for a single query category."""

    mrr_at_5: float
    recall_at_5: float
    recall_at_10: float
    precision_at_5: float
    ndcg_at_5: float
    query_count: int
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset(
        {
            "mrr_at_5",
            "recall_at_5",
            "recall_at_10",
            "precision_at_5",
            "ndcg_at_5",
            "query_count",
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CategoryMetrics:
        return cls(
            mrr_at_5=float(data.get("mrr_at_5", 0.0)),
            recall_at_5=float(data.get("recall_at_5", 0.0)),
            recall_at_10=float(data.get("recall_at_10", 0.0)),
            precision_at_5=float(data.get("precision_at_5", 0.0)),
            ndcg_at_5=float(data.get("ndcg_at_5", 0.0)),
            query_count=int(data.get("query_count", 0)),
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "mrr_at_5": self.mrr_at_5,
            "recall_at_5": self.recall_at_5,
            "recall_at_10": self.recall_at_10,
            "precision_at_5": self.precision_at_5,
            "ndcg_at_5": self.ndcg_at_5,
            "query_count": self.query_count,
        }
        d.update(self.extra)
        return d


_OPT_FIELDS = (
    "predicate_precision",
    "global_matched_count",
    "returned_count",
    "matched_count",
    "min_results_ok",
    "strict_pass",
    "soft_pass",
    "broad_eval_error",
    "llm_scores",
    "public_query",
    "overlay_applied",
)


@dataclass
class RunResult:
    """Evaluation result for a single query."""

    query_id: str
    query: str
    category: str
    results_found: int
    top_titles: list[str]
    first_relevant_rank: int | None
    first_relevant_rank_at_10: int | None
    reciprocal_rank: float
    precision_at_5: float
    ndcg_at_5: float | None
    expected_min_results: int
    passed: bool
    eval_mode: str
    overlay_applied: bool | None = None
    predicate_precision: float | None = None
    global_matched_count: int | None = None
    returned_count: int | None = None
    matched_count: int | None = None
    min_results_ok: bool | None = None
    strict_pass: bool | None = None
    soft_pass: bool | None = None
    broad_eval_error: str | None = None
    llm_scores: list[int] | None = None
    public_query: str | None = None
    top_doc_ids: list[str] | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)
    _present_opt: frozenset[str] = field(default_factory=frozenset, repr=False)
    _had_ndcg: bool = field(default=False, repr=False)
    _had_top_doc_ids: bool = field(default=False, repr=False)

    _KNOWN_KEYS = frozenset(
        {
            "id",
            "query",
            "category",
            "results_found",
            "top_titles",
            "first_relevant_rank",
            "first_relevant_rank_at_10",
            "reciprocal_rank",
            "precision_at_5",
            "ndcg_at_5",
            "expected_min_results",
            "pass",
            "eval_mode",
            "overlay_applied",
            "predicate_precision",
            "global_matched_count",
            "returned_count",
            "matched_count",
            "min_results_ok",
            "strict_pass",
            "soft_pass",
            "broad_eval_error",
            "llm_scores",
            "public_query",
            "top_doc_ids",
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunResult:
        present = frozenset(k for k in _OPT_FIELDS if k in data)
        had_ndcg = "ndcg_at_5" in data
        had_top_doc_ids = "top_doc_ids" in data
        return cls(
            query_id=str(data.get("id", "")),
            query=str(data.get("query", "")),
            category=str(data.get("category", "")),
            results_found=int(data.get("results_found", 0)),
            top_titles=list(data.get("top_titles", [])),
            first_relevant_rank=data.get("first_relevant_rank"),
            first_relevant_rank_at_10=data.get("first_relevant_rank_at_10"),
            reciprocal_rank=float(data.get("reciprocal_rank", 0.0)),
            precision_at_5=float(data.get("precision_at_5", 0.0)),
            ndcg_at_5=data.get("ndcg_at_5"),
            expected_min_results=int(data.get("expected_min_results", 0)),
            passed=bool(data.get("pass", False)),
            eval_mode=str(data.get("eval_mode", "exact_mrr")),
            overlay_applied=data.get("overlay_applied"),
            predicate_precision=data.get("predicate_precision"),
            global_matched_count=data.get("global_matched_count"),
            returned_count=data.get("returned_count"),
            matched_count=data.get("matched_count"),
            min_results_ok=data.get("min_results_ok"),
            strict_pass=data.get("strict_pass"),
            soft_pass=data.get("soft_pass"),
            broad_eval_error=data.get("broad_eval_error"),
            llm_scores=data.get("llm_scores"),
            public_query=data.get("public_query"),
            top_doc_ids=data.get("top_doc_ids"),
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
            _present_opt=present,
            _had_ndcg=had_ndcg,
            _had_top_doc_ids=had_top_doc_ids,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.query_id,
            "query": self.query,
            "category": self.category,
            "results_found": self.results_found,
            "top_titles": self.top_titles,
            "first_relevant_rank": self.first_relevant_rank,
            "first_relevant_rank_at_10": self.first_relevant_rank_at_10,
            "reciprocal_rank": self.reciprocal_rank,
            "precision_at_5": self.precision_at_5,
            "expected_min_results": self.expected_min_results,
            "pass": self.passed,
        }
        if self._had_ndcg or self.ndcg_at_5 is not None:
            d["ndcg_at_5"] = self.ndcg_at_5
        if self._had_top_doc_ids or self.top_doc_ids is not None:
            d["top_doc_ids"] = self.top_doc_ids
        if self.eval_mode != "exact_mrr":
            d["eval_mode"] = self.eval_mode
        for opt_field in _OPT_FIELDS:
            if self._present_opt:
                if opt_field in self._present_opt:
                    d[opt_field] = getattr(self, opt_field)
            else:
                val = getattr(self, opt_field)
                if val is not None:
                    d[opt_field] = val
        d.update(self.extra)
        return d


@dataclass
class SemanticReport:
    """Report-only semantic comparison appended to eval results."""

    enabled: bool
    metrics: dict[str, float]
    failure_count: int
    failure_ids: list[str]
    fixed_by_semantic: list[str]
    regressed_by_semantic: list[str]
    still_failing_both: list[str]
    delta: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset(
        {
            "enabled",
            "metrics",
            "failure_count",
            "failure_ids",
            "fixed_by_semantic",
            "regressed_by_semantic",
            "still_failing_both",
            "delta",
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticReport:
        return cls(
            enabled=bool(data.get("enabled", False)),
            metrics={k: float(v) for k, v in data.get("metrics", {}).items()},
            failure_count=int(data.get("failure_count", 0)),
            failure_ids=list(data.get("failure_ids", [])),
            fixed_by_semantic=list(data.get("fixed_by_semantic", [])),
            regressed_by_semantic=list(data.get("regressed_by_semantic", [])),
            still_failing_both=list(data.get("still_failing_both", [])),
            delta=dict(data.get("delta", {})),
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "enabled": self.enabled,
            "metrics": self.metrics,
            "failure_count": self.failure_count,
            "failure_ids": self.failure_ids,
            "fixed_by_semantic": self.fixed_by_semantic,
            "regressed_by_semantic": self.regressed_by_semantic,
            "still_failing_both": self.still_failing_both,
            "delta": self.delta,
        }
        d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# Top-level types (no own extra — EvalRun handles unknown top-level keys)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalRunConfig:
    """Immutable configuration that produced an eval run."""

    judge_mode: str
    semantic_enabled: bool
    live_mode: bool
    overlay_enabled: bool


@dataclass(frozen=True)
class EvalRunMetadata:
    """Provenance metadata for an eval run."""

    timestamp: str
    frozen_at: str
    anchor_date: str
    commit: str
    python_version: str
    tokenizer_version: int
    run_id: str | None = None
    frozen_by: str | None = None


@dataclass
class EvalRunResults:
    """Measurement results from an eval run."""

    total_queries: int
    skipped_queries: int
    metrics: dict[str, float]
    by_category: dict[str, CategoryMetrics]
    per_query: list[RunResult]
    failures: list[FailureRecord]
    overlay_applied_count: int | None = None
    overlay_warnings: list[str] | None = None
    broad_eval_metrics: dict[str, Any] | None = None
    recall_gaps: list[Any] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)
    semantic_report: SemanticReport | None = None


# All known top-level keys across config, metadata, results, and baseline.
_TOP_LEVEL_KNOWN_KEYS = frozenset(
    {
        # Config
        "judge_mode",
        "semantic_enabled",
        "live_mode",
        # Metadata
        "timestamp",
        "frozen_at",
        "anchor_date",
        "commit",
        "python_version",
        "tokenizer_version",
        # Baseline
        "baseline_id",
        "meta",
        # Results
        "total_queries",
        "skipped_queries",
        "metrics",
        "by_category",
        "per_query",
        "failures",
        "recall_gaps",
        "summary_lines",
        "overlay_applied_count",
        "overlay_warnings",
        "broad_eval_metrics",
        "semantic_report",
    }
)


@dataclass
class EvalRun:
    """Complete evaluation run with typed config, metadata, and results."""

    config: EvalRunConfig
    metadata: EvalRunMetadata
    results: EvalRunResults
    baseline_meta: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalRun:
        # Config
        overlay_count_raw = data.get("overlay_applied_count")
        overlay_count = int(overlay_count_raw) if overlay_count_raw is not None else None
        config = EvalRunConfig(
            judge_mode=str(data.get("judge_mode", "keyword")),
            semantic_enabled=bool(data.get("semantic_enabled", False)),
            live_mode=bool(data.get("live_mode", False)),
            overlay_enabled=overlay_count is not None and overlay_count > 0,
        )

        # Metadata
        run_id = data.get("baseline_id")
        baseline_meta = data.get("meta")
        frozen_by: str | None = None
        if isinstance(baseline_meta, dict):
            frozen_by = baseline_meta.get("frozen_by")
        metadata = EvalRunMetadata(
            timestamp=str(data.get("timestamp", "")),
            frozen_at=str(data.get("frozen_at", "")),
            anchor_date=str(data.get("anchor_date", "")),
            commit=str(data.get("commit", "")),
            python_version=str(data.get("python_version", "")),
            tokenizer_version=int(data.get("tokenizer_version", 0)),
            run_id=run_id,
            frozen_by=frozen_by,
        )

        # Results
        per_query = [RunResult.from_dict(pq) for pq in data.get("per_query", [])]
        failures = [FailureRecord.from_dict(f) for f in data.get("failures", [])]
        by_category = {
            cat: CategoryMetrics.from_dict(m) for cat, m in data.get("by_category", {}).items()
        }
        sr_data = data.get("semantic_report")
        semantic_report = SemanticReport.from_dict(sr_data) if sr_data else None

        results = EvalRunResults(
            total_queries=int(data.get("total_queries", 0)),
            skipped_queries=int(data.get("skipped_queries", 0)),
            metrics={k: float(v) for k, v in data.get("metrics", {}).items()},
            by_category=by_category,
            per_query=per_query,
            failures=failures,
            overlay_applied_count=overlay_count,
            overlay_warnings=list(data["overlay_warnings"]) if "overlay_warnings" in data else None,
            broad_eval_metrics=data.get("broad_eval_metrics"),
            recall_gaps=list(data.get("recall_gaps", [])),
            summary_lines=list(data.get("summary_lines", [])),
            semantic_report=semantic_report,
        )

        # Unknown top-level keys
        extra = {k: v for k, v in data.items() if k not in _TOP_LEVEL_KNOWN_KEYS}

        return cls(
            config=config,
            metadata=metadata,
            results=results,
            baseline_meta=baseline_meta if isinstance(baseline_meta, dict) else None,
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}

        # Baseline wrapper
        if self.metadata.run_id is not None:
            d["baseline_id"] = self.metadata.run_id
        if self.baseline_meta is not None:
            d["meta"] = self.baseline_meta

        # Config fields
        d["judge_mode"] = self.config.judge_mode
        d["semantic_enabled"] = self.config.semantic_enabled
        d["live_mode"] = self.config.live_mode

        # Metadata fields
        d["timestamp"] = self.metadata.timestamp
        d["frozen_at"] = self.metadata.frozen_at
        d["anchor_date"] = self.metadata.anchor_date
        d["commit"] = self.metadata.commit
        d["python_version"] = self.metadata.python_version
        d["tokenizer_version"] = self.metadata.tokenizer_version

        # Results fields
        d["total_queries"] = self.results.total_queries
        d["skipped_queries"] = self.results.skipped_queries
        d["metrics"] = self.results.metrics
        d["by_category"] = {cat: m.to_dict() for cat, m in self.results.by_category.items()}
        d["per_query"] = [pq.to_dict() for pq in self.results.per_query]
        d["failures"] = [f.to_dict() for f in self.results.failures]
        d["recall_gaps"] = self.results.recall_gaps
        d["summary_lines"] = self.results.summary_lines
        if self.results.overlay_applied_count is not None:
            d["overlay_applied_count"] = self.results.overlay_applied_count
        if self.results.overlay_warnings is not None:
            d["overlay_warnings"] = self.results.overlay_warnings
        if self.results.broad_eval_metrics is not None:
            d["broad_eval_metrics"] = self.results.broad_eval_metrics
        if self.results.semantic_report is not None:
            d["semantic_report"] = self.results.semantic_report.to_dict()

        # Forward-compatible unknown fields
        d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# QuerySpec: typed golden query specification
# ---------------------------------------------------------------------------

_QUERY_SPEC_EXPECTED_KNOWN_KEYS = frozenset({"min_results", "must_contain_title"})


@dataclass
class QuerySpec:
    """Typed representation of a golden query specification.

    Wraps the untyped dict from golden_queries.yaml (or post-overlay dict)
    with typed fields. Supports forward-compatible round-trip via extra dicts.

    ``overlay_applied`` is metadata computed at construction time (from
    ``applied_query_ids`` or the presence of ``_public_query``); it is NOT
    serialized by ``to_dict()``.
    """

    query_id: str
    query: str
    category: str
    description: str
    tags: list[str]
    expected_min_results: int
    expected_must_contain_title: list[str]
    skip_until_phase: int | None = None
    audit_note: str | list[str] | None = None
    broad_eval: dict[str, Any] | None = None
    public_query: str | None = None
    overlay_applied: bool = False
    extra: dict[str, Any] = field(default_factory=dict, repr=False)
    _had_must_contain_title: bool = field(default=False, repr=False)
    _expected_extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset(
        {
            "id",
            "query",
            "category",
            "description",
            "expected",
            "tags",
            "skip_until_phase",
            "audit_note",
            "broad_eval",
            "_public_query",
        }
    )

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *, applied_query_ids: set[str] | None = None
    ) -> QuerySpec:
        expected = data.get("expected", {})
        if not isinstance(expected, dict):
            expected = {}

        had_mct = "must_contain_title" in expected
        must_contain = expected.get("must_contain_title", [])
        if not isinstance(must_contain, list):
            must_contain = [str(must_contain)] if must_contain else []

        qid = str(data.get("id", ""))
        public_query = data.get("_public_query")

        if applied_query_ids is not None:
            overlay_applied = qid in applied_query_ids
        else:
            overlay_applied = public_query is not None

        expected_extra = {
            k: v for k, v in expected.items() if k not in _QUERY_SPEC_EXPECTED_KNOWN_KEYS
        }
        extra = {k: v for k, v in data.items() if k not in cls._KNOWN_KEYS}

        return cls(
            query_id=qid,
            query=str(data.get("query", "")),
            category=str(data.get("category", "")),
            description=str(data.get("description", "")),
            tags=list(data.get("tags", [])),
            expected_min_results=int(expected.get("min_results", 0)),
            expected_must_contain_title=[str(t) for t in must_contain],
            skip_until_phase=data.get("skip_until_phase"),
            audit_note=data.get("audit_note"),
            broad_eval=data.get("broad_eval"),
            public_query=public_query,
            overlay_applied=overlay_applied,
            extra=extra,
            _had_must_contain_title=had_mct,
            _expected_extra=expected_extra,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.query_id,
            "query": self.query,
            "category": self.category,
            "description": self.description,
            "expected": {"min_results": self.expected_min_results},
            "tags": self.tags,
        }

        if self._had_must_contain_title or self.expected_must_contain_title:
            d["expected"]["must_contain_title"] = self.expected_must_contain_title

        if self._expected_extra:
            d["expected"].update(self._expected_extra)

        if self.skip_until_phase is not None:
            d["skip_until_phase"] = self.skip_until_phase

        if self.audit_note is not None:
            d["audit_note"] = self.audit_note

        if self.broad_eval is not None:
            d["broad_eval"] = self.broad_eval

        if self.public_query is not None:
            d["_public_query"] = self.public_query

        d.update(self.extra)
        return d
