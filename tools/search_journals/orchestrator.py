#!/usr/bin/env python3
"""Smart Search Orchestrator.

The product smart-search CLI constructs this orchestrator with ``llm_client=None``.
Provider-backed synthesis is retired from default tool paths; host agents and
Skills own planning, filtering, and synthesis.

The injectable client protocol remains for eval/legacy characterization tests,
not as a core tool execution path. With no client, the orchestrator returns a
deterministic scaffold over the dual-pipeline search results.
"""

from __future__ import annotations

import logging
import calendar
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..lib.search_constants import ORCHESTRATOR_MAX_LLM_CANDIDATES

_MAX_ENTITY_HINTS = 5
_MAX_EXPANSION_TERMS_PER_HINT = 3
_MAX_EXPANSION_TERM_LENGTH = 20
_MAX_ENTITY_MATCHES_PER_ITEM = 3
_MAX_MATCHED_TERMS_PER_ENTITY = 3
_MAX_ENTITY_ID_LENGTH = 64
_MAX_ENTITY_TYPE_LENGTH = 32
_MAX_MATCHED_TERM_LENGTH = 40
_MAX_SMART_SEARCH_SUB_QUERIES = 3
_MAX_SMART_SEARCH_SUB_QUERY_LENGTH = 120
_QUERY_TOKEN_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

# Lazy import to avoid circular dependency — but store at module level for mocking
_search_fn = None


def _get_search_fn() -> Any:
    """Lazy-load hierarchical_search to allow mocking in tests."""
    global _search_fn
    if _search_fn is None:
        from .core import hierarchical_search

        _search_fn = hierarchical_search
    return _search_fn


logger = logging.getLogger(__name__)


def _is_absolute_path(path: str) -> bool:
    """Check if a path looks absolute (Windows or POSIX)."""
    import os

    return os.path.isabs(path) or (len(path) >= 2 and path[1] == ":")


# ── LLM Client Protocol ──────────────────────────────────────────────────────


class LLMClient(Protocol):
    """Minimal protocol for LLM interaction. Mock or real implementation."""

    def chat(self, messages: list[dict[str, str]], *, max_tokens: int = 2000) -> str:
        """Send messages and return assistant response text."""
        ...


# ── Output Schema ─────────────────────────────────────────────────────────────


@dataclass
class AgentDecision:
    """Record of a single LLM decision for debugging transparency."""

    stage: str  # "rewrite" | "filter" | "summarize"
    input_summary: str
    output_summary: str
    latency_ms: float


@dataclass
class SmartSearchResult:
    """Structured output for smart-search command."""

    success: bool = True
    query: str = ""
    rewritten_query: str = ""
    filtered_results: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    citations: list[str] = field(default_factory=list)
    agent_decisions: list[dict[str, Any]] = field(default_factory=list)
    agent_unavailable: bool = False
    performance: dict[str, float] = field(default_factory=dict)

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


def _build_agent_instructions(mode: str) -> dict[str, Any]:
    """Build deterministic instructions for the calling L3 agent."""

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
    """Build provider-free response guidance for agent consumers."""

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
    """Return a stable dedupe key for search candidates."""

    for key in ("rel_path", "path", "title"):
        value = item.get(key)
        if value:
            return str(value)
    return ""


# ── Orchestrator ─────────────────────────────────────────────────────────────


