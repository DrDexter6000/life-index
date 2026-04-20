# ADR-006: Semantic Adaptive Threshold

> **Status**: Accepted
> **Date**: 2026-04-17
> **Context**: Round 10 Phase 2, Task 2.2

## Decision

Set the semantic runtime threshold to:

`max(0.40, semantic_baseline_p25 + 0.02)`

The absolute floor remains `0.40`. The adaptive baseline is computed during rebuild and persisted into the SQLite `index_meta` table as `semantic_baseline_p25`.

## Context

The previous `SEMANTIC_MIN_SIMILARITY = 0.15` was too permissive. It allowed weak semantic matches to enter the candidate set and leak noise into hybrid results.

Round 10 Phase 2 requires a stricter guardrail that still adapts as the corpus grows. A fixed threshold alone is brittle: too low for today's corpus, but potentially too high or too low after future embedding/corpus drift.

## Rationale

Round 7 baseline observations showed the random-doc max-cosine P25 sits around `0.34`. Adding a `0.06` safety margin yields `0.40`, which becomes the hard floor.

To keep the threshold adaptive, rebuild now computes the corpus baseline via a pseudo-query procedure:

1. Randomly sample document embeddings
2. For each sampled document, compute cosine similarity against all other docs
3. Record the maximum non-self cosine per sample
4. Persist the P25 of that distribution as `semantic_baseline_p25`

At query time, the effective threshold becomes `max(0.40, baseline_p25 + 0.02)`.

This preserves a conservative minimum today while allowing future corpora with denser semantic neighborhoods to raise the bar automatically.

## Implementation Notes

- `tools/lib/search_constants.py`
  - `SEMANTIC_MIN_SIMILARITY = 0.40`
  - `SEMANTIC_ABSOLUTE_FLOOR = 0.40`
  - `SEMANTIC_BASELINE_OFFSET = 0.02`
- `tools/lib/semantic_baseline.py`
  - Computes rebuild-time `semantic_baseline_p25`
- `tools/build_index/__init__.py`
  - Computes and persists baseline after successful vector build
- `tools/lib/search_index.py`
  - Persists `semantic_baseline_p25` into `index_meta`
- `tools/search_journals/semantic_pipeline.py`
  - Loads baseline from SQLite and computes the effective runtime threshold

## Consequences

- Fewer irrelevant semantic-only matches survive into hybrid ranking
- Old indexes remain backward compatible: if no baseline is stored, runtime falls back to the absolute floor `0.40`
- Future corpus growth can tighten the threshold automatically without another hardcoded recalibration
- Rebuild gains one additional calibration step, but failure to compute the baseline is non-fatal
