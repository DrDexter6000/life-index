---
type: analysis
title: V120 Phase A Stage 2b Meta Issue Log
created: 2026-05-23
tags:
  - life-index
  - v120
  - search-fusion
  - stage2b
related:
  - '[[PHASE_A_A2R1_STAGE2A_REVIEW_2026-05-23]]'
  - '[[PHASE_A_A3_STAGE2B_REVIEW_2026-05-23]]'
---

# V120 Phase A Stage 2b Meta Issue Log

## Verdict

Stage 2b accepts a balanced subset of Stage 2a: 14 queries per category, 56 total. The subset removes placeholder-style `prompt_hash` entries and keeps all categories within the 10-20 query target.

## Category Counts

| Category | Stage 2a accepted | Stage 2b accepted | Main pruning reason |
|---|---:|---:|---|
| C1_keyword_exact | 20 | 14 | Removed placeholder provenance and reduced repeated 03-14 / 04-13 clustering. |
| C2_paraphrase | 20 | 14 | Removed placeholder provenance and reduced finance / review-topic clustering. |
| C3_temporal | 20 | 14 | Removed placeholder provenance and ambiguous English relative-date entries. |
| C4_entity_heavy | 20 | 14 | Reduced exact-keyword / product-name skew while preserving family, work, AI, and geopolitics entities. |

## Bias Review

### Category Balance

All four categories now contain exactly 14 accepted entries. This avoids the previous Stage 2a shape where every category was capped at 20 but C4 and C1 still had more exact-name/entity-heavy surface area than C2/C3.

### Query Shape Bias

- C1 remains intentionally keyword-exact and includes mostly short exact tokens or entity names.
- C2 remains entirely Chinese. This is acceptable for Stage 2b because the accepted English paraphrases in the raw set were not corpus-grounded, but it remains a coverage gap for CTO review.
- C3 now favors absolute dates and Chinese month/date expressions. Ambiguous English relative entries such as `last month` and `weekend` were excluded.
- C4 remains entity-heavy but is pruned to avoid turning the category into a pure product-name exact-match set.

### BM25 / Entity / RRF Skew

- BM25-friendly skew remains expected in C1 but is bounded by equal category counts.
- Entity-heavy skew is intentionally isolated to C4. Stage 2b removed C4 entries that were mainly algorithm/product exact keywords rather than relationship/entity queries.
- RRF-specific skew is not intentionally introduced. The selected fixtures do not depend on hybrid semantic-vs-FTS rank fusion behavior.

### Life Index Realism

The selected queries map to recurring Life Index usage patterns: family memory lookup, project/tool recall, dated review, investment notes, geopolitics notes, and agent/tool work. The weakest realism gap is still C2 language variety: no English paraphrase survived review.

## Issues Carried To CTO Stage 2c

| ID | Issue | Severity | Stage 2b disposition |
|---|---|---|---|
| S2B-01 | C2 has no English paraphrase queries. | Medium | Accept with note; do not replenish again unless CTO requires bilingual coverage. |
| S2B-02 | Several selected queries still target March/April clusters heavily. | Medium | Accept; baseline report should surface per-category metrics rather than hide cluster effects. |
| S2B-03 | C4 still contains exact entity names that BM25 can also match. | Medium | Accept; this is inherent to entity-heavy search, but CTO should check that Phase B does not overfit C4. |
| S2B-04 | Stage 2a accepted entries from original A1 had placeholder-style hashes. | High | Excluded from Stage 2b. |

## Pruned Stage 2a Entries

| Category | Pruned queries |
|---|---|
| C1_keyword_exact | `Kimi`, `CTO 任务`, `OpenClaw`, `vibe coding`, `Claude Opus`, `数据港` |
| C2_paraphrase | `工作压力`, `生活不易`, `算力股票`, `代码审查`, `定期投资`, `前端审美` |
| C3_temporal | `上周六的事`, `三月份`, `3月14号`, `last month`, `weekend`, `春节` |
| C4_entity_heavy | `Master Dexter`, `Kimi 选股`, `OpenClaw 部署`, `团团妈 教育`, `BM25 检索`, `LobsterAI Journal` |
