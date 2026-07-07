#!/usr/bin/env python3
"""Evidence Pack builder: extracts typed pack from hierarchical_search() output (R2-C MVP).

Pure function — reads existing search result dicts, does not call search,
semantic, LLM, filesystem, or production data. Does not modify input.
"""

from __future__ import annotations

import os
from typing import Any, Literal, cast

from tools.evidence.types import (
    DocumentRef,
    EntityMatch,
    EvidenceDiagnostics,
    EvidenceItem,
    EvidencePack,
    PipelineComposition,
    QueryContext,
    ScoreBreakdown,
    SemanticCandidate,
)
from tools.lib.entity_runtime import _contains_entity_term


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def _is_absolute_path(path: str) -> bool:
    """Check if a path looks absolute (Windows or POSIX)."""
    return os.path.isabs(path) or (len(path) >= 2 and path[1] == ":")


def _journals_suffix(path: str) -> str:
    """Extract a safe Journals/... suffix from a normalized path."""
    norm = _normalize_path(path)
    journals_prefix = "Journals/"
    start = 0
    while True:
        idx = norm.find(journals_prefix, start)
        if idx < 0:
            return ""
        if idx == 0 or norm[idx - 1] == "/":
            return norm[idx:]
        start = idx + len(journals_prefix)


def _metadata_doc_id(result: dict[str, Any]) -> str:
    """Build a non-path fallback id from safe document metadata."""
    parts = [
        str(result.get("date", "")).strip(),
        str(result.get("title", "")).strip(),
    ]
    fallback = " ".join(part for part in parts if part)
    if not fallback or _is_absolute_path(fallback):
        return "unknown"
    return _normalize_path(fallback).replace("/", "-").replace(":", "-")


def _safe_path(raw_path: str, result: dict[str, Any]) -> str:
    """Return a safe relative path, never an absolute filesystem path.

    Strategy:
      1. If rel_path is present in result, sanitize and prefer it.
      2. If raw_path is relative, use it as-is (after normalization).
      3. If raw_path is absolute, try to extract a Journals/... suffix.
      4. Fall back to empty string (path omitted; doc_id uses metadata).
    """
    rel = result.get("rel_path", "")
    if isinstance(rel, str) and rel:
        normalized_rel = _normalize_path(rel)
        if not _is_absolute_path(normalized_rel):
            return normalized_rel
        suffix = _journals_suffix(normalized_rel)
        if suffix:
            return suffix

    if not raw_path:
        return ""

    normalized_raw = _normalize_path(raw_path)
    if not _is_absolute_path(normalized_raw):
        return normalized_raw

    return _journals_suffix(normalized_raw)


def _determine_provenance(source: str) -> Literal["keyword", "semantic", "hybrid"]:
    """Map search source field to provenance tag."""
    if not source or source == "none":
        return "keyword"
    if "semantic" in source and source != "semantic":
        return "hybrid"
    if source == "semantic":
        return "semantic"
    return "keyword"


def _build_document_ref(result: dict[str, Any]) -> DocumentRef:
    """Build DocumentRef from a search result item.

    Absolute filesystem paths are filtered - only safe relative paths
    are emitted in doc_id and path fields.
    """
    raw_path = result.get("path") or ""
    safe = _safe_path(str(raw_path), result)
    doc_id = safe or _metadata_doc_id(result)

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
        path=safe if safe else None,
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
        confidence=cast(Literal["high", "medium", "low"], str(result.get("confidence", "low"))),
    )


