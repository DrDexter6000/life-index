# ADR-009: Chinese Stopword List for FTS Query Filtering

> **Status**: Accepted
> **Date**: 2026-04-17
> **Context**: Round 10 Phase 3, Task 3.0 (D8). Need stopword filtering for FTS min-hits calculation.

## Decision

Create `tools/search_journals/stopwords_zh.txt` as a UTF-8 plain-text stopword list with approximately 250 entries.

The file is comment-friendly (`#` prefix), one token per line, and loaded via `tools/search_journals/stopwords.py` with cached singleton semantics.

## Context

Round 10 Phase 3 tightens FTS OR-query behavior to reduce noisy matches. A key requirement is to compute minimum required hits from the count of meaningful query tokens rather than raw token count.

Without stopword filtering, vague and high-frequency function words inflate token counts and distort FTS hit thresholds. This especially affects natural-language Chinese queries, where structural particles, vague time/place terms, and connective filler words contribute little retrieval value.

## Sources

- jieba default Chinese stopword set
- Project-specific high-frequency function words observed in natural-language journal queries
- Minimal English stopword subset for mixed Chinese-English queries

## Update Strategy

The stopword list is static runtime data and must only be changed through an explicit commit with written justification.

No runtime updates, dynamic downloads, or user-data-driven mutation are allowed.

## Audit Rhythm

Review the stopword list when eval rejection pass-rate drops below 90%.

## Consequences

- FTS OR queries can require minimum hits based on non-stopword token count
- Vague natural-language queries produce less noise in the keyword pipeline
- Mixed-language queries get basic English function-word filtering without introducing a separate runtime dependency
- Stopword behavior stays deterministic, reviewable, and easy to audit because the source of truth is a plain text file in the repo
