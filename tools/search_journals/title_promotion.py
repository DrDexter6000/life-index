"""Title hard promotion: post-rank 1.5x multiplier for title-matching results.

D12: Multiplier applied AFTER confidence classification, BEFORE final sort.
Does not change confidence labels — only adjusts final_score for ranking.
"""

from __future__ import annotations

TITLE_PROMOTION_MULTIPLIER: float = 1.5
TITLE_PROMOTION_COVERAGE_THRESHOLD: float = 0.60
TITLE_PROMOTION_MIN_QUERY_CHARS: int = 3


def should_promote(query: str, title: str, stopwords: frozenset[str] | None = None) -> bool:
    """Determine if title should be promoted based on non-stopword character coverage.

    Coverage = |non-stopword query chars found in title| / |non-stopword query chars|
    Promote if coverage ≥ 60% AND query has ≥ 3 non-stopword characters.
    """
    if stopwords is None:
        from .stopwords import load_stopwords

        stopwords = load_stopwords("zh")

    # Get non-stopword characters from query
    non_stop_chars = [c for c in query if c.strip() and c not in stopwords]
    if len(non_stop_chars) < TITLE_PROMOTION_MIN_QUERY_CHARS:
        return False

    # Count how many of those characters appear in the title
    title_lower = title.lower()
    matched = sum(1 for c in non_stop_chars if c.lower() in title_lower)
    coverage = matched / len(non_stop_chars)
    return coverage >= TITLE_PROMOTION_COVERAGE_THRESHOLD


def apply_title_promotion(
    merged_results: list[dict],
    query: str,
) -> list[dict]:
    """Apply title promotion multiplier to qualifying results.

    Modifies final_score by 1.5x for promoted results, then re-sorts.
    Does NOT modify confidence labels (D12 requirement).

    Returns:
        Re-sorted merged_results list.
    """
    for result in merged_results:
        title = str(result.get("title", ""))
        if should_promote(query, title):
            old_score = result.get("final_score", 0)
            result["final_score"] = old_score * TITLE_PROMOTION_MULTIPLIER
            result["title_promoted"] = True
        else:
            result["title_promoted"] = False

    # Re-sort by final_score descending
    merged_results.sort(key=lambda r: float(r.get("final_score", 0)), reverse=True)
    return merged_results
