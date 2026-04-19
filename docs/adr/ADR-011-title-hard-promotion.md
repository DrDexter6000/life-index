# ADR-011: Title Hard Promotion Post-Rank Multiplier (D12)

**Status**: Accepted
**Date**: 2026-04-17
**Round/Phase**: Round 10 Phase 4 Task 4.4

## Context

Search results with titles that strongly match the query should rank higher than their RRF/lexical score alone would suggest. This is a common IR pattern — title signals are strong relevance indicators. Currently, title matching only contributes via FTS title_match bonus or L2 metadata scoring, but neither creates a decisive post-rank promotion.

## Decision

Apply a **1.5x multiplier** to `final_score` for results whose title covers ≥60% of the query's non-stopword characters. The multiplier is applied **after** confidence classification (D10) and **before** final sort, so confidence labels are never inflated.

### Parameters

| Constant | Value | Rationale |
|---|---|---|
| `TITLE_PROMOTION_MULTIPLIER` | 1.5 | Within D12 bounds (1.3–1.5). Strong enough to reorder, not so strong as to overwhelm. |
| `TITLE_PROMOTION_COVERAGE_THRESHOLD` | 0.60 | 60% non-stopword char coverage — prevents weak matches from being promoted. |
| `TITLE_PROMOTION_MIN_QUERY_CHARS` | 3 | Minimum non-stopword query length — prevents short/generic queries from triggering promotion. |

### Algorithm

1. Extract non-stopword characters from the query
2. Count how many appear in the title (case-insensitive)
3. If coverage ≥ 60% AND query has ≥ 3 non-stopword chars → multiply `final_score` by 1.5
4. Re-sort all results by `final_score` descending

## Consequences

- Title-matching results with medium/low confidence can outrank higher-confidence results, which is correct behavior (title match is a strong signal).
- `relevance_score` (backward-compat alias) is set **before** promotion — it reflects the pre-promotion score. `final_score` reflects post-promotion.
- `title_promoted: true/false` is added to every merged result for transparency.
- No change to confidence rules (D10 frozen from Phase 2).
- Non-hybrid path also receives title promotion (unified in `core.py`).

## Related

- T4.2: Unified `rrf_score`/`final_score`/`relevance_score` fields
- T4.3: `source` field reflecting actual pipeline hits
- D10: Confidence classification rules (frozen)
