#!/usr/bin/env python3
"""Internal calibration helper for existing eval runs (M05).

This module is diagnostic-only. It summarizes existing EvalRun data into
a CalibrationReport with per-layer metrics, without changing public CLI/API
behavior, search defaults, golden queries, or eval gate logic.

No public CLI flags. No eval runner edits. No search pipeline imports.

Usage (internal only)::

    from tools.eval.calibrate import gather_calibration
    report = gather_calibration(eval_run, policy_eval_run=other_run)
    serialized = report.to_dict()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.eval.eval_compare import compare_eval_runs
from tools.eval.eval_types import EvalRun

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LayerCalibration:
    """Calibration summary for a single layer."""

    layer_name: str
    present: bool
    metrics: dict[str, float]
    diagnostic_notes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "layer_name": self.layer_name,
            "present": self.present,
            "metrics": self.metrics,
        }
        if self.diagnostic_notes:
            d["diagnostic_notes"] = list(self.diagnostic_notes)
        if self.extra:
            d["extra"] = self.extra
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LayerCalibration:
        return cls(
            layer_name=str(data["layer_name"]),
            present=bool(data["present"]),
            metrics={k: float(v) for k, v in data.get("metrics", {}).items()},
            diagnostic_notes=list(data.get("diagnostic_notes", [])),
            extra=dict(data.get("extra", {})),
        )


@dataclass(frozen=True)
class CalibrationReport:
    """Multi-layer calibration report from EvalRun data."""

    timestamp: str
    anchor_date: str
    commit: str
    layers: dict[str, LayerCalibration]
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "anchor_date": self.anchor_date,
            "commit": self.commit,
            "layers": {name: layer.to_dict() for name, layer in self.layers.items()},
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationReport:
        layers = {
            name: LayerCalibration.from_dict(layer_data)
            for name, layer_data in data.get("layers", {}).items()
        }
        return cls(
            timestamp=str(data.get("timestamp", "")),
            anchor_date=str(data.get("anchor_date", "")),
            commit=str(data.get("commit", "")),
            layers=layers,
            config=dict(data.get("config", {})),
        )


# ---------------------------------------------------------------------------
# Layer extraction helpers
# ---------------------------------------------------------------------------


def _extract_layer0(eval_run: EvalRun) -> LayerCalibration:
    """Layer 0: keyword/default metrics from EvalRun.results.metrics."""
    metrics = dict(eval_run.results.metrics)
    return LayerCalibration(
        layer_name="keyword_default",
        present=True,
        metrics=metrics,
        diagnostic_notes=["Copied from EvalRun.results.metrics"],
    )


def _resolve_expansion_pair(extra: dict[str, Any]) -> tuple[str, str]:
    """Resolve raw/expanded query from any supported diagnostic shape.

    Supported shapes in ``RunResult.extra``:
    - flat: ``raw_query`` + ``expanded_query``
    - nested: ``query_params.raw_query`` + ``query_params.expanded_query``
    - nested: ``search_plan.raw_query`` + ``search_plan.expanded_query``
    """
    # Flat shape
    raw = extra.get("raw_query", "")
    expanded = extra.get("expanded_query", "")
    if raw or expanded:
        return raw, expanded

    # Nested: query_params
    qp = extra.get("query_params")
    if isinstance(qp, dict):
        raw = qp.get("raw_query", "")
        expanded = qp.get("expanded_query", "")
        if raw or expanded:
            return raw, expanded

    # Nested: search_plan
    sp = extra.get("search_plan")
    if isinstance(sp, dict):
        raw = sp.get("raw_query", "")
        expanded = sp.get("expanded_query", "")
        if raw or expanded:
            return raw, expanded

    return "", ""


def _extract_layer1(eval_run: EvalRun) -> LayerCalibration:
    """Layer 1: entity/query expansion diagnostics from RunResult.extra."""
    per_query = eval_run.results.per_query
    expansion_count = 0
    total = len(per_query)

    for rq in per_query:
        raw, expanded = _resolve_expansion_pair(rq.extra)
        if raw and expanded and raw != expanded:
            expansion_count += 1

    expansion_rate = expansion_count / total if total > 0 else 0.0

    return LayerCalibration(
        layer_name="entity_expansion",
        present=True,
        metrics={
            "expansion_applied_count": float(expansion_count),
            "expansion_rate": expansion_rate,
        },
        diagnostic_notes=[f"Entity expansion applied to {expansion_count}/{total} queries"],
    )


def _extract_layer2(eval_run: EvalRun) -> LayerCalibration:
    """Layer 2: semantic report summary when present."""
    sr = eval_run.results.semantic_report
    if sr is None:
        return LayerCalibration(
            layer_name="semantic",
            present=False,
            metrics={},
        )

    metrics: dict[str, float] = {}
    for k, v in sr.metrics.items():
        metrics[k] = float(v)
    metrics["fixed_count"] = float(len(sr.fixed_by_semantic))
    metrics["regressed_count"] = float(len(sr.regressed_by_semantic))

    return LayerCalibration(
        layer_name="semantic",
        present=True,
        metrics=metrics,
        diagnostic_notes=[
            f"Semantic enabled: {sr.enabled}",
            f"Fixed by semantic: {len(sr.fixed_by_semantic)}",
            f"Regressed by semantic: {len(sr.regressed_by_semantic)}",
        ],
    )


def _extract_layer4(eval_run: EvalRun) -> LayerCalibration:
    """Layer 4: companion-route summaries from EvalRun.extra."""
    extra = eval_run.extra
    has_companion = any(
        k in extra for k in ("aggregate_eval", "smart_aggregate_eval", "timeline_eval")
    )

    if not has_companion:
        return LayerCalibration(
            layer_name="companion_routes",
            present=False,
            metrics={},
        )

    metrics: dict[str, float] = {}

    agg = extra.get("aggregate_eval")
    if isinstance(agg, dict):
        metrics["aggregate_total"] = float(agg.get("total_queries", 0))
        metrics["aggregate_passed"] = float(agg.get("passed_queries", 0))

    smart_agg = extra.get("smart_aggregate_eval")
    if isinstance(smart_agg, dict):
        metrics["smart_aggregate_total"] = float(smart_agg.get("total_queries", 0))
        metrics["smart_aggregate_passed"] = float(smart_agg.get("passed_queries", 0))

    timeline = extra.get("timeline_eval")
    if isinstance(timeline, dict):
        metrics["timeline_total"] = float(timeline.get("total_queries", 0))
        metrics["timeline_passed"] = float(timeline.get("passed_queries", 0))

    return LayerCalibration(
        layer_name="companion_routes",
        present=True,
        metrics=metrics,
    )


def _extract_layer5(
    eval_run: EvalRun,
    policy_eval_run: EvalRun | None,
) -> LayerCalibration:
    """Layer 5: policy comparison with a supplied candidate EvalRun."""
    if policy_eval_run is None:
        return LayerCalibration(
            layer_name="policy_comparison",
            present=False,
            metrics={},
        )

    comparison = compare_eval_runs(eval_run, policy_eval_run)

    return LayerCalibration(
        layer_name="policy_comparison",
        present=True,
        metrics={
            "fixed_count": float(len(comparison.fixed_query_ids)),
            "regressed_count": float(len(comparison.regressed_query_ids)),
            "still_failing_count": float(len(comparison.still_failing_ids)),
            "still_passing_count": float(len(comparison.still_passing_ids)),
            "failure_delta": float(comparison.failure_delta),
        },
        diagnostic_notes=[
            f"Baseline commit: {comparison.baseline_commit}",
            f"Policy commit: {comparison.candidate_commit}",
            f"Shared queries: {comparison.total_shared_queries}",
        ],
    )


# ---------------------------------------------------------------------------


def gather_calibration(
    eval_run: EvalRun,
    *,
    semantic_eval_run: EvalRun | None = None,
    policy_eval_run: EvalRun | None = None,
) -> CalibrationReport:
    """Gather a multi-layer calibration report from existing EvalRun data.

    Parameters
    ----------
    eval_run:
        Primary eval run (typically keyword/default).
    semantic_eval_run:
        Optional separate semantic eval run for extended Layer 2 comparison.
        Currently unused but reserved for future expansion.
    policy_eval_run:
        Optional policy eval run for Layer 5 comparison.  When provided,
        ``compare_eval_runs`` is used to classify fixed/regressed queries.

    Returns
    -------
    CalibrationReport
        Summary-only, deterministic report with no query text, titles,
        doc IDs, absolute paths, or raw result titles.
    """
    layers: dict[str, LayerCalibration] = {}

    # Layer 0: keyword/default metrics
    layers["keyword_default"] = _extract_layer0(eval_run)

    # Layer 1: entity/query expansion diagnostics
    layers["entity_expansion"] = _extract_layer1(eval_run)

    # Layer 2: semantic report summary
    layers["semantic"] = _extract_layer2(eval_run)

    # Layer 4: companion-route summaries
    layers["companion_routes"] = _extract_layer4(eval_run)

    # Layer 5: policy comparison
    layers["policy_comparison"] = _extract_layer5(eval_run, policy_eval_run)

    config: dict[str, Any] = {
        "semantic_eval_run_provided": semantic_eval_run is not None,
        "policy_eval_run_provided": policy_eval_run is not None,
    }

    return CalibrationReport(
        timestamp=eval_run.metadata.timestamp,
        anchor_date=eval_run.metadata.anchor_date,
        commit=eval_run.metadata.commit,
        layers=layers,
        config=config,
    )
