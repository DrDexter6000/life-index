# ADR-007: FTS Title Column Split — Raw + Segmented Dual Storage

**Status**: Accepted
**Date**: 2026-04-17
**Round/Phase**: Round 10 Phase 0 Task 0.2
**Decision**: D13 (PRD §9)

## Context

Round 8 introduced Chinese tokenization (jieba) for FTS5 indexing. The `title` column in the FTS table was stored as segmented text (jieba `mode=index` output with spaces between tokens). This caused two problems:

1. **R11 — Title display corruption**: Search results returned segmented titles (e.g., `"计划 回 重庆 给 小朋友 过 生日"` instead of `"计划回重庆给小朋友过生日"`). Users saw space-injected gibberish.
2. **FTS title matching ambiguity**: The same `title` column was used for both FTS matching and display, making it impossible to tune matching independently from presentation.

## Decision

Split the FTS `title` column into two columns:

| Column | Content | FTS Role |
|--------|---------|----------|
| `title` | Raw original text (UNINDEXED) | Display only |
| `title_segmented` | jieba `mode=index` segmented text | FTS MATCH target |

### Schema Migration

- `FTS_SCHEMA_VERSION` bumped from 1 → 2
- Migration: `DROP TABLE journals` + full rebuild (non-destructive since FTS is a derived index, not the data source)
- `fts_update.py` INSERT writes both columns simultaneously
- `fts_search.py` SELECT reads `title` for display; FTS MATCH targets `title_segmented`
- BM25 weight for `title_segmented` inherits the original `title` weight (1.0)

### Invariant

- `title` must always be the raw original text — never segmented, never modified
- `title_segmented` must always be the jieba `mode=index` segmentation of `title`
- These are synchronized at INSERT time; no runtime transformation

## Consequences

- Search results display clean titles without spaces ✅
- FTS title matching continues to work via segmented column ✅
- Existing `title_match` scoring logic unchanged — only the match source shifted from `title` to `title_segmented`
- Schema version bump triggers automatic full rebuild on next `life-index index` call
- Snippet column index shifted from 2 → 3 (content column offset by new `title_segmented`)

## Related

- T0.1: Windows encoding fix (orthogonal)
- T0.3: Chinese tokenizer integration (Round 8 legacy)
- T4.4: Title hard promotion (uses raw `title` for coverage calculation)
- `tools/lib/search_index.py`: `FTS_SCHEMA_VERSION = 2`
- `tools/lib/chinese_tokenizer.py`: `segment_for_fts(title, mode="index")`