def _build_entity_matches(
    result: dict[str, Any],
    entity_hints: list[dict[str, Any]],
) -> list[EntityMatch]:
    """Build EntityMatch list from entity_hints matched against item fields.

    Checks title, snippet, abstract, and metadata string values for hint
    matched_term/expansion_terms presence. Deterministic — no filesystem,
    search, or LLM calls.
    """
    if not entity_hints:
        return []

    # Collect searchable text from item fields
    title = str(result.get("title", ""))
    snippet = str(result.get("snippet", ""))
    metadata = result.get("metadata", {})
    abstract = None
    if isinstance(metadata, dict):
        abstract = metadata.get("abstract") or metadata.get("summary")
    if not abstract:
        abstract = result.get("abstract")

    # Build a mapping of searchable text sources
    source_texts: dict[str, str] = {
        "title": title,
        "snippet": snippet,
    }
    if abstract:
        source_texts["abstract"] = str(abstract)

    # Flatten metadata string values into searchable text
    metadata_parts: list[str] = []
    if isinstance(metadata, dict):
        for v in metadata.values():
            if isinstance(v, str) and v:
                metadata_parts.append(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and item:
                        metadata_parts.append(item)
    if metadata_parts:
        source_texts["metadata"] = " ".join(metadata_parts)

    matches: list[EntityMatch] = []
    for hint in entity_hints:
        matched_term = hint.get("matched_term", "")
        if not matched_term:
            continue

        # Build candidate terms: matched_term first, then expansion_terms,
        # deduplicated preserving stable order.
        expansion = hint.get("expansion_terms") or []
        candidate_terms: list[str] = []
        for t in [matched_term] + [e for e in expansion if isinstance(e, str) and e]:
            if t not in candidate_terms:
                candidate_terms.append(t)

        # Find which candidate terms actually appear in item text.
        found_terms: list[str] = []
        sources: list[str] = []
        for term in candidate_terms:
            term_found = False
            for source_name, text in source_texts.items():
                if _contains_entity_term(text, term):
                    term_found = True
                    if source_name not in sources:
                        sources.append(source_name)
            if term_found:
                found_terms.append(term)

        if found_terms:
            matches.append(
                EntityMatch(
                    entity_id=str(hint.get("entity_id", "")),
                    primary_name=str(hint.get("primary_name", "")),
                    entity_type=str(hint.get("entity_type", "")),
                    matched_terms=found_terms,
                    match_sources=sorted(set(sources)),
                    query_matched_term=matched_term,
                )
            )

    return matches


def _build_evidence_item(
    result: dict[str, Any],
    rank: int,
    entity_hints: list[dict[str, Any]] | None = None,
) -> EvidenceItem:
    """Build EvidenceItem from a merged_results entry."""
    source = str(result.get("source", "none"))
    metadata = result.get("metadata", {})
    abstract = None
    if isinstance(metadata, dict):
        abstract = metadata.get("abstract") or metadata.get("summary")

    entity_match_hints = entity_hints if entity_hints is not None else []
    return EvidenceItem(
        document=_build_document_ref(result),
        scores=_build_score_breakdown(result, rank),
        snippet=str(result.get("snippet", "")),
        abstract=abstract,
        explain=result.get("explain"),
        provenance=_determine_provenance(source),
        entity_matches=_build_entity_matches(result, entity_match_hints),
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


def _compute_pipeline_composition(items: list[dict[str, Any]]) -> PipelineComposition:
    """Determine primary pipeline from merged_results source fields.

    Values: none, fts, semantic, hybrid.
    Deterministic — no filesystem, search, or LLM calls.
    """
    if not items:
        return PipelineComposition(primary_pipeline="none")

    sources = [str(r.get("source", "none")) for r in items]
    has_fts = any("fts" in s for s in sources)
    has_semantic = any("semantic" in s for s in sources)

    if has_fts and has_semantic:
        return PipelineComposition(primary_pipeline="hybrid")
    if has_fts:
        return PipelineComposition(primary_pipeline="fts")
    if has_semantic:
        return PipelineComposition(primary_pipeline="semantic")
    return PipelineComposition(primary_pipeline="none")


def compute_diagnostics(search_result: dict[str, Any]) -> EvidenceDiagnostics:
    """Compute deterministic retrieval diagnostics from search result fields.

    Reads: items count, total_available, no_confident_match, has_more,
    and per-item confidence/score fields.  No LLM, filesystem, or search calls.
    """
    items = search_result.get("merged_results", [])
    total_available = int(search_result.get("total_available", len(items)))
    no_confident_match = bool(search_result.get("no_confident_match", False))

    # Determine per-item confidence distribution
    confidences = [str(r.get("confidence", "low")) for r in items]

    # S1-B: pipeline composition from existing merged_results fields
    pipeline_composition = _compute_pipeline_composition(items)

    # zero_results: no items and no available
    if len(items) == 0 and total_available == 0:
        return EvidenceDiagnostics(
            retrieval_outcome="zero_results",
            outcome_reason="no_matches_found",
            notes=["Query returned zero results from both pipelines."],
            suggestions=[
                "Try broader or fewer search terms.",
                "Check spelling and entity names.",
                "Verify the data directory has indexed journals.",
            ],
            pipeline_composition=pipeline_composition,
        )

    # zero_results edge: no items but total_available > 0 (presentation truncation)
    if len(items) == 0 and total_available > 0:
        return EvidenceDiagnostics(
            retrieval_outcome="zero_results",
            outcome_reason="results_truncated_before_delivery",
            notes=[
                f"total_available={total_available} but merged_results is empty.",
            ],
            suggestions=["Increase --limit to retrieve available results."],
            pipeline_composition=pipeline_composition,
        )

    # no_confident_match flag set by search core
    if no_confident_match:
        has_high = "high" in confidences
        has_medium = "medium" in confidences

        # S1-A: all-low remains no_confident_match
        if not has_high and not has_medium:
            return EvidenceDiagnostics(
                retrieval_outcome="no_confident_match",
                outcome_reason="all_items_low_confidence",
                notes=[
                    f"Results present ({len(items)}) but all have low confidence.",
                    "no_confident_match flag is True.",
                ],
                suggestions=[
                    "Results may not directly address the query intent.",
                    "Consider rephrasing with more specific terms.",
                ],
                pipeline_composition=pipeline_composition,
            )

        # S1-A: semantic-only moderate-confidence → weak_results
        sources = [str(r.get("source", "none")) for r in items]
        has_fts = any("fts" in s for s in sources)
        is_semantic_only = len(items) > 0 and not has_fts
        if is_semantic_only and (has_medium or has_high):
            return EvidenceDiagnostics(
                retrieval_outcome="weak_results",
                outcome_reason="semantic_only_moderate_confidence_no_fts_support",
                notes=[
                    f"Results present ({len(items)}) with medium/high confidence "
                    "from semantic pipeline only.",
                    "no_confident_match flag is True because FTS pipeline provided "
                    "no supporting matches.",
                ],
                suggestions=[
                    "Results are semantically relevant but lack keyword confirmation.",
                    "Consider rephrasing with more specific or common terms.",
                ],
                pipeline_composition=pipeline_composition,
            )

        # Mixed confidence with FTS support → stays no_confident_match
        return EvidenceDiagnostics(
            retrieval_outcome="no_confident_match",
            outcome_reason="search_core_flagged_no_confident",
            notes=[
                f"Results present ({len(items)}) with mixed confidence levels.",
                "no_confident_match flag is True despite some medium/high items.",
            ],
            suggestions=[
                "Top results may not be the best match for the query.",
                "Review semantic_candidates for potentially relevant items.",
            ],
            pipeline_composition=pipeline_composition,
        )

    # weak_results: items exist but no high-confidence, and total fits in one page
    has_high = "high" in confidences
    has_medium = "medium" in confidences
    if not has_high and not has_medium and total_available <= len(items):
        return EvidenceDiagnostics(
            retrieval_outcome="weak_results",
            outcome_reason="all_items_low_confidence_full_recall",
            notes=[
                f"All {len(items)} items have low confidence.",
                "total_available equals item count (full recall, weak quality).",
            ],
            suggestions=[
                "Query may be too vague or match tangential content.",
                "Try adding time range or entity filters.",
            ],
            pipeline_composition=pipeline_composition,
        )

    # ok: at least some high or medium confidence results
    if has_high or has_medium:
        return EvidenceDiagnostics(
            retrieval_outcome="ok",
            outcome_reason="confident_results_present",
            notes=[],
            suggestions=[],
            pipeline_composition=pipeline_composition,
        )

    # Default: low confidence items but possibly more available (under-recall hint)
    notes: list[str] = [f"Results present ({len(items)}) with low confidence."]
    if total_available > len(items):
        notes.append(f"total_available ({total_available}) exceeds returned items ({len(items)}).")
    return EvidenceDiagnostics(
        retrieval_outcome="weak_results",
        outcome_reason="low_confidence_with_potential_under_recall",
        notes=notes,
        suggestions=[
            "Consider increasing result limit to capture more candidates.",
        ],
        pipeline_composition=pipeline_composition,
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
    entity_hints = list(search_result.get("entity_hints", []))

    # Build items from merged_results
    items = []
    for i, r in enumerate(search_result.get("merged_results", []), start=1):
        rank = int(r.get("search_rank", i))
        items.append(_build_evidence_item(r, rank, entity_hints))

    # Build semantic candidates, excluding those already in merged_results
    merged_ids = {item.document.doc_id for item in items}
    semantic_candidates = []
    for i, r in enumerate(search_result.get("semantic_results", []), start=1):
        safe = _safe_path(str(r.get("path") or ""), r)
        doc_id = safe or _metadata_doc_id(r)
        if doc_id not in merged_ids:
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
        diagnostics=compute_diagnostics(search_result),
        schema_version="1.0.0",
    )
