# ADR-010: RRF Semantic Weight Tuning (0.4 → 0.6)

**Status**: Accepted
**Date**: 2026-04-17
**Round/Phase**: Round 10 Phase 4 Task 4.1

## Context

In the hybrid RRF fusion, FTS weight is 1.0 and semantic weight was 0.4 (4:1 ratio). Root cause R4 identified that this imbalance causes FTS weak hits to dominate over semantically strong results. For example, the query "想起女儿" (miss my daughter) returned "GitHub Star" (FTS hit on generic text) above "想念尿片侠" (semantically highly relevant).

## Decision

Raise `SEMANTIC_WEIGHT_DEFAULT` from 0.4 to 0.6, changing the FTS:semantic ratio from 1.0:0.4 (5:2) to 1.0:0.6 (5:3).

## Rationale

- A 0.6 weight gives semantic results ~60% of FTS influence per rank position, vs 40% previously.
- This is a conservative change — not equal weighting (1.0:1.0), which would over-index on semantic similarity for short queries.
- The 0.6 value was chosen as the smallest step that measurably improves semantic result ranking without destabilizing FTS-heavy queries.

## Consequences

- Weak semantic-only results (similarity ~0.2) that were previously filtered by `RRF_MIN_SCORE=0.008` may now pass (0.6/61 = 0.00984 > 0.008). These get low confidence labels via D10 rules.
- `test_ranking.py` and `test_search_ranking.py` expectations updated to reflect new weights.
- Rollback window: before Phase 5 completion.

## Impact on Existing Tests

- `test_semantic_results_added`: relevance_score changed from 0.4/61 to 0.6/61
- `test_merge_and_rank_results_hybrid_does_not_force_extra_backfill`: weak semantic results now pass RRF threshold (expected len 1 → 3)
