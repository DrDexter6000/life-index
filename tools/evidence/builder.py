#!/usr/bin/env python3
"""Evidence Pack builder: extracts typed pack from hierarchical_search() output (R2-C MVP).

Pure function — reads existing search result dicts, does not call search,
semantic, LLM, filesystem, or production data. Does not modify input.
"""

from __future__ import annotations

from typing import Any

from tools.evidence.types import (
    DocumentRef,
    EvidenceItem,
    EvidencePack,
    QueryContext,
    ScoreBreakdown,
    SemanticCandidate,
)


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def _determine_provenance(source: str) -> str:
    """Map search source field to provenance tag."""
    if not source or source == "none":
        return "keyword"
    if "semantic" in source and source != "semantic":
        return "hybrid"
    if source == "semantic":
        return "semantic"
    return "keyword"


def _build_document_ref(result: dict[str, Any]) -> DocumentRef:
    """Build DocumentRef from a search result item."""
    raw_path = result.get("path", "")
    doc_id = _normalize_path(str(raw_path)) if raw_path else ""

    metadata = result.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    topic = metadata.get("topic", result.get("topic", []))
    if isinstance(topic, str):
        topic = [topic]

    return DocumentRef(
        doc_id=doc_id,
        title=str(result.get("title", "")),
        date=str(result.get("date", "")),
        path=str(raw_path) if raw_path else None,
        topic=list(topic),
        location=metadata.get("location"),
        metadata={k: v for k, v in metadata.items() if k != "topic" and k != "location"},
    )


def _build_score_breakdown(result: dict[str, Any], rank: int) -> ScoreBreakdown:
    """Build ScoreBreakdown from a search result item."""
    return ScoreBreakdown(
        source=str(result.get("source", "none")),
        rank=rank,
        relevance=float(result.get("relevance", result.get("fts_score", 0.0))),
        similarity=float(result.get("semantic_score", result.get("similarity", 0.0))),
        rrf_score=float(result.get("rrf_score", 0.0)),
        final_score=float(result.get("final_score", 0.0)),
        confidence=str(result.get("confidence", "low")),
    )


def _build_evidence_item(result: dict[str, Any], rank: int) -> EvidenceItem:
    """Build EvidenceItem from a merged_results entry."""
    source = str(result.get("source", "none"))
    metadata = result.get("metadata", {})
    abstract = None
    if isinstance(metadata, dict):
        abstract = metadata.get("abstract") or metadata.get("summary")

    return EvidenceItem(
        document=_build_document_ref(result),
        scores=_build_score_breakdown(result, rank),
        snippet=str(result.get("snippet", "")),
        abstract=abstract,
        explain=result.get("explain"),
        provenance=_determine_provenance(source),
    )


def _build_semantic_candidate(result: dict[str, Any], rank: int) -> SemanticCandidate:
    """Build SemanticCandidate from a semantic_results entry."""
    return SemanticCandidate(
        document=_build_document_ref(result),
        similarity=float(result.get("similarity", 0.0)),
        snippet=str(result.get("snippet", "")),
        rank=rank,
        provenance="semantic",
    )


def build_evidence_pack(search_result: dict[str, Any]) -> EvidencePack:
    """Build EvidencePack from hierarchical_search() output dict.

    Reads:
      - result["merged_results"] -> EvidenceItem list
      - result["semantic_results"] -> SemanticCandidate list (those NOT in merged)
      - result["query_params"]["query"], ["expanded_query"]
      - result["total_available"], ["has_more"], ["no_confident_match"]
      - result["semantic_effective_policy"]
      - result["entity_hints"]
      - result["search_plan"]
      - result["warnings"]
      - result["performance"]

    Does NOT modify search_result. Pure extraction.
    """
    query_params = search_result.get("query_params") or {}
    query = str(query_params.get("query", ""))
    expanded_query = query_params.get("expanded_query")

    # Build items from merged_results
    items = []
    for i, r in enumerate(search_result.get("merged_results", []), start=1):
        rank = int(r.get("search_rank", i))
        items.append(_build_evidence_item(r, rank))

    # Build semantic candidates, excluding those already in merged_results
    merged_ids = {item.document.doc_id for item in items}
    semantic_candidates = []
    for i, r in enumerate(search_result.get("semantic_results", []), start=1):
        raw_path = r.get("path", "")
        normalized = _normalize_path(str(raw_path)) if raw_path else ""
        if normalized not in merged_ids:
            semantic_candidates.append(_build_semantic_candidate(r, i))

    # Build query context
    query_context = QueryContext(
        query=query,
        expanded_query=expanded_query if expanded_query != query else None,
        search_plan=search_result.get("search_plan"),
        entity_hints=list(search_result.get("entity_hints", [])),
        semantic_policy=str(search_result.get("semantic_effective_policy", "off")),
        warnings=list(search_result.get("warnings", [])),
        performance={k: float(v) for k, v in search_result.get("performance", {}).items()},
    )

    return EvidencePack(
        query_context=query_context,
        items=items,
        semantic_candidates=semantic_candidates,
        total_available=int(search_result.get("total_available", len(items))),
        has_more=bool(search_result.get("has_more", False)),
        no_confident_match=bool(search_result.get("no_confident_match", False)),
    )
