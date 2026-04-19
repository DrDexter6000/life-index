# ADR-016: Query Preprocessor — Deterministic Query Understanding Layer

**Status**: Accepted
**Date**: 2026-04-18
**Round/Phase**: Round 11 Phase 1–3

## Context

Round 10 terminal review identified that the search tool had no query understanding layer. Agents received raw keyword/semantic results without any signal about what the query *meant* — whether it was a count query, a time-range recall, a broad exploration, or something ambiguous. This forced each Agent integration to re-implement query parsing ad hoc, leading to inconsistent behavior across platforms.

The SKILL.md attempted to compensate with prescriptive prose about how to handle different query types, but prose is untestable, unverifiable, and easily lost when context windows reset.

## Decision

Introduce a **lightweight deterministic query preprocessor** inside the CLI search tool. The preprocessor runs before retrieval and outputs three structured fields:

1. **`search_plan`** (Phase 1): Normalized query, intent classification (`recall`/`count`/`compare`/`summarize`/`unknown`), extracted keywords, parsed time range, topic hints, and pipeline configuration.
2. **`ambiguity`** (Phase 2): Structured signals about query ambiguity (aggregation needs agent judgment, time range interpretation, entity resolution, query too broad).
3. **`hints`** (Phase 2): Invocation-time hints for the caller (≤5, ≤120 chars each), such as "聚合型问题：total_found 不等于最终答案" or "建议缩小时间范围".

### Architecture

```
User Query
    │
    ▼
┌──────────────────────────┐
│ Query Preprocessor       │
│ (deterministic, no LLM)  │
│                          │
│ normalize → tokenize →   │
│ extract_time → classify  │
│ → keywords → topic_hints │
│ → detect_ambiguity →     │
│ build_hints              │
│                          │
│ Output: search_plan +    │
│         ambiguity +      │
│         hints            │
└──────────┬───────────────┘
           │
           ▼
    Existing Retrieval Pipeline
    (keyword ∥ semantic → RRF)
```

### Key Design Constraints

- **No LLM calls**: The preprocessor is entirely deterministic (regex + jieba + rule-based). This ensures fast, reproducible results.
- **No query-specific if/else branches** (PRD D6): Intent classification uses token patterns, not hard-coded query strings.
- **No threshold changes**: RRF/semantic constants remain frozen from Round 10.
- **No modification of search core**: Preprocessor output is attached to results but does not alter retrieval behavior.

## Alternatives Considered

### A. SKILL.md Prose-Only Approach

Continue relying on SKILL.md prose to guide Agent behavior.

**Rejected**: Prose is untestable, platform-specific, and easily lost across context resets. Every Agent integration must re-learn the rules independently.

### B. LLM Query Rewriting

Use an LLM to rewrite/expand queries before retrieval.

**Rejected**: Adds latency (200-500ms), requires model availability, introduces non-determinism. Overkill for the 80% case where simple rules suffice. Could be added later as an optional enhancement.

### C. Agent-Side Preprocessing

Each Agent platform implements its own query understanding.

**Rejected**: Fragments the logic across integrations. Different platforms would produce different results for the same query. The CLI should be the SSOT for query understanding.

## Consequences

### Positive

- **Testable**: 78 unit tests cover preprocessor, ambiguity detector, and hints builder.
- **Reproducible**: Same query always produces same `search_plan`. No model variance.
- **Platform-agnostic**: All Agent integrations (CLI, GUI, Web) get the same structured signals.
- **Contract-driven**: `schema.json` v2.0 and `docs/API.md` define the contract.
- **SKILL.md simplification**: Prose about query handling can be replaced by "read `search_plan`/`ambiguity`/`hints`".

### Limitations

- **Chinese time expressions only**: The time parser handles common Chinese patterns (过去30天, 上个月, 今年) but not arbitrary natural language dates. English time expressions are partially supported.
- **No entity-aware intent**: Intent classification doesn't use entity graph data (only the post-preprocessor entity expansion does).
- **Coverage ceiling**: Rule-based approach handles ~80% of common patterns. Edge cases (e.g., "那年夏天" without a year) fall back to `unknown` intent.

## Related

- `tools/search_journals/query_types.py` — Data contracts (IntentType, QueryMode, etc.)
- `tools/search_journals/query_preprocessor.py` — Core preprocessor logic
- `tools/search_journals/ambiguity_detector.py` — Ambiguity signal detection
- `tools/search_journals/hints_builder.py` — Invocation-time hints generation
- `tools/search_journals/schema.json` v2.0 — JSON Schema contract
- ADR-004: RRF threshold baseline
- ADR-010: RRF weight tuning
- ADR-014: Score dimension mismatch note
