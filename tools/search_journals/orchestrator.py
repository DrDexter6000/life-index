#!/usr/bin/env python3
"""Deterministic smart-search orchestration over keyword and entity retrieval.

Host agents and Skills own planning, filtering, interpretation, and synthesis.
This module only builds a bounded, provider-free evidence scaffold.
"""

from __future__ import annotations

import calendar
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, TypedDict

from ..lib.search_constants import ORCHESTRATOR_MAX_CANDIDATES
from ..lib.planner_types import (
    QueryPlan,
    StageRecord,
    build_planner_record_from_stages,
    merge_planner_into_search_plan,
)

_MAX_SMART_SEARCH_SUB_QUERIES = 3
_MAX_SMART_SEARCH_SUB_QUERY_LENGTH = 120

_search_fn = None
logger = logging.getLogger(__name__)


def _get_search_fn() -> Any:
    """Lazy-load hierarchical_search to allow focused test substitution."""
    global _search_fn
    if _search_fn is None:
        from .core import hierarchical_search

        _search_fn = hierarchical_search
    return _search_fn


@dataclass
class SmartSearchResult:
    """Structured output for the smart-search command."""

    success: bool = True
    query: str = ""
    rewritten_query: str = ""
    filtered_results: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    citations: list[str] = field(default_factory=list)
    agent_decisions: list[dict[str, Any]] = field(default_factory=list)
    agent_unavailable: bool = True
    performance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "query": self.query,
            "rewritten_query": self.rewritten_query,
            "filtered_results": self.filtered_results,
            "summary": self.summary,
            "citations": self.citations,
            "agent_decisions": self.agent_decisions,
            "agent_unavailable": self.agent_unavailable,
            "performance": self.performance,
        }


class _RewrittenPlan(TypedDict, total=False):
    core_terms: str
    expanded_terms: list[str]
    time_range: Any
    intent_type: str
    rewritten_query: str
    sub_queries: list[str]
    semantic_fallback_query: str | None
    search_plan: dict[str, Any]


class _SearchExecution(TypedDict):
    raw_results: dict[str, Any]
    candidates: list[dict[str, Any]]
    total_available: int
    sub_queries: list[str]
    strategy: str
    semantic_fallback_used: bool
    semantic_fallback_query: str | None


@dataclass(frozen=True)
class _EvidenceBuild:
    data: dict[str, Any] | None = None
    elapsed_ms: float = 0.0
    error: str | None = None


def _build_agent_instructions(mode: str) -> dict[str, Any]:
    """Build deterministic instructions for the calling host agent."""
    return {
        "schema_version": "smart_search.agent_instructions.v1",
        "role": "calling_agent",
        "mode": mode,
        "steps": [
            "Use filtered_results as bounded evidence; do not cite outside returned results.",
            "If filtered_results is empty, say that this search did not find enough evidence.",
            "Prefer concise synthesis with file/date citations from returned results.",
            (
                "For broader interpretation, run another explicit smart-search query "
                "rather than inventing evidence."
            ),
        ],
    }


