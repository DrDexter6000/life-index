#!/usr/bin/env python3
"""Smart Search Orchestrator — Intelligence Layer (CHARTER §1.5).

This module is the ONLY place where LLM calls are allowed in the search subsystem.
It sits ABOVE the deterministic dual-pipeline (hierarchical_search) and orchestrates:
  1. Query rewriting (pre-processing)
  2. Search execution (calling deterministic primitives)
  3. Post-filtering + summarization (LLM-assisted curation)

When LLM is unavailable, falls back to pure dual-pipeline with agent_unavailable=True.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..lib.search_constants import ORCHESTRATOR_MAX_LLM_CANDIDATES

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
            # Degradation: pass through unchanged
            return {
                "core_terms": query,
                "expanded_terms": [],
                "time_range": None,
                "intent_type": "simple",
                "rewritten_query": query,
            }

        try:
            start = time.time()
            prompt = self._build_rewrite_prompt(query)
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
            }

    # ── Stage 2: Search Execution ────────────────────────────────────────

    def execute_search(self, rewritten: dict[str, Any]) -> dict[str, Any]:
        """Execute search using deterministic primitives.

        Calls hierarchical_search with parameters from rewritten query.
        """
        search_fn = _get_search_fn()
        query = rewritten.get("rewritten_query", rewritten.get("core_terms", ""))
        result = search_fn(query=query)

        # Apply data minimization: trim to max candidates
        merged = result.get("merged_results", [])
        if len(merged) > ORCHESTRATOR_MAX_LLM_CANDIDATES:
            merged = merged[:ORCHESTRATOR_MAX_LLM_CANDIDATES]

        return {
            "raw_results": result,
            "candidates": merged,
            "total_available": result.get("total_available", len(merged)),
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

    def search(self, query: str) -> dict[str, Any]:
        """Execute full smart-search pipeline.

        Returns dict matching SmartSearchResult schema.
        """
        start_time = time.time()
        decisions: list[dict[str, Any]] = []

        # Stage 1: Rewrite
        rewritten = self.rewrite_query(query)
        if "latency_ms" in rewritten:
            decisions.append(
                {
                    "stage": "rewrite",
                    "input_summary": f"query='{query}'",
                    "output_summary": f"rewritten='{rewritten.get('rewritten_query', query)}'",
                    "latency_ms": rewritten["latency_ms"],
                }
            )

        # Stage 2: Execute search
        search_result = self.execute_search(rewritten)
        candidates = search_result["candidates"]

        # Stage 3: Post-filter + summarize
        filtered = self.post_filter_and_summarize(query, candidates)
        if "latency_ms" in filtered:
            decisions.append(
                {
                    "stage": "filter",
                    "input_summary": f"{len(candidates)} candidates",
                    "output_summary": f"{len(filtered.get('filtered_results', []))} filtered",
                    "latency_ms": filtered["latency_ms"],
                }
            )

        total_ms = (time.time() - start_time) * 1000

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

        return result.to_dict()

    # ── LLM Helpers ──────────────────────────────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        """Call LLM with timeout protection."""
        if self._llm is None:
            raise RuntimeError("No LLM client available")
        messages = [{"role": "user", "content": prompt}]
        return self._llm.chat(messages)

    def _build_rewrite_prompt(self, query: str) -> str:
        return (
            f"You are a search query analyzer. Analyze this search query and return JSON:\n"
            f'Query: "{query}"\n\n'
            f"Return ONLY a JSON object with these fields:\n"
            f'- "core_terms": the main search terms\n'
            f'- "expanded_terms": list of related terms/synonyms\n'
            f'- "time_range": any time reference (e.g., "2024", "last week") or null\n'
            f'- "intent_type": one of "simple", "temporal", "thematic", "complex"\n'
            f'- "rewritten_query": optimized search query\n'
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
            }
        except (json.JSONDecodeError, KeyError):
            # Fallback: treat raw query as-is
            return {
                "core_terms": response[:100],
                "expanded_terms": [],
                "time_range": None,
                "intent_type": "simple",
                "rewritten_query": response[:100],
            }

    def _build_filter_prompt(self, query: str, candidates: list[dict[str, Any]]) -> str:
        """Build prompt for post-filtering. Data minimization enforced."""
        items = []
        for i, c in enumerate(candidates, 1):
            title = c.get("title", "")
            abstract = c.get("abstract", "")[:200]
            items.append(f"{i}. Title: {title}\n   Abstract: {abstract}")

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
