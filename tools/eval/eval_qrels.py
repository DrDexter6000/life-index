#!/usr/bin/env python3
"""Qrels builder utility for eval (R2-B3b).

Converts QuerySpec + DocCatalog into standard qrels format:
    {query_id: {doc_id: relevance_grade}}

This module is independent of run_eval.py. It does not change eval behavior.
Integration with run_eval.py is deferred to a later task.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from tools.eval.eval_doc_catalog import DocRecord
from tools.eval.eval_doc_catalog import build_title_to_doc_ids as _build_title_to_doc_ids
from tools.eval.eval_types import QuerySpec

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

Qrels: TypeAlias = dict[str, dict[str, int]]


@dataclass(frozen=True)
class QrelCoverageReport:
    """Classification of how query specs map to qrels coverage."""

    total_queries: int
    resolved: int
    ambiguous: int
    unresolved: int
    negative: int
    min_results_only: int
    broad_eval: int
    broad_eval_with_titles: int
    unresolved_ids: list[str]
    ambiguous_ids: list[str]
    procedural_only_ids: list[str]
    warnings: list[str]


# ---------------------------------------------------------------------------
# Title resolution
# ---------------------------------------------------------------------------


def resolve_title_to_doc_ids(
    title_fragment: str,
    title_map: dict[str, list[str]],
) -> list[str]:
    """Resolve a title fragment to doc_ids via exact match, then substring.

    Matches current run_eval semantics where ``fragment in title`` is used.
    Returns deduplicated, deterministically sorted doc_ids.
    Empty or whitespace-only fragment returns [].
    """
    if not title_fragment or not title_fragment.strip():
        return []

    # Exact match first
    if title_fragment in title_map:
        return sorted(set(title_map[title_fragment]))

    # Substring fallback: fragment in title
    doc_ids: set[str] = set()
    for title, ids in title_map.items():
        if title_fragment in title:
            doc_ids.update(ids)

    return sorted(doc_ids)


# ---------------------------------------------------------------------------
# Qrels builder
# ---------------------------------------------------------------------------


def build_qrels_from_query_specs(
    specs: list[QuerySpec],
    catalog: list[DocRecord],
) -> Qrels:
    """Build qrels from query specs and doc catalog.

    For each QuerySpec:
    - Resolves ``expected_must_contain_title`` entries to doc_ids via catalog
    - Emits relevance grade 1 for every resolved doc_id
    - Negative queries (expected_min_results == 0) get empty inner dict
    - Unresolved titles produce empty inner dict
    - ``expected_min_results`` is NOT stored in qrels
    - ``first_relevant_rank`` is NOT stored in qrels
    - ``broad_eval`` is NOT materialized in qrels in this slice
    - Output contains only query_id/doc_id/int grade, never query or title text
    """
    title_map = _build_title_to_doc_ids(catalog)
    qrels: Qrels = {}

    for spec in specs:
        # Negative queries: no relevant documents
        if spec.expected_min_results == 0 and not spec.expected_must_contain_title:
            qrels[spec.query_id] = {}
            continue

        if not spec.expected_must_contain_title:
            # min_results-only or broad_eval-only: no title-based qrels
            qrels[spec.query_id] = {}
            continue

        doc_ids: set[str] = set()
        for title_fragment in spec.expected_must_contain_title:
            resolved = resolve_title_to_doc_ids(title_fragment, title_map)
            doc_ids.update(resolved)

        qrels[spec.query_id] = {doc_id: 1 for doc_id in sorted(doc_ids)}

    return qrels


# ---------------------------------------------------------------------------
# Coverage classifier
# ---------------------------------------------------------------------------


def classify_qrel_coverage(
    specs: list[QuerySpec],
    catalog: list[DocRecord],
) -> QrelCoverageReport:
    """Classify each query spec by qrel coverage.

    Emits only query IDs and counts - no title strings.

    Classification rules:
    - resolved: every expected title resolves to doc_ids, and no single
      title fragment resolves to more than one doc_id.
    - ambiguous: any single expected title fragment resolves to multiple
      doc_ids (title ambiguity), regardless of how many titles the query has.
    - unresolved: any expected title fragment resolves to zero doc_ids
      (incomplete coverage). Conservative: qrels are not fully reliable.
    - negative: expected_min_results == 0
    - min_results_only: expected_min_results > 0, no expected titles, no broad_eval
    - broad_eval: specs with broad_eval
    - broad_eval_with_titles: broad_eval specs that also have expected titles
    """
    title_map = _build_title_to_doc_ids(catalog)

    resolved = 0
    ambiguous = 0
    unresolved = 0
    negative = 0
    min_results_only = 0
    broad_eval_count = 0
    broad_eval_with_titles_count = 0
    unresolved_ids: list[str] = []
    ambiguous_ids: list[str] = []
    procedural_only_ids: list[str] = []
    warnings: list[str] = []

    for spec in specs:
        qid = spec.query_id
        has_titles = bool(spec.expected_must_contain_title)
        has_broad = spec.broad_eval is not None

        if has_broad:
            broad_eval_count += 1
            if has_titles:
                broad_eval_with_titles_count += 1

        if spec.expected_min_results == 0 and not has_titles:
            negative += 1
            procedural_only_ids.append(qid)
            continue

        if not has_titles:
            min_results_only += 1
            procedural_only_ids.append(qid)
            continue

        # Has titles: classify by per-fragment resolution
        any_unresolved = False
        any_ambiguous = False
        for fragment in spec.expected_must_contain_title:
            resolved_ids = resolve_title_to_doc_ids(fragment, title_map)
            if len(resolved_ids) == 0:
                any_unresolved = True
            elif len(resolved_ids) > 1:
                any_ambiguous = True

        if any_unresolved:
            unresolved += 1
            unresolved_ids.append(qid)
            procedural_only_ids.append(qid)
            warnings.append(f"{qid}: partial title resolution, qrels incomplete")
        elif any_ambiguous:
            ambiguous += 1
            ambiguous_ids.append(qid)
        else:
            resolved += 1

    return QrelCoverageReport(
        total_queries=len(specs),
        resolved=resolved,
        ambiguous=ambiguous,
        unresolved=unresolved,
        negative=negative,
        min_results_only=min_results_only,
        broad_eval=broad_eval_count,
        broad_eval_with_titles=broad_eval_with_titles_count,
        unresolved_ids=unresolved_ids,
        ambiguous_ids=ambiguous_ids,
        procedural_only_ids=procedural_only_ids,
        warnings=warnings,
    )
