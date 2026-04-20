# ADR-005: Confidence Rules for Search Rejection

> **Status**: Accepted
> **Date**: 2026-04-17
> **Context**: Round 10 Phase 2, Task 2.3

## Decision

Add deterministic confidence labels to every merged search result:

- `high`
- `medium`
- `low`

Also add a top-level boolean flag:

- `no_confident_match`

This flag is `True` when the result set is empty or every result is only `low`/`none` confidence.

## Context

Round 10 requires a reliable "I don't know" capability. The search stack already returns ranked results, but rank alone is not enough for Agent decision-making:

- weak semantic neighbors can still appear in a non-empty result set
- low-score fallback results should not be mistaken for trustworthy recall
- downstream Agents need a deterministic signal for when to reject or hedge

The solution must be absolute, reproducible, and free of model-side randomness.

## Rules

Inputs per result:

- `fts_score`: keyword/BM25 score on 0-100 scale
- `semantic_score`: cosine similarity on 0-100 scale
- `rrf_score`: hybrid fusion score (typically ~0.01-0.05)
- `title_promoted`: whether title/metadata promotion was applied

Classification rules:

| Level | Rule |
|------|------|
| `high` | `(fts_score >= 70 AND semantic_score >= 55) OR rrf_score >= 0.018 OR title_promoted` |
| `medium` | `fts_score >= 50 OR semantic_score >= 45 OR rrf_score >= 0.010` |
| `low` | passed retrieval thresholds but does not meet `medium` |

Top-level rule:

```python
no_confident_match = len(merged_results) == 0 or all(
    r.get("confidence") in {"low", "none"} for r in merged_results
)
```

## Implementation Notes

- `tools/search_journals/confidence.py` is the SSOT for confidence logic
- hybrid ranking now emits `confidence` on every merged result
- non-hybrid ranking also emits `confidence` for consistency
- hybrid results keep both:
  - `relevance_score`: exposed RRF score for fused items
  - internal absolute fallback score for thresholding/backfill

## Consequences

- Agents can safely say "I don't know" when `no_confident_match=True`
- search responses expose confidence in a deterministic, inspectable way
- rejection behavior is regression-tested via `tests/golden_rejection_queries.yaml`
- future threshold tuning can change retrieval floors without redefining the confidence contract
