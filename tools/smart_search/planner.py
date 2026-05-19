#!/usr/bin/env python3
"""Additive Planner Recorder — M06 Option A (CHARTER §1.4, §1.5, §1.9).

Deterministic recorder that captures orchestrator search-stage provenance.
No LLM calls, no dynamic stage selection, no CLI flags, no behavior change.

The planner records *what happened* during a smart-search pipeline execution,
producing a typed, frozen, round-trippable data structure that can be
surfaced in EvidencePack.query_context.search_plan alongside existing
query-preprocessor output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# StageRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageRecord:
    """Record of a single orchestrator stage execution.

    Attributes:
        name: Stage identifier (e.g. "rewrite", "search", "filter",
              "evidence", "synthesis").
        status: Execution outcome — "success", "skipped", or "failed".
        latency_ms: Wall-clock time for this stage in milliseconds.
        parameters: Optional dict of stage-specific parameters that were
                    used (query text, candidate count, etc.).
        extra: Forward-compatible container for unknown fields.
    """

    name: str
    status: str  # "success" | "skipped" | "failed"
    latency_ms: float = 0.0
    parameters: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset({"name", "status", "latency_ms", "parameters"})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageRecord:
        return cls(
            name=str(data.get("name", "")),
            status=str(data.get("status", "success")),
            latency_ms=float(data.get("latency_ms", 0.0)),
            parameters=data.get("parameters"),
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
            "latency_ms": self.latency_ms,
        }
        if self.parameters is not None:
            d["parameters"] = self.parameters
        d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# PlannerRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlannerRecord:
    """Ordered list of orchestrator stage records with version tracking.

    This is the top-level additive provenance structure. It records which
    stages ran, in what order, and with what outcomes — without changing
    any pipeline behavior.

    Attributes:
        planner_version: Schema version for forward-compatibility.
        stages: Ordered list of stage execution records.
        extra: Forward-compatible container for unknown fields.
    """

    planner_version: str = "0.1.0"
    stages: list[StageRecord] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_KEYS = frozenset({"planner_version", "stages"})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlannerRecord:
        stages = [StageRecord.from_dict(s) for s in data.get("stages", [])]
        return cls(
            planner_version=str(data.get("planner_version", "0.1.0")),
            stages=stages,
            extra={k: v for k, v in data.items() if k not in cls._KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "planner_version": self.planner_version,
            "stages": [s.to_dict() for s in self.stages],
        }
        d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# Builder helper
# ---------------------------------------------------------------------------


def build_planner_record_from_stages(
    stage_records: list[StageRecord],
    **extra: Any,
) -> PlannerRecord:
    """Build a PlannerRecord from a list of StageRecord instances.

    Convenience factory used by the orchestrator after pipeline execution.
    """
    return PlannerRecord(
        stages=list(stage_records),
        extra=dict(extra) if extra else {},
    )


def merge_planner_into_search_plan(
    existing_plan: dict[str, Any] | None,
    planner_record: PlannerRecord,
) -> dict[str, Any]:
    """Merge planner provenance into an existing search_plan dict.

    Preserves all existing keys from the query preprocessor's plan.
    Adds ``orchestrator_stages`` and ``planner_version`` keys.
    Returns a new dict (does not mutate existing_plan).

    If existing_plan is None, returns a fresh dict with only planner keys.
    """
    base = dict(existing_plan) if existing_plan else {}
    base["orchestrator_stages"] = [s.to_dict() for s in planner_record.stages]
    base["planner_version"] = planner_record.planner_version
    return base
