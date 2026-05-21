"""IR metrics for ablation evaluation: P@k, R@k, MRR@k."""

from __future__ import annotations

from typing import Any


def precision_at_k(results: list[dict[str, Any]], relevant_ids: set[str], k: int = 5) -> float:
    """Compute Precision@k: fraction of top-k results that are relevant.

    Args:
        results: Search result dicts, each with 'path' or 'journal_route_path'.
        relevant_ids: Set of document IDs (filenames like "life-index_2026-03-04_002.md").
        k: Number of top results to consider.

    Returns:
        Precision score in [0.0, 1.0].
    """
    if k <= 0 or not results:
        return 0.0
    top_k = results[:k]
    retrieved_relevant = sum(1 for r in top_k if _extract_doc_id(r) in relevant_ids)
    return retrieved_relevant / k


def recall_at_k(results: list[dict[str, Any]], relevant_ids: set[str], k: int = 5) -> float:
    """Compute Recall@k: fraction of relevant docs retrieved in top-k.

    Args:
        results: Search result dicts, each with 'path' or 'journal_route_path'.
        relevant_ids: Set of document IDs (filenames).
        k: Number of top results to consider.

    Returns:
        Recall score in [0.0, 1.0].
    """
    if k <= 0 or not results or not relevant_ids:
        return 0.0
    top_k = results[:k]
    retrieved_relevant = sum(1 for r in top_k if _extract_doc_id(r) in relevant_ids)
    return retrieved_relevant / len(relevant_ids)


def mrr_at_k(results: list[dict[str, Any]], relevant_ids: set[str], k: int = 5) -> float:
    """Compute Mean Reciprocal Rank@k: 1 / rank of first relevant result.

    Args:
        results: Search result dicts, each with 'path' or 'journal_route_path'.
        relevant_ids: Set of document IDs (filenames).
        k: Number of top results to consider.

    Returns:
        MRR score in [0.0, 1.0]. 0.0 if no relevant result in top-k.
    """
    if k <= 0 or not results or not relevant_ids:
        return 0.0
    top_k = results[:k]
    for idx, result in enumerate(top_k, start=1):
        if _extract_doc_id(result) in relevant_ids:
            return 1.0 / idx
    return 0.0


def _extract_doc_id(result: dict[str, Any]) -> str:
    """Extract a document identifier from a search result.

    Uses journal_route_path first, then path, then strips to filename.
    """
    route = result.get("journal_route_path", "")
    if route:
        return _filename_from_path(str(route))
    path = result.get("path", "")
    if path:
        return _filename_from_path(str(path))
    return ""


def _filename_from_path(path: str) -> str:
    """Extract the filename from a path like 'Journals/2026/03/life-index_2026-03-04_002.md'."""
    normalized = path.replace("\\", "/")
    return normalized.rsplit("/", 1)[-1]
