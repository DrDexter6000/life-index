# ADR-004: RRF_MIN_SCORE Floor Value Selection

> **Status**: Accepted
> **Date**: 2026-04-17
> **Context**: Round 10 Phase 2, Task 2.0

## Decision

Set `RRF_MIN_SCORE = 0.008` as the RRF fusion floor threshold.

## Context

The RRF (Reciprocal Rank Fusion) threshold filters low-quality results from hybrid search (keyword + semantic). Round 10 PRD decision D1 requires data-driven selection via A/B experiment on three candidates: `{0.005, 0.008, 0.012}`.

The previous value was `0.003` (set in Round 8), which was too permissive for the new hybrid pipeline.

## Experiment

**Methodology**: Each candidate was tested against the 10-journal eval fixture with semantic search enabled (bge-m3 embeddings, hybrid keyword+semantic via RRF fusion). The fixture contains 24 golden queries across 7 categories (chinese_recall, entity_expansion, noise_rejection, english_regression, cross_language, high_frequency).

**Results**:

| candidate | MRR@5 | P@5 | rejection_pass_rate | avg_result_count | failures |
|-----------|-------|-----|---------------------|------------------|----------|
| 0.005 | 0.8947 | 0.3158 | 0% (0/5) | 10.2 | 6 |
| 0.008 | 0.8947 | 0.7342 | 0% (0/5) | 3.0 | 6 |
| 0.012 | 0.8947 | 0.7342 | 0% (0/5) | 3.0 | 6 |

## Analysis

1. **MRR@5 is unchanged** across all candidates (0.8947). High-relevance queries rank #1 regardless of threshold — the top results have RRF scores well above 0.012.

2. **P@5 improves dramatically** from 0.005 to 0.008 (0.3158 -> 0.7342, +132%). The 0.005 threshold admits too many low-relevance results that dilute the top-5 precision.

3. **Average result count drops** from 10.2 to 3.0 at 0.008. With a 10-journal corpus, returning 10 results means nearly every query returns every journal. At 3.0, results are focused and meaningful.

4. **0.008 and 0.012 are identical**. No result has an RRF score between 0.008 and 0.012, so raising the threshold further has no effect.

5. **Rejection pass rate is 0%** for all candidates. This is expected — noise rejection is the responsibility of confidence rules (T2.3), not the RRF floor. The RRF threshold filters weak results from *positive* queries; it cannot distinguish noise queries from legitimate ones.

## Rationale for Selecting 0.008

- 0.005 is too permissive — P@5 of 0.3158 means 2/3 of top-5 results are irrelevant for positive queries
- 0.008 and 0.012 produce identical results, so 0.008 is preferred (lower thresholds preserve more borderline results that may be relevant)
- The 2.4x precision improvement (0.3158 -> 0.7342) justifies the tighter threshold
- The avg result count of 3.0 is within the target window [3, 15] from the TDD selection rules

## Consequences

- `tools/lib/search_constants.py`: `RRF_MIN_SCORE` changes from `0.003` to `0.008`
- The dynamic threshold (`_compute_dynamic_rrf_threshold`) is retained and applies as `max(dynamic, RRF_MIN_SCORE)`
- Phase 4 may revisit this value when adjusting RRF_FTS_WEIGHT / RRF_SEMANTIC_WEIGHT
- 6 eval failures remain (3 are FTS syntax errors in GQ08/GQ17, 3 are semantic noise leaks) — these are addressed in Phase 3 (FTS noise control) and Phase 2 T2.3 (confidence rules)

## Runner Infrastructure Note

The A/B runner (`tests/eval/rrf_ab_runner.py`) initially produced identical results across all candidates because:

1. First run: `use_semantic=False` — RRF threshold only affects hybrid fusion; pure keyword bypasses it entirely
2. Second run: Vector index not built in temp directory — `update_index()` only builds FTS; needed `build_all()` for both FTS + vector
3. Third run: Module reload ordering — `paths.py` (which holds `USER_DATA_DIR`) must be reloaded before all other modules to propagate the temp data directory to vector_index_simple

All three issues were resolved in the final runner version.