def _build_answer_scaffold(query: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build provider-free response guidance for host-agent consumers."""
    return {
        "schema_version": "smart_search.answer_scaffold.v1",
        "query": query,
        "citation_policy": "cite_only_returned_results",
        "result_count": len(results),
        "suggested_response_shape": {
            "summary": "brief evidence-backed answer",
            "citations": "file/date references from filtered_results",
            "limitations": "explicitly name missing evidence or low recall",
        },
    }


def _result_identity(item: dict[str, Any]) -> str:
    """Return a stable deduplication key for search candidates."""
    for key in ("rel_path", "path", "title"):
        value = item.get(key)
        if value:
            return str(value)
    return ""


class SmartSearchOrchestrator:
    """Build a deterministic smart-search scaffold."""

    @staticmethod
    def _bounded_unique_strings(values: list[str]) -> list[str]:
        """Return bounded, de-duplicated non-empty strings preserving order."""
        normalized: list[str] = []
        for item in values:
            value = item.strip()
            if not value or value in normalized:
                continue
            normalized.append(value[:_MAX_SMART_SEARCH_SUB_QUERY_LENGTH])
            if len(normalized) >= _MAX_SMART_SEARCH_SUB_QUERIES:
                break
        return normalized

    def _deterministic_rewrite_query(self, query: str) -> _RewrittenPlan:
        """Build the smart-search scaffold from the shared deterministic plan."""
        from .query_preprocessor import build_search_plan

        plan = build_search_plan(query)
        plan_dict = plan.to_dict()
        keywords = [kw for kw in plan.keywords if isinstance(kw, str) and kw.strip()]
        query_mode = plan_dict.get("query_mode")
        base_query = plan.expanded_query or plan.normalized_query or plan.raw_query or query

        if query_mode in {"natural_language", "mixed"} and keywords:
            sub_queries = self._bounded_unique_strings(keywords)
        else:
            sub_queries = self._bounded_unique_strings([base_query])
        if not sub_queries:
            sub_queries = [query[:_MAX_SMART_SEARCH_SUB_QUERY_LENGTH]]

        return {
            "core_terms": " ".join(keywords) if keywords else base_query,
            "expanded_terms": [],
            "time_range": plan_dict.get("date_range"),
            "intent_type": plan_dict.get("intent_type", "unknown"),
            "rewritten_query": base_query,
            "sub_queries": sub_queries,
            "semantic_fallback_query": None,
            "search_plan": plan_dict,
        }

    def rewrite_query(self, query: str) -> _RewrittenPlan:
        """Build a deterministic structured query plan."""
        return self._deterministic_rewrite_query(query)

    def _normalize_sub_queries(self, rewritten: _RewrittenPlan) -> list[str]:
        """Clamp deterministic query decomposition to a bounded list."""
        base_query = str(
            rewritten.get("rewritten_query") or rewritten.get("core_terms") or ""
        ).strip()
        raw = rewritten.get("sub_queries")
        if not isinstance(raw, list) or not raw:
            raw = [base_query]
        normalized = self._bounded_unique_strings([item for item in raw if isinstance(item, str)])
        return normalized or [base_query[:_MAX_SMART_SEARCH_SUB_QUERY_LENGTH]]

    @staticmethod
    def _coerce_iso_date(value: Any) -> str | None:
        """Accept only exact ISO calendar dates."""
        if not isinstance(value, str):
            return None
        candidate = value.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            return candidate
        return None

    @classmethod
    def _resolve_time_range(cls, rewritten: _RewrittenPlan) -> dict[str, str]:
        """Map deterministic time-range metadata to search date filters."""
        raw = rewritten.get("time_range")
        if raw is None:
            return {}
        if isinstance(raw, dict):
            date_from = (
                cls._coerce_iso_date(raw.get("date_from"))
                or cls._coerce_iso_date(raw.get("since"))
                or cls._coerce_iso_date(raw.get("start"))
            )
            date_to = (
                cls._coerce_iso_date(raw.get("date_to"))
                or cls._coerce_iso_date(raw.get("until"))
                or cls._coerce_iso_date(raw.get("end"))
            )
            return {
                key: value
                for key, value in {"date_from": date_from, "date_to": date_to}.items()
                if value
            }
        if not isinstance(raw, str):
            return {}
        value = raw.strip()
        range_match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})", value)
        if range_match:
            return {"date_from": range_match.group(1), "date_to": range_match.group(2)}
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return {"date_from": value, "date_to": value}
        month_match = re.fullmatch(r"(\d{4})-(\d{2})", value)
        if month_match:
            year = int(month_match.group(1))
            month = int(month_match.group(2))
            if 1 <= month <= 12:
                last_day = calendar.monthrange(year, month)[1]
                return {
                    "date_from": f"{year:04d}-{month:02d}-01",
                    "date_to": f"{year:04d}-{month:02d}-{last_day:02d}",
                }
        year_match = re.fullmatch(r"(\d{4})", value)
        if year_match:
            year = int(year_match.group(1))
            return {"date_from": f"{year:04d}-01-01", "date_to": f"{year:04d}-12-31"}
        return {}

    @staticmethod
    def _select_search_strategy(
        rewritten: _RewrittenPlan,
        sub_queries: list[str],
        search_kwargs: dict[str, str],
    ) -> str:
        """Select a truthful deterministic QueryPlan strategy label."""
        if len(sub_queries) > 1:
            return "keyword_multi_pass"
        if search_kwargs:
            return "keyword_temporal"
        return "keyword_only"

    def execute_search(self, rewritten: _RewrittenPlan) -> _SearchExecution:
        """Execute bounded search using deterministic primitives."""
        search_fn = _get_search_fn()
        sub_queries = self._normalize_sub_queries(rewritten)
        search_kwargs = self._resolve_time_range(rewritten)
        strategy = self._select_search_strategy(rewritten, sub_queries, search_kwargs)

        if len(sub_queries) == 1:
            result = search_fn(query=sub_queries[0], **search_kwargs)
            merged = result.get("merged_results", [])[:ORCHESTRATOR_MAX_CANDIDATES]
            return {
                "raw_results": result,
                "candidates": merged,
                "total_available": result.get("total_available", len(merged)),
                "sub_queries": sub_queries,
                "strategy": strategy,
                "semantic_fallback_used": False,
                "semantic_fallback_query": None,
            }

        raw_query_results: list[dict[str, Any]] = []
        fused_by_key: dict[str, dict[str, Any]] = {}
        child_incomplete = False
        total_time_ms = 0.0
        warnings: list[str] = []
        for sub_query in sub_queries:
            result = search_fn(query=sub_query, **search_kwargs)
            raw_query_results.append({"query": sub_query, "result": result})
            total_time_ms += float(result.get("performance", {}).get("total_time_ms", 0) or 0)
            warnings.extend(str(warning) for warning in result.get("warnings", []) if warning)
            child_items = result.get("merged_results", [])
            child_reported_total = int(result.get("total_available", len(child_items)) or 0)
            child_failed = result.get("success") is False
            child_incomplete = child_incomplete or bool(result.get("has_more"))
            child_incomplete = child_incomplete or child_reported_total > len(child_items)
            child_incomplete = child_incomplete or child_failed
            if child_failed:
                warnings.append(
                    f"Sub-query {sub_query!r} returned a failure envelope; "
                    "total_available is an observed lower bound."
                )
            for item in child_items:
                key = _result_identity(item)
                if not key:
                    continue
                candidate = dict(item)
                candidate["source_queries"] = [sub_query]
                existing = fused_by_key.get(key)
                if existing is None:
                    fused_by_key[key] = candidate
                    continue
                existing["source_queries"] = sorted(
                    set(existing.get("source_queries", []) + [sub_query])
                )
                existing_score = float(existing.get("rrf_score", 0) or 0)
                candidate_score = float(candidate.get("rrf_score", 0) or 0)
                if candidate_score > existing_score:
                    for field_name in (
                        "title",
                        "date",
                        "abstract",
                        "snippet",
                        "path",
                        "rel_path",
                    ):
                        if candidate.get(field_name):
                            existing[field_name] = candidate[field_name]
                    existing["rrf_score"] = candidate_score

        observed_unique = len(fused_by_key)
        ranked = sorted(
            fused_by_key.values(),
            key=lambda item: float(item.get("rrf_score", 0) or 0),
            reverse=True,
        )
        merged = ranked[:ORCHESTRATOR_MAX_CANDIDATES]
        has_more = observed_unique > ORCHESTRATOR_MAX_CANDIDATES or child_incomplete
        raw_results = {
            "success": True,
            "query_params": {
                "query": rewritten.get("rewritten_query") or " ".join(sub_queries),
                "semantic": False,
            },
            "merged_results": merged,
            "semantic_results": [],
            "total_found": len(merged),
            "total_available": observed_unique,
            "has_more": has_more,
            "no_confident_match": len(merged) == 0,
            "performance": {"total_time_ms": round(total_time_ms, 2)},
            "warnings": warnings,
            "search_plan": rewritten.get("search_plan"),
            "semantic_policy": "deprecated_noop",
            "semantic_effective_policy": "off",
            "semantic_fallback_used": False,
            "semantic_fallback_query": None,
            "multi_query_results": raw_query_results,
        }
        return {
            "raw_results": raw_results,
            "candidates": merged,
            "total_available": observed_unique,
            "sub_queries": sub_queries,
            "strategy": strategy,
            "semantic_fallback_used": False,
            "semantic_fallback_query": None,
        }

    @staticmethod
    def _try_aggregate(query: str) -> dict[str, Any] | None:
        """Return a deterministic aggregate result or fall back to search."""
        from .aggregate_router import try_route_aggregate

        aggregate_route = try_route_aggregate(query)
        if aggregate_route is None:
            return None
        try:
            from tools.aggregate.core import run_aggregate

            return run_aggregate(
                range_str=aggregate_route.range_str,
                unit=aggregate_route.unit,
                predicate=aggregate_route.predicate,
                query=aggregate_route.query,
            )
        except Exception as exc:
            logger.warning("[Orchestrator] Aggregate delegation failed: %s", exc)
            return None

    @staticmethod
    def _build_aggregate_envelope(
        query: str,
        aggregate_result: dict[str, Any],
        start_time: float,
    ) -> dict[str, Any]:
        """Build the stable smart-search envelope for aggregate delegation."""
        result = SmartSearchResult(
            query=query,
            rewritten_query=query,
            performance={
                "total_time_ms": round((time.time() - start_time) * 1000, 2),
                "rewrite_time_ms": 0,
                "filter_time_ms": 0,
                "search_time_ms": 0,
                "total_available": 0,
            },
        ).to_dict()
        result["smart_search_mode"] = "deterministic_aggregate"
        result["agent_instructions"] = _build_agent_instructions(result["smart_search_mode"])
        result["answer_scaffold"] = _build_answer_scaffold(query, [])
        result["query_plan"] = QueryPlan(
            raw_query=query,
            expanded_query=query,
            sub_queries=[query],
            strategy="deterministic_aggregate",
            fallback_decision=False,
        ).to_dict()
        result["aggregate_result"] = aggregate_result
        return result

    @staticmethod
    def _build_evidence(
        query: str,
        rewritten: _RewrittenPlan,
        search_result: _SearchExecution,
    ) -> _EvidenceBuild:
        """Build evidence best-effort without affecting search success."""
        from tools.evidence.adapter import extract_evidence_from_orchestrator

        evidence_started = time.time()
        try:
            evidence_pack = extract_evidence_from_orchestrator(
                search_result["raw_results"],
                smart_result={
                    "rewritten_query": rewritten.get("rewritten_query"),
                    "original_query": query,
                },
            )
            evidence_data = evidence_pack.to_dict()
            rewritten_query = evidence_data.pop("rewritten_query", None)
            if rewritten_query:
                evidence_data.setdefault("query_context", {})["rewritten_query"] = rewritten_query
            return _EvidenceBuild(
                data=evidence_data,
                elapsed_ms=(time.time() - evidence_started) * 1000,
            )
        except Exception as exc:
            logger.warning("[Orchestrator] Evidence build failed: %s", exc)
            return _EvidenceBuild(
                elapsed_ms=(time.time() - evidence_started) * 1000,
                error=str(exc),
            )

    @staticmethod
    def _build_search_envelope(
        query: str,
        rewritten: _RewrittenPlan,
        search_result: _SearchExecution,
        planner_stages: list[StageRecord],
        evidence: _EvidenceBuild,
        *,
        include_evidence: bool,
        start_time: float,
    ) -> dict[str, Any]:
        """Assemble planner provenance, performance, evidence, and stable fields."""
        candidates = search_result["candidates"]
        planner_record = build_planner_record_from_stages(planner_stages)
        evidence_data = evidence.data
        if evidence_data is not None:
            query_context = evidence_data.setdefault("query_context", {})
            existing_plan = query_context.get("search_plan")
            query_context["search_plan"] = merge_planner_into_search_plan(
                existing_plan,
                planner_record,
            )

        result = SmartSearchResult(
            query=query,
            rewritten_query=rewritten.get("rewritten_query", query),
            filtered_results=candidates,
            performance={
                "total_time_ms": round((time.time() - start_time) * 1000, 2),
                "rewrite_time_ms": 0,
                "filter_time_ms": 0,
                "search_time_ms": search_result["raw_results"]
                .get("performance", {})
                .get("total_time_ms", 0),
                "total_available": search_result["total_available"],
            },
        ).to_dict()
        raw_fallback = search_result["raw_results"].get("semantic_fallback_used")
        if raw_fallback is not None:
            result["semantic_fallback_used"] = bool(raw_fallback)
        result["smart_search_mode"] = "deterministic_scaffold"
        result["agent_instructions"] = _build_agent_instructions(result["smart_search_mode"])
        result["answer_scaffold"] = _build_answer_scaffold(query, candidates)
        result["query_plan"] = QueryPlan(
            raw_query=query,
            expanded_query=rewritten.get("rewritten_query"),
            sub_queries=search_result.get("sub_queries", [query]),
            strategy=search_result.get("strategy", "keyword_only"),
            fallback_decision=False,
        ).to_dict()
        if evidence_data is not None:
            result["performance"]["evidence_build_ms"] = round(evidence.elapsed_ms, 2)
            result["evidence_pack"] = evidence_data
        elif include_evidence:
            result["performance"]["evidence_build_ms"] = round(evidence.elapsed_ms, 2)
            result["performance"]["evidence_error"] = evidence.error
        return result

    def search(
        self, query: str, *, include_evidence: bool = False, synthesize: bool = False
    ) -> dict[str, Any]:
        """Execute deterministic smart-search; ``synthesize`` is a compatibility no-op."""
        start_time = time.time()
        aggregate_result = self._try_aggregate(query)
        if aggregate_result is not None:
            return self._build_aggregate_envelope(query, aggregate_result, start_time)

        rewritten = self.rewrite_query(query)
        planner_stages = [
            StageRecord(
                name="rewrite",
                status="success",
                latency_ms=0.0,
                parameters={"deterministic": True},
            )
        ]
        search_started = time.time()
        search_result = self.execute_search(rewritten)
        candidates = search_result["candidates"]
        planner_stages.append(
            StageRecord(
                name="search",
                status="success",
                latency_ms=round((time.time() - search_started) * 1000, 2),
                parameters={
                    "total_available": search_result["total_available"],
                    "candidates_returned": len(candidates),
                },
            )
        )
        evidence = (
            self._build_evidence(query, rewritten, search_result)
            if include_evidence
            else _EvidenceBuild()
        )
        if include_evidence:
            planner_stages.append(
                StageRecord(
                    name="evidence",
                    status="success" if evidence.data is not None else "failed",
                    latency_ms=round(evidence.elapsed_ms, 2),
                )
            )
        planner_stages.append(
            StageRecord(
                name="filter",
                status="success" if candidates else "skipped",
                latency_ms=0.0,
                parameters={"input_candidates": len(candidates)},
            )
        )
        return self._build_search_envelope(
            query,
            rewritten,
            search_result,
            planner_stages,
            evidence,
            include_evidence=include_evidence,
            start_time=start_time,
        )