class SmartSearchOrchestrator:
    """Three-stage smart search orchestrator.

    Args:
        llm_client: Optional LLM client. If None, operates in degradation mode
                    (pure dual-pipeline, no LLM calls).
    """

    LLM_TIMEOUT_SECONDS = 5.0

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client

    # ── Stage 1: Query Rewriting ──────────────────────────────────────────

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

    def _deterministic_rewrite_query(self, query: str) -> dict[str, Any]:
        """Build the no-LLM smart-search scaffold from the shared search plan.

        This does not infer user meaning. It reuses the deterministic search
        preprocessor's already-extracted keywords so natural-language queries
        are not sent to keyword search only as a single literal sentence.
        """

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

    def _resolve_entity_hints(self, query: str) -> list[dict[str, Any]]:
        """Resolve entity hints from the query using the deterministic entity graph.

        Returns a bounded list of matched-entity dicts with safe fields only.
        """
        try:
            from .core import resolve_query_entities

            hints = resolve_query_entities(query)
            bounded = []
            for h in hints[:_MAX_ENTITY_HINTS]:
                terms = [
                    t[:_MAX_EXPANSION_TERM_LENGTH]
                    for t in h["expansion_terms"][:_MAX_EXPANSION_TERMS_PER_HINT]
                ]
                bounded.append(
                    {
                        "entity_id": h["entity_id"],
                        "primary_name": h.get("primary_name", ""),
                        "entity_type": h["entity_type"],
                        "matched_term": h["matched_term"],
                        "expansion_terms": terms,
                    }
                )
            return bounded
        except Exception as e:
            logger.debug(f"[Orchestrator] Entity hint resolution skipped: {e}")
            return []

    def rewrite_query(self, query: str) -> dict[str, Any]:
        """Rewrite user query into structured intent.

        Returns:
            {
                "core_terms": str,
                "expanded_terms": list[str],
                "time_range": str | None,
                "intent_type": str,  # "simple" | "temporal" | "thematic" | "complex"
                "rewritten_query": str,
            }
        """
        if self._llm is None:
            return self._deterministic_rewrite_query(query)

        try:
            start = time.time()
            entity_hints = self._resolve_entity_hints(query)
            prompt = self._build_rewrite_prompt(query, entity_hints=entity_hints)
            response = self._call_llm(prompt)
            parsed = self._parse_rewrite_response(response)
            parsed["latency_ms"] = (time.time() - start) * 1000
            return parsed
        except Exception as e:
            logger.warning(f"[Orchestrator] Rewrite failed: {e}. Using raw query.")
            return {
                "core_terms": query,
                "expanded_terms": [],
                "time_range": None,
                "intent_type": "simple",
                "rewritten_query": query,
                "sub_queries": [query],
            }

    # ── Stage 2: Search Execution ────────────────────────────────────────

    def _normalize_sub_queries(self, rewritten: dict[str, Any]) -> list[str]:
        """Clamp optional LLM query decomposition to a bounded list."""

        base_query = str(
            rewritten.get("rewritten_query") or rewritten.get("core_terms") or ""
        ).strip()
        raw = rewritten.get("sub_queries")
        if not isinstance(raw, list) or not raw:
            raw = [base_query]

        normalized: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                continue
            value = item.strip()
            if not value:
                continue
            normalized.append(value[:_MAX_SMART_SEARCH_SUB_QUERY_LENGTH])
            if len(normalized) >= _MAX_SMART_SEARCH_SUB_QUERIES:
                break

        expansion_base = normalized[0] if normalized else base_query
        for term in self._normalize_expanded_terms(rewritten):
            if len(normalized) >= _MAX_SMART_SEARCH_SUB_QUERIES:
                break
            candidate = expansion_base if term in expansion_base else f"{expansion_base} {term}"
            candidate = candidate.strip()[:_MAX_SMART_SEARCH_SUB_QUERY_LENGTH]
            if candidate and candidate not in normalized:
                normalized.append(candidate)

        if normalized:
            return normalized

        return [base_query[:_MAX_SMART_SEARCH_SUB_QUERY_LENGTH]]

    @staticmethod
    def _normalize_expanded_terms(rewritten: dict[str, Any]) -> list[str]:
        """Return bounded expansion terms from LLM rewrite output."""

        raw = rewritten.get("expanded_terms")
        if not isinstance(raw, list):
            return []

        terms: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                continue
            value = item.strip()
            if not value or value in terms:
                continue
            terms.append(value[:_MAX_SMART_SEARCH_SUB_QUERY_LENGTH])
            if len(terms) >= _MAX_SMART_SEARCH_SUB_QUERIES - 1:
                break
        return terms

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
    def _resolve_time_range(cls, rewritten: dict[str, Any]) -> dict[str, str]:
        """Map LLM time_range output to deterministic search date filters."""

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
            return {k: v for k, v in {"date_from": date_from, "date_to": date_to}.items() if v}

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

    def _select_search_strategy(
        self,
        rewritten: dict[str, Any],
        sub_queries: list[str],
        search_kwargs: dict[str, str],
    ) -> str:
        """Select a truthful QueryPlan strategy label."""

        if len(sub_queries) > 1:
            return "keyword_multi_pass"
        if search_kwargs:
            return "keyword_temporal"
        if self._llm is None:
            return "keyword_only"
        if rewritten.get("intent_type") == "temporal":
            return "keyword_temporal"
        if self._normalize_expanded_terms(rewritten):
            return "keyword_expanded"
        return "keyword_rewritten"

    def execute_search(self, rewritten: dict[str, Any]) -> dict[str, Any]:
        """Execute search using deterministic primitives.

        Calls hierarchical_search with parameters from rewritten query.
        """
        search_fn = _get_search_fn()
        sub_queries = self._normalize_sub_queries(rewritten)
        search_kwargs = self._resolve_time_range(rewritten)
        strategy = self._select_search_strategy(rewritten, sub_queries, search_kwargs)

        if len(sub_queries) == 1:
            result = search_fn(query=sub_queries[0], **search_kwargs)

            # Apply data minimization: trim to max candidates
            merged = result.get("merged_results", [])
            if len(merged) > ORCHESTRATOR_MAX_LLM_CANDIDATES:
                merged = merged[:ORCHESTRATOR_MAX_LLM_CANDIDATES]

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
        total_available = 0
        total_time_ms = 0.0
        warnings: list[str] = []

        for sub_query in sub_queries:
            result = search_fn(query=sub_query, **search_kwargs)
            raw_query_results.append({"query": sub_query, "result": result})
            total_available += int(result.get("total_available", 0) or 0)
            total_time_ms += float(result.get("performance", {}).get("total_time_ms", 0) or 0)
            warnings.extend(str(w) for w in result.get("warnings", []) if w)

            for item in result.get("merged_results", []):
                key = _result_identity(item)
                if not key:
                    continue
                candidate = dict(item)
                candidate["source_queries"] = [sub_query]
                existing = fused_by_key.get(key)
                if existing is None:
                    fused_by_key[key] = candidate
                    continue

                existing_queries = existing.get("source_queries", [])
                existing["source_queries"] = sorted(set(existing_queries + [sub_query]))
                existing_score = float(existing.get("rrf_score", 0) or 0)
                candidate_score = float(candidate.get("rrf_score", 0) or 0)
                if candidate_score > existing_score:
                    for merge_field in ("title", "date", "abstract", "snippet", "path", "rel_path"):
                        if candidate.get(merge_field):
                            existing[merge_field] = candidate[merge_field]
                    existing["rrf_score"] = candidate_score

        merged = sorted(
            fused_by_key.values(),
            key=lambda item: float(item.get("rrf_score", 0) or 0),
            reverse=True,
        )[:ORCHESTRATOR_MAX_LLM_CANDIDATES]

        raw_results = {
            "success": True,
            "query_params": {
                "query": rewritten.get("rewritten_query") or " ".join(sub_queries),
                "semantic": False,
            },
            "merged_results": merged,
            "semantic_results": [],
            "total_found": len(merged),
            "total_available": total_available,
            "has_more": False,
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
            "total_available": total_available,
            "sub_queries": sub_queries,
            "strategy": strategy,
            "semantic_fallback_used": False,
            "semantic_fallback_query": None,
        }

    # ── Stage 3: Post-Filter + Summarize ─────────────────────────────────

    def post_filter_and_summarize(
        self,
        query: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """LLM reads candidate metadata, filters low-relevance, generates summary.

        Data minimization: only title + abstract + snippet (≤200 chars) sent to LLM.
        """
        if self._llm is None or not candidates:
            # Degradation: return candidates as-is with empty summary
            return {
                "filtered_results": candidates,
                "summary": "",
                "citations": [],
            }

        try:
            start = time.time()
            prompt = self._build_filter_prompt(query, candidates)
            response = self._call_llm(prompt)
            parsed = self._parse_filter_response(response, candidates)
            parsed["latency_ms"] = (time.time() - start) * 1000
            return parsed
        except Exception as e:
            logger.warning(f"[Orchestrator] Post-filter failed: {e}. Returning raw candidates.")
            return {
                "filtered_results": candidates,
                "summary": "",
                "citations": [],
            }

    # ── Main Entry Point ─────────────────────────────────────────────────

    def search(
        self, query: str, *, include_evidence: bool = False, synthesize: bool = False
    ) -> dict[str, Any]:
        """Execute full smart-search pipeline.

        Args:
            query: User's natural language search query.
            include_evidence: If True, include evidence_pack in output.
            synthesize: If True, generate citation-backed answer via LLM.

        Returns dict matching SmartSearchResult schema.
        """
        from .aggregate_router import try_route_aggregate

        from tools.lib.planner_types import (
            QueryPlan,
            StageRecord,
            build_planner_record_from_stages,
            merge_planner_into_search_plan,
        )

        start_time = time.time()
        decisions: list[dict[str, Any]] = []
        planner_stages: list[StageRecord] = []

        aggregate_route = try_route_aggregate(query)
        aggregate_result_dict: dict[str, Any] | None = None
        if aggregate_route is not None:
            try:
                from tools.aggregate.core import run_aggregate

                aggregate_result_dict = run_aggregate(
                    range_str=aggregate_route.range_str,
                    unit=aggregate_route.unit,
                    predicate=aggregate_route.predicate,
                    query=aggregate_route.query,
                )
            except Exception as exc:
                logger.warning(f"[Orchestrator] Aggregate delegation failed: {exc}")
                aggregate_result_dict = None

        if aggregate_result_dict is not None:
            total_ms = (time.time() - start_time) * 1000
            result = SmartSearchResult(
                success=True,
                query=query,
                rewritten_query=query,
                filtered_results=[],
                summary="",
                citations=[],
                agent_decisions=[],
                agent_unavailable=self._llm is None,
                performance={
                    "total_time_ms": round(total_ms, 2),
                    "rewrite_time_ms": 0,
                    "filter_time_ms": 0,
                    "search_time_ms": 0,
                    "total_available": 0,
                },
            )
            result_dict = result.to_dict()
            result_dict["smart_search_mode"] = "deterministic_aggregate"
            result_dict["agent_instructions"] = _build_agent_instructions(
                result_dict["smart_search_mode"]
            )
            result_dict["answer_scaffold"] = _build_answer_scaffold(
                query, result_dict.get("filtered_results", [])
            )
            result_dict["query_plan"] = QueryPlan(
                raw_query=query,
                expanded_query=query,
                sub_queries=[query],
                strategy="deterministic_aggregate",
                fallback_decision=False,
            ).to_dict()
            result_dict["aggregate_result"] = aggregate_result_dict
            return result_dict

        # Stage 1: Rewrite
        rw_start = time.time()
        rewritten = self.rewrite_query(query)
        rw_ms = (time.time() - rw_start) * 1000
        if "latency_ms" in rewritten:
            decisions.append(
                {
                    "stage": "rewrite",
                    "input_summary": f"query='{query}'",
                    "output_summary": f"rewritten='{rewritten.get('rewritten_query', query)}'",
                    "latency_ms": rewritten["latency_ms"],
                }
            )
        planner_stages.append(
            StageRecord(
                name="rewrite",
                status="success",
                latency_ms=round(rw_ms, 2),
                parameters={"llm_used": self._llm is not None},
            )
        )

        # Stage 2: Execute search
        se_start = time.time()
        search_result = self.execute_search(rewritten)
        se_ms = (time.time() - se_start) * 1000
        candidates = search_result["candidates"]
        planner_stages.append(
            StageRecord(
                name="search",
                status="success",
                latency_ms=round(se_ms, 2),
                parameters={
                    "total_available": search_result["total_available"],
                    "candidates_returned": len(candidates),
                },
            )
        )

        # Evidence Pack (built when include_evidence or synthesize; best-effort)
        evidence_dict: dict[str, Any] | None = None
        evidence_context_for_synthesis: list[dict[str, Any]] | None = None
        evidence_ms = 0.0
        evidence_error: str | None = None
        if include_evidence or (synthesize and self._llm is not None):
            from tools.evidence.adapter import extract_evidence_from_orchestrator

            ev_start = time.time()
            try:
                evidence_pack = extract_evidence_from_orchestrator(
                    search_result["raw_results"],
                    smart_result={
                        "rewritten_query": rewritten.get("rewritten_query"),
                        "original_query": query,
                    },
                )
                evidence_ms = (time.time() - ev_start) * 1000
                evidence_dict = evidence_pack.to_dict()
                rewritten_query = evidence_dict.pop("rewritten_query", None)
                if rewritten_query:
                    evidence_dict.setdefault("query_context", {})[
                        "rewritten_query"
                    ] = rewritten_query
                # Build minimized context for synthesis prompt
                evidence_context_for_synthesis = self._evidence_to_synthesis_context(evidence_pack)
            except Exception as exc:
                evidence_ms = (time.time() - ev_start) * 1000
                evidence_error = str(exc)
                logger.warning(f"[Orchestrator] Evidence build failed: {exc}")

            planner_stages.append(
                StageRecord(
                    name="evidence",
                    status="success" if evidence_dict is not None else "failed",
                    latency_ms=round(evidence_ms, 2),
                )
            )

        # Stage 3: Post-filter + summarize
        pf_start = time.time()
        filtered = self.post_filter_and_summarize(query, candidates)
        pf_ms = (time.time() - pf_start) * 1000
        if "latency_ms" in filtered:
            decisions.append(
                {
                    "stage": "filter",
                    "input_summary": f"{len(candidates)} candidates",
                    "output_summary": f"{len(filtered.get('filtered_results', []))} filtered",
                    "latency_ms": filtered["latency_ms"],
                }
            )
        planner_stages.append(
            StageRecord(
                name="filter",
                status="success" if filtered.get("filtered_results") else "skipped",
                latency_ms=round(pf_ms, 2),
                parameters={"input_candidates": len(candidates)},
            )
        )

        total_ms = (time.time() - start_time) * 1000

        # Stage 4: Answer synthesis (opt-in)
        answer_dict: dict[str, Any] | None = None
        if synthesize and self._llm is not None and filtered.get("filtered_results"):
            try:
                ans_start = time.time()
                answer_dict = self.synthesize_answer(
                    query=query,
                    filtered_results=filtered["filtered_results"],
                    summary=filtered.get("summary", ""),
                    evidence_context=evidence_context_for_synthesis,
                )
                if answer_dict is not None:
                    answer_dict["latency_ms"] = (time.time() - ans_start) * 1000
                planner_stages.append(
                    StageRecord(
                        name="synthesis",
                        status="success" if answer_dict is not None else "failed",
                        latency_ms=round((time.time() - ans_start) * 1000, 2),
                    )
                )
            except Exception as exc:
                logger.warning(f"[Orchestrator] Answer synthesis failed: {exc}")
                planner_stages.append(
                    StageRecord(name="synthesis", status="failed", latency_ms=0.0)
                )

        # Build planner record and merge into evidence pack search_plan
        planner_record = build_planner_record_from_stages(planner_stages)
        if evidence_dict is not None:
            existing_sp = evidence_dict.get("query_context", {}).get("search_plan")
            enriched_sp = merge_planner_into_search_plan(existing_sp, planner_record)
            evidence_dict.setdefault("query_context", {})["search_plan"] = enriched_sp

        result = SmartSearchResult(
            success=True,
            query=query,
            rewritten_query=rewritten.get("rewritten_query", query),
            filtered_results=filtered.get("filtered_results", []),
            summary=filtered.get("summary", ""),
            citations=filtered.get("citations", []),
            agent_decisions=decisions,
            agent_unavailable=self._llm is None,
            performance={
                "total_time_ms": round(total_ms, 2),
                "rewrite_time_ms": rewritten.get("latency_ms", 0),
                "filter_time_ms": filtered.get("latency_ms", 0),
                "search_time_ms": search_result["raw_results"]
                .get("performance", {})
                .get("total_time_ms", 0),
                "total_available": search_result["total_available"],
            },
        )

        result_dict = result.to_dict()
        raw_semantic_fallback = search_result["raw_results"].get("semantic_fallback_used")
        if raw_semantic_fallback is not None:
            result_dict["semantic_fallback_used"] = bool(raw_semantic_fallback)
        result_dict["smart_search_mode"] = (
            "deterministic_scaffold" if self._llm is None else "llm_orchestrated"
        )
        result_dict["agent_instructions"] = _build_agent_instructions(
            result_dict["smart_search_mode"]
        )
        result_dict["answer_scaffold"] = _build_answer_scaffold(
            query, result_dict.get("filtered_results", [])
        )
        query_plan = QueryPlan(
            raw_query=query,
            expanded_query=rewritten.get("rewritten_query"),
            sub_queries=search_result.get("sub_queries", [query]),
            strategy=search_result.get("strategy", "keyword_only"),
            fallback_decision=False,
        ).to_dict()
        result_dict["query_plan"] = query_plan
        if answer_dict is not None:
            result_dict["answer"] = {
                "answer_text": answer_dict["answer_text"],
                "citations": answer_dict["citations"],
                "confidence": answer_dict["confidence"],
                "confidence_reason": answer_dict.get("confidence_reason", ""),
                "limitations": answer_dict.get("limitations", []),
                "evidence_summary": answer_dict.get("evidence_summary", ""),
            }
            result_dict["performance"]["synthesis_ms"] = round(answer_dict.get("latency_ms", 0), 2)
        if evidence_dict is not None:
            result_dict["performance"]["evidence_build_ms"] = round(evidence_ms, 2)
            if include_evidence:
                result_dict["evidence_pack"] = evidence_dict
        elif include_evidence:
            result_dict["performance"]["evidence_build_ms"] = round(evidence_ms, 2)
            result_dict["performance"]["evidence_error"] = evidence_error
        return result_dict

    # ── Stage 4: Answer Synthesis ────────────────────────────────────────

    def synthesize_answer(
        self,
        query: str,
        filtered_results: list[dict[str, Any]],
        summary: str,
        evidence_context: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Generate citation-backed answer from filtered results.

        Data minimization: only title, date, abstract (≤200 chars), and
        snippet (≤200 chars) are sent to the LLM.  When evidence_context
        is available, provenance/source/score are also included.  No
        full_content, no raw metadata dict, no absolute paths.

        Trust gate: citations are validated against known paths and
        confidence is calibrated against evidence strength.
        """
        if self._llm is None or not filtered_results:
            return None

        try:
            prompt = self._build_synthesis_prompt(
                query, filtered_results, summary, evidence_context
            )
            response = self._call_llm(prompt)
            parsed = self._parse_synthesis_response(response, filtered_results)
            if parsed is None:
                return None
            gated = self._apply_trust_gate(parsed, filtered_results, evidence_context, query=query)
            transparency = self._compute_transparency(
                gated,
                evidence_context,
                original_citation_count=len(parsed.get("citations", [])),
            )
            gated.update(transparency)
            return gated
        except Exception as e:
            logger.warning(f"[Orchestrator] Answer synthesis failed: {e}")
            return None

    def _build_synthesis_prompt(
        self,
        query: str,
        filtered_results: list[dict[str, Any]],
        summary: str,
        evidence_context: list[dict[str, Any]] | None = None,
    ) -> str:
        """Build synthesis prompt with strict data minimization.

        When evidence_context is available (from EvidencePack), includes
        provenance/source/score per item.  Otherwise falls back to
        filtered_results fields only.
        """
        ev_by_path: dict[str, dict[str, Any]] = {}
        if evidence_context:
            for context_item in evidence_context:
                rp = context_item.get("rel_path", "")
                if rp:
                    ev_by_path[rp] = context_item

        items: list[str] = []
        for i, r in enumerate(filtered_results, 1):
            title = str(r.get("title", ""))
            date = str(r.get("date", ""))
            abstract = str(r.get("abstract", r.get("snippet", "")))[:200]
            line = f"{i}. Title: {title}  Date: {date}\n   Abstract: {abstract}"

            r_path = r.get("rel_path", "") or r.get("path", "")
            ev: dict[str, Any] | None = ev_by_path.get(r_path) if r_path else None
            if evidence_context and ev is None and not r_path and i <= len(evidence_context):
                ev = evidence_context[i - 1]
            if evidence_context and ev is not None:
                extras: list[str] = []
                if ev.get("provenance"):
                    extras.append(f"provenance: {ev['provenance']}")
                if ev.get("source"):
                    extras.append(f"source: {ev['source']}")
                if ev.get("score") is not None:
                    extras.append(f"score: {ev['score']}")
                if ev.get("confidence"):
                    extras.append(f"confidence: {ev['confidence']}")
                if ev.get("entity_matches"):
                    em_parts = []
                    for em in ev["entity_matches"]:
                        terms = ", ".join(em.get("matched_terms", []))
                        entity_id = em["entity_id"]
                        label = em.get("primary_name") or entity_id
                        display = (
                            f"{label}<{entity_id}>" if label and label != entity_id else entity_id
                        )
                        em_parts.append(f"{display}({em['entity_type']})[{terms}]")
                    extras.append(f"entities: {'; '.join(em_parts)}")
                if extras:
                    line += "\n   " + ", ".join(extras)

            items.append(line)

        evidence_text = "\n".join(items)
        summary_line = f"\nSummary of findings: {summary}" if summary else ""
        return (
            f"You are a personal journal assistant. A user searched their life journal "
            f'with the query: "{query}"\n\n'
            f"Here are the relevant journal entries found:\n\n{evidence_text}"
            f"{summary_line}\n\n"
            f"Based ONLY on the evidence above, answer the user's query in natural language.\n"
            f"- Write 2-4 sentences that directly address the query.\n"
            f"- Cite specific entries by their number (e.g., [1], [2]).\n"
            f"- If the evidence is insufficient, say so honestly.\n"
            f"- Rate your confidence: high (multiple strong matches), "
            f"medium (some matches with gaps), or low (weak or indirect matches).\n\n"
            f"Return JSON: {{\n"
            f'  "answer_text": "...",\n'
            f'  "citations": [1, 2, ...],\n'
            f'  "confidence": "high|medium|low"\n'
            f"}}"
        )

    @staticmethod
    def _evidence_to_synthesis_context(
        evidence_pack: Any,
    ) -> list[dict[str, Any]]:
        """Extract safe whitelisted fields from EvidencePack items for synthesis.

        Only includes: title, date, snippet/abstract (capped 200 chars),
        relative doc path, provenance, source, confidence, score, and a
        bounded entity_matches summary when present.
        Excludes: full_content, raw metadata dict, absolute paths, raw
        relationship edges, full graph attributes.
        """
        items: list[dict[str, Any]] = []
        for ev_item in evidence_pack.items:
            doc = ev_item.document
            scores = ev_item.scores
            # Use relative path only; skip absolute paths
            rel_path = doc.path if doc.path and not _is_absolute_path(doc.path) else None
            snippet = ev_item.snippet or ""
            abstract = ev_item.abstract or ""
            text = abstract if len(abstract) >= len(snippet) else snippet
            entry: dict[str, Any] = {
                "title": doc.title,
                "date": doc.date,
                "snippet": text[:200],
                "rel_path": rel_path,
                "provenance": ev_item.provenance,
                "source": scores.source,
                "score": scores.final_score,
                "confidence": scores.confidence,
            }
            if ev_item.entity_matches:
                bounded: list[dict[str, Any]] = []
                for em in ev_item.entity_matches[:_MAX_ENTITY_MATCHES_PER_ITEM]:
                    bounded.append(
                        {
                            "entity_id": em.entity_id[:_MAX_ENTITY_ID_LENGTH],
                            "primary_name": em.primary_name[:_MAX_MATCHED_TERM_LENGTH],
                            "entity_type": em.entity_type[:_MAX_ENTITY_TYPE_LENGTH],
                            "matched_terms": [
                                t[:_MAX_MATCHED_TERM_LENGTH]
                                for t in em.matched_terms[:_MAX_MATCHED_TERMS_PER_ENTITY]
                            ],
                        }
                    )
                entry["entity_matches"] = bounded
            items.append(entry)
        return items

    def _parse_synthesis_response(
        self,
        response: str,
        filtered_results: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Parse LLM synthesis response into structured answer dict."""
        import json

        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None

        answer_text = parsed.get("answer_text", "")
        if not answer_text:
            return None

        # Map numeric citation indices to relative doc paths
        raw_citations = parsed.get("citations", [])
        citation_paths: list[str] = []
        for c in raw_citations:
            if isinstance(c, int) and 0 < c <= len(filtered_results):
                path = filtered_results[c - 1].get("rel_path") or filtered_results[c - 1].get(
                    "path", ""
                )
                # Only include relative paths, never absolute
                if path and not _is_absolute_path(path):
                    citation_paths.append(path)
            elif isinstance(c, str):
                if not _is_absolute_path(c):
                    citation_paths.append(c)

        confidence = parsed.get("confidence", "low")
        if confidence not in ("high", "medium", "low"):
            confidence = "low"

        return {
            "answer_text": answer_text,
            "citations": citation_paths,
            "confidence": confidence,
        }

    @staticmethod
    def _apply_trust_gate(
        parsed: dict[str, Any],
        filtered_results: list[dict[str, Any]],
        evidence_context: list[dict[str, Any]] | None = None,
        *,
        query: str = "",
    ) -> dict[str, Any]:
        """Validate citations against known paths and calibrate confidence.

        Citation validation: only paths present in filtered_results or
        evidence_context are kept.  Absolute paths are already filtered
        upstream.

        Confidence calibration: the LLM's self-assessed confidence is
        capped by evidence strength.  The cap is determined by:
          - no valid citations -> max low
          - cited evidence contains 'high' -> cap high
          - cited evidence contains 'medium' (no high) -> cap medium
          - otherwise -> cap low
        When evidence_context is None, valid filtered-results citations
        serve as weak support (cap medium max).
        """
        # Build set of known valid relative paths from filtered_results only
        known_paths: set[str] = set()
        filtered_paths: set[str] = set()
        for r in filtered_results:
            rel = r.get("rel_path", "")
            p = r.get("path", "")
            if rel and not _is_absolute_path(rel):
                known_paths.add(rel)
                filtered_paths.add(rel)
            elif p and not _is_absolute_path(p):
                known_paths.add(p)
                filtered_paths.add(p)
        # Evidence context paths are only valid when they also appear in
        # filtered_results; paths removed by post-filter must not be accepted
        for ev in evidence_context or []:
            rel = ev.get("rel_path", "")
            if rel and not _is_absolute_path(rel) and rel in filtered_paths:
                known_paths.add(rel)

        evidence_by_path = {
            ev.get("rel_path", ""): ev for ev in evidence_context or [] if ev.get("rel_path")
        }
        filtered_by_path: dict[str, dict[str, Any]] = {}
        for r in filtered_results:
            path = r.get("rel_path", "") or r.get("path", "")
            if path and not _is_absolute_path(path):
                filtered_by_path[path] = r

        valid_citations = []
        for citation in parsed.get("citations", []):
            if citation not in known_paths:
                continue
            evidence_item = evidence_by_path.get(citation, {})
            filtered_item = filtered_by_path.get(citation, {})
            confidence = evidence_item.get("confidence") or filtered_item.get("confidence")
            if confidence == "low" and not SmartSearchOrchestrator._citation_matches_query(
                query, filtered_item, evidence_item
            ):
                continue
            valid_citations.append(citation)

        if not valid_citations:
            confidence_cap = "low"
        elif evidence_context is not None:
            cited_confidences: set[str] = set()
            for vc in valid_citations:
                for ev in evidence_context:
                    if ev.get("rel_path") == vc:
                        conf = ev.get("confidence", "low")
                        if conf in ("high", "medium", "low"):
                            cited_confidences.add(conf)
            if "high" in cited_confidences:
                confidence_cap = "high"
            elif "medium" in cited_confidences:
                confidence_cap = "medium"
            else:
                confidence_cap = "low"
        else:
            confidence_cap = "medium"

        llm_confidence = parsed.get("confidence", "low")
        order = {"low": 0, "medium": 1, "high": 2}
        if order.get(llm_confidence, 0) > order.get(confidence_cap, 0):
            llm_confidence = confidence_cap

        answer_text = parsed["answer_text"]
        if parsed.get("citations") and not valid_citations:
            answer_text = (
                "The retrieved evidence could not be validated into a "
                "citation-backed answer for this query."
            )

        return {
            "answer_text": answer_text,
            "citations": valid_citations,
            "confidence": llm_confidence,
        }

    @staticmethod
    def _compute_transparency(
        gated: dict[str, Any],
        evidence_context: list[dict[str, Any]] | None = None,
        original_citation_count: int = 0,
    ) -> dict[str, Any]:
        """Derive transparency fields from validated trust gate output.

        Fields are computed from validated citations and evidence context.
        The LLM is never allowed to set these fields directly.

        Args:
            gated: Output of _apply_trust_gate (answer_text, citations, confidence).
            evidence_context: Optional evidence context from EvidencePack.
            original_citation_count: Number of citations before trust gate
                validation (used to detect dropped citations).

        Returns:
            Dict with confidence_reason, limitations, evidence_summary.
        """
        valid_citations = gated.get("citations", [])
        confidence = gated.get("confidence", "low")

        # confidence_reason: why this confidence level was assigned
        if not valid_citations:
            confidence_reason = "No validated citations support this answer."
        elif evidence_context is not None:
            cited_strengths: set[str] = set()
            for vc in valid_citations:
                for ev in evidence_context:
                    if ev.get("rel_path") == vc:
                        conf = ev.get("confidence", "low")
                        if conf in ("high", "medium", "low"):
                            cited_strengths.add(conf)
            if "high" in cited_strengths:
                confidence_reason = "Answer supported by high-confidence evidence."
            elif "medium" in cited_strengths:
                confidence_reason = "Answer supported by moderate-confidence evidence."
            else:
                confidence_reason = "Answer supported by low-confidence evidence only."
        else:
            confidence_reason = "Answer supported by retrieved results without evidence pack."

        # limitations: what the answer cannot claim
        limitations: list[str] = []
        if not valid_citations:
            limitations.append("No validated citations support this answer.")
        if original_citation_count > len(valid_citations):
            dropped = original_citation_count - len(valid_citations)
            limitations.append(f"{dropped} citation(s) were dropped as unvalidated.")
        if evidence_context is not None and valid_citations:
            low_count = sum(
                1
                for vc in valid_citations
                for ev in evidence_context
                if ev.get("rel_path") == vc and ev.get("confidence", "low") == "low"
            )
            if low_count > 0:
                limitations.append(f"{low_count} cited source(s) have low evidence confidence.")
        if confidence == "low" and valid_citations:
            limitations.append("Overall confidence is low despite having citations.")

        # evidence_summary: summary of validated evidence per cited source
        evidence_summary = ""
        if valid_citations and evidence_context is not None:
            parts: list[str] = []
            for vc in valid_citations:
                for ev in evidence_context:
                    if ev.get("rel_path") == vc:
                        segments: list[str] = []
                        if ev.get("title"):
                            segments.append(ev["title"])
                        if ev.get("source"):
                            segments.append(f"source: {ev['source']}")
                        if ev.get("confidence"):
                            segments.append(f"confidence: {ev['confidence']}")
                        if segments:
                            parts.append("; ".join(segments))
            evidence_summary = " | ".join(parts)

        return {
            "confidence_reason": confidence_reason,
            "limitations": limitations,
            "evidence_summary": evidence_summary,
        }

    # ── LLM Helpers ──────────────────────────────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        """Call LLM with timeout protection."""
        if self._llm is None:
            raise RuntimeError("No LLM client available")
        messages = [{"role": "user", "content": prompt}]
        return self._llm.chat(messages)

    def _build_rewrite_prompt(
        self,
        query: str,
        *,
        entity_hints: list[dict[str, Any]] | None = None,
    ) -> str:
        entity_block = ""
        if entity_hints:
            lines = []
            for h in entity_hints[:_MAX_ENTITY_HINTS]:
                terms = ", ".join(
                    t[:_MAX_EXPANSION_TERM_LENGTH]
                    for t in h["expansion_terms"][:_MAX_EXPANSION_TERMS_PER_HINT]
                )
                name = h.get("primary_name") or h["entity_id"]
                display = (
                    f"{name} <{h['entity_id']}>"
                    if name and name != h["entity_id"]
                    else h["entity_id"]
                )
                lines.append(
                    f"- matched \"{h['matched_term']}\" -> {display} "
                    f"({h['entity_type']}); also known as: {terms}"
                )
            entity_block = (
                "\n\nLocal entity graph matches for this query:\n"
                + "\n".join(lines)
                + "\nUse these when expanding terms."
            )
        return (
            f"You are a search query analyzer. Analyze this search query and return JSON:\n"
            f'Query: "{query}"\n'
            f"{entity_block}\n"
            f"Return ONLY a JSON object with these fields:\n"
            f'- "core_terms": the main search terms\n'
            f'- "expanded_terms": list of related terms/synonyms\n'
            f'- "time_range": any time reference (e.g., "2024", "last week") or null\n'
            f'- "intent_type": one of "simple", "temporal", "thematic", "complex"\n'
            f'- "rewritten_query": optimized search query\n'
            f'- "sub_queries": up to 3 focused keyword queries for multi-pass search\n'
        )

    def _parse_rewrite_response(self, response: str) -> dict[str, Any]:
        """Parse LLM rewrite response. Returns structured dict."""
        import json

        try:
            # Try to extract JSON from response
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed = json.loads(text)
            return {
                "core_terms": parsed.get("core_terms", ""),
                "expanded_terms": parsed.get("expanded_terms", []),
                "time_range": parsed.get("time_range"),
                "intent_type": parsed.get("intent_type", "simple"),
                "rewritten_query": parsed.get("rewritten_query", ""),
                "sub_queries": parsed.get("sub_queries", []),
            }
        except (json.JSONDecodeError, KeyError):
            # Fallback: treat raw query as-is
            return {
                "core_terms": response[:100],
                "expanded_terms": [],
                "time_range": None,
                "intent_type": "simple",
                "rewritten_query": response[:100],
                "sub_queries": [],
            }

    def _build_filter_prompt(self, query: str, candidates: list[dict[str, Any]]) -> str:
        """Build prompt for post-filtering. Data minimization enforced."""
        items = []
        for i, c in enumerate(candidates, 1):
            metadata = c.get("metadata", {}) if isinstance(c.get("metadata"), dict) else {}
            title = str(c.get("title", ""))[:200]
            date = str(c.get("date", ""))[:40]
            abstract = str(c.get("abstract") or metadata.get("abstract") or "")[:200]
            snippet = str(c.get("snippet", ""))[:200]
            lines = [f"{i}. Title: {title}"]
            if date:
                lines.append(f"   Date: {date}")
            if abstract:
                lines.append(f"   Abstract: {abstract}")
            if snippet and snippet != abstract:
                lines.append(f"   Snippet: {snippet}")

            signals = []
            if c.get("source"):
                signals.append(f"source: {str(c['source'])[:80]}")
            if c.get("confidence"):
                signals.append(f"confidence: {str(c['confidence'])[:20]}")
            score = c.get("final_score", c.get("score", c.get("relevance")))
            if score is not None:
                signals.append(f"score: {score}")
            if signals:
                lines.append(f"   Signals: {', '.join(signals)}")

            entity_matches = c.get("entity_matches") or metadata.get("entity_matches") or []
            if entity_matches:
                entity_parts = []
                for em in entity_matches[:_MAX_ENTITY_MATCHES_PER_ITEM]:
                    entity_id = str(em.get("entity_id", ""))[:_MAX_ENTITY_ID_LENGTH]
                    primary_name = str(em.get("primary_name", ""))[:_MAX_MATCHED_TERM_LENGTH]
                    entity_type = str(em.get("entity_type", ""))[:_MAX_ENTITY_TYPE_LENGTH]
                    matched_terms = [
                        str(t)[:_MAX_MATCHED_TERM_LENGTH]
                        for t in em.get("matched_terms", [])[:_MAX_MATCHED_TERMS_PER_ENTITY]
                    ]
                    if entity_id and entity_type:
                        label = primary_name or entity_id
                        display = (
                            f"{label}<{entity_id}>" if label and label != entity_id else entity_id
                        )
                        entity_parts.append(f"{display}({entity_type})[{', '.join(matched_terms)}]")
                if entity_parts:
                    lines.append(f"   entities: {'; '.join(entity_parts)}")

            items.append("\n".join(lines))

        candidates_text = "\n".join(items)
        return (
            f'You are a search result curator. A user searched for: "{query}"\n\n'
            f"Candidates:\n{candidates_text}\n\n"
            f"Tasks:\n"
            f"1. Filter out results NOT relevant to the query\n"
            f"2. Write a 2-3 sentence summary of the relevant results\n"
            f"3. List citation titles\n\n"
            f"Return JSON: {{"
            f'"filtered_indices": [1,2,...], '
            f'"summary": "...", '
            f'"citations": ["..."]'
            f"}}"
        )

    @staticmethod
    def _citation_matches_query(
        query: str,
        filtered_item: dict[str, Any],
        evidence_item: dict[str, Any],
    ) -> bool:
        query_tokens = SmartSearchOrchestrator._normalized_tokens(query)
        if not query_tokens:
            return True

        text_parts = [
            filtered_item.get("title", ""),
            filtered_item.get("abstract", ""),
            filtered_item.get("snippet", ""),
            evidence_item.get("title", ""),
            evidence_item.get("snippet", ""),
        ]
        metadata = filtered_item.get("metadata", {})
        if isinstance(metadata, dict):
            text_parts.append(metadata.get("abstract", ""))
        entity_matches = (evidence_item.get("entity_matches") or []) + (
            filtered_item.get("entity_matches") or []
        )
        for em in entity_matches:
            text_parts.extend(
                [
                    em.get("entity_id", ""),
                    em.get("entity_type", ""),
                    " ".join(em.get("matched_terms", [])),
                ]
            )

        item_tokens = SmartSearchOrchestrator._normalized_tokens(" ".join(map(str, text_parts)))
        matches = query_tokens & item_tokens
        required_matches = 1 if len(query_tokens) == 1 else 2
        return len(matches) >= required_matches

    @staticmethod
    def _normalized_tokens(text: str) -> set[str]:
        tokens: set[str] = set()
        lowered = text.lower()
        for token in re.findall(r"[a-z0-9]+", lowered):
            if token in _QUERY_TOKEN_STOPWORDS or len(token) < 2:
                continue
            if token.endswith("ies") and len(token) > 4:
                token = token[:-3] + "y"
            elif (
                token.endswith("s")
                and len(token) > 3
                and not token.endswith("is")
                and not token.endswith("us")
                and not token.endswith("sis")
            ):
                token = token[:-1]
            tokens.add(token)
        for match in re.finditer(r"[\u4e00-\u9fff\u3400-\u4dbf]+", lowered):
            segment = match.group(0)
            for i in range(len(segment)):
                tokens.add(segment[i])
        return tokens

    def _parse_filter_response(
        self, response: str, candidates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Parse LLM filter response and apply to candidates."""
        import json

        try:
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed = json.loads(text)

            indices = parsed.get("filtered_indices", [])
            filtered = [candidates[i - 1] for i in indices if 0 < i <= len(candidates)]

            return {
                "filtered_results": filtered if filtered else candidates,
                "summary": parsed.get("summary", ""),
                "citations": parsed.get("citations", []),
            }
        except (json.JSONDecodeError, KeyError, IndexError):
            return {
                "filtered_results": candidates,
                "summary": "",
                "citations": [],
            }
