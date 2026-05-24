# ADR-028: L2 Retrieval Default = Pure Keyword (Recall-First Truthfulness Model)

> **Status**: Accepted
> **Date**: 2026-05-23
> **Context**: v1.2.0 Cycle 2 absorption surfaced 2 long-standing loopholes (semantic noise vs recall trade-off, hard truncation cap). Triggered creation of CHARTER §1.11 via RFC-2026-05-23.
> **Related**: RFC-2026-05-23-l2-recall-first-truthfulness-model, ADR-006 (semantic adaptive threshold), ADR-010 (RRF weight tuning), CHARTER §1.11

---

## Decision

Life Index L2 retrieval default behavior is **pure keyword (BM25 / FTS5) recall-first**. Vector / semantic / hybrid retrieval is preserved as **explicit opt-in only**.

Concretely:

1. **L2 default search path** = keyword tokenize → FTS5 → BM25 ranking → return complete token-match candidate set + `total_matches` count
2. **Truncation** = display layer only (default top-20), explicitly opt-out via `--limit 0` or equivalent
3. **Semantic / vector retrieval** = preserved code; activated only by:
   - User explicit `--semantic` flag
   - L3 agent explicit request
   - Zero-result keyword fallback (existing ADR-006 behavior, retained)
4. **Paraphrase responsibility** = L1 enrichment + L3 agentic query rewrite (not L2)

This decision is now enshrined in **CHARTER §1.11** as an inviolable invariant. Any future proposal to revert L2 default to hybrid must go through CHARTER §5.2 substantive gate.

---

## Context

### The Two Loopholes Surfaced 2026-05-23

**Loophole 1 — Semantic threshold dilemma**

The user (主理人) explicitly recalled (2026-05-23 对话):

> "...semantic搜索一打开就确实能够提高搜索的全面性...但是当时无论如何调试semantic的一个什么取值都无法获得一个两全其美的效果 —— 要么取值太低匹配为零、对双管道搜索结果贡献为零，要么就井喷出一堆噪音..."

Quantified evidence:
- Round 19 Phase 1-D hybrid mode: R@5=0.8387, **P@5=0.4894** (CHARTER.md:423 note)
- ~half of returned hybrid results are noise

Previous decision (by a prior orchestrator agent, not current) was to set semantic default off at production runtime — but this decision was **never formally documented** and the eval gate / production runtime stayed misaligned (eval default keyword-only, production default still hybrid in code per `tools/search_journals/core.py:1026`).

**Loophole 2 — Hard 20-result truncation**

CLI display truncates at 20 results. For a 50-year journal corpus, high-frequency events (e.g. 1000+ entries mentioning a child's name) cannot be fully recalled. This breaks the "不遗漏每一个人生碎片" product promise.

### v1.2.0 cycle2 baseline as forcing evidence

A6 baseline (`.agent-reports/v120-search-fusion-m3/phase-a/A6_baseline_result.json`):
- overall R@5 = 0.6786, MRR@5 = 0.6354
- C1 keyword_exact = 1.0000 (ceiling)
- C2 paraphrase = 0.1429 (12/14 fail in keyword-only mode)
- C3 temporal = 0.5714 (5 月份 expressions all return 0 results)
- C4 entity_heavy = 1.0000 (ceiling)

This baseline ran with `semantic_enabled: false` (line 14 of result). It documents L2 keyword-only mode behavior. The CTO initially misread these numbers as "Life Index production retrieval capability" and started designing v1.2.0 sub-PRDs that targeted ranking improvements (BM25 normalization / entity_boost / RRF) — none of which would have moved the needle, because:

- C1/C4 already ceiling → no headroom for ranking work
- C2 paraphrase failures are **0-results** (token not in corpus), not ranking errors
- C3 temporal failures are **abstract Chinese month expression** mismatches, not ranking errors

→ Root cause: **truthfulness model未定调** → eval mode vs production mode mismatch → PRD scope misaligned.

### Architectural status before ADR-028

| Layer | Default behavior (pre-ADR-028) | Comment |
|---|---|---|
| `tools/search_journals/core.py:1026` | mode = "hybrid" (keyword + semantic + RRF) | production default |
| `tools/eval/__main__.py:38-40` | `--semantic` flag default disabled | eval default keyword-only |
| `tools/search_journals/query_types.py:89` | `pipelines={"keyword": True, "semantic": True}` | dataclass default both on |
| `tools/lib/search_config.py:138` | `EMBEDDING_MODEL.name = "BAAI/bge-m3"` | SOTA-tier model (not the bottleneck) |

Three different defaults across three layers reflect the absence of a single source of truth on L2 truthfulness model.

---

## Rationale

### Why pure keyword default (not hybrid)

1. **Product promise alignment**: "不遗漏每一个人生碎片" is a recall-first signal. Hybrid mode's P@5=0.49 means half of "extra recall" is noise — users can't trust the result set, which is worse than a smaller honest set.

2. **Determinism**: Keyword retrieval is deterministic. Vector retrieval depends on embedding model version, normalization, and threshold tuning — all of which drift across releases. CHARTER §1.6 backward compatibility favors deterministic L2.

3. **Layer hygiene** (per CHARTER §1.4, §1.5, §1.10): L2 is the deterministic basal layer. Semantic noise filtering requires either LLM (forbidden in L2 per §1.5) or fragile threshold tuning (the very problem we're trying to escape). Push semantic concerns to L3.

4. **Embedding model isn't the bottleneck**: BGE-M3 (current) is SOTA-tier Chinese embedding. Upgrading to multilingual-e5-large or OpenAI text-embedding-3 gives marginal improvement (and the latter violates §1.5 / Foundation Freeze offline). The bottleneck is **dense retrieval inherently mismatched to short Chinese journal corpus**, not model quality.

5. **Karpathy simplicity**: A pure keyword L2 is simpler to reason about. Users grok "I searched for X, X isn't in the corpus, that's why I got 0 results." Users don't grok "embedding similarity says this is related, but actually it's noise."

### Why preserve semantic code (not delete)

1. L3 agent path may legitimately need vector retrieval for downstream filtering (`--semantic` flag preserved)
2. Zero-result keyword fallback (ADR-006) provides recall safety net without polluting main path
3. Future architecture (L3 agentic mature) may need vector signal merged through agent reasoning, not L2 default
4. Removing it loses optionality with no benefit

### Why truncation lives in display layer only

1. Retrieval truthfulness ("complete token-match set") must be intact for the recall promise
2. CLI ergonomics (don't flood terminal) require display cap
3. Decoupling lets agents bypass cap when needed (agent passes `--limit 0` and gets full set)
4. `total_matches` count tells user "what they're missing" → consent over silent truncation

---

## Consequences

### Positive

- **CHARTER §1.11 enshrines product promise**: future agents/CTOs can't silently revert to hybrid default
- **eval gate ↔ production runtime mode aligned**: both now default keyword-only
- **PRD scope clarity**: future search work targets L1 enrichment + L3 agentic + L2 token coverage, not "magic threshold tuning"
- **User trust**: `total_matches` makes retrieval honest about coverage

### Negative

- **Direct CLI users lose paraphrase capability** unless they explicit `--semantic` or go through agent
- **R@5 numbers in evaluation will appear lower** than hybrid mode would show — but this reflects the deliberate trade-off (precision/honesty > recall-with-noise)
- **Migration cost**: 3 places in code (`core.py`, `query_types.py`, default flags) need alignment; existing tests may need updating to assume keyword-only default

### Neutral

- **No data layer changes**: §1.6 backward compatibility intact
- **Existing `.index/` vector index files preserved**: can be regenerated for `--semantic` opt-in
- **ADR-006 (semantic adaptive threshold) preserved**: its zero-result fallback role is consistent with §1.11 exception (c)
- **ADR-010 (RRF weight tuning) preserved**: only used when `--semantic` is on

---

## Implementation Notes (for future code PR, not this ADR)

| Location | Current | Target |
|---|---|---|
| `tools/search_journals/core.py:1026` | `# default mode: hybrid` | `# default mode: keyword (per CHARTER §1.11)` + reset default |
| `tools/search_journals/query_types.py:89` | `pipelines={"keyword": True, "semantic": True}` | `pipelines={"keyword": True, "semantic": False}` |
| `tools/eval/__main__.py:38-40` | (already keyword-only default ✓) | no change |
| L2 result set | `top_K` truncated (size TBD) | full set + `total_matches` field |
| CLI display layer | hard truncate 20 | default top-20 + "showing 20 of N, use --limit 0" + opt-out flag |
| Documentation | no §1.11 reference | CHARTER §1.11 added, ARCHITECTURE.md updated |

These code changes are **NOT in this ADR's scope**. They will be driven by the new v1.2.0 cycle PRD (renamed: `.strategy/cli/v1.2.0_搜索truthfulness与recall-first/`).

---

## Open Questions (deferred to new v1.2.0 cycle PRD)

1. **What is the correct CLI display default?** (20 vs 50 vs always full vs pagination?) → answered in new PRD
2. **How is `total_matches` displayed in JSON vs human CLI mode?** → answered in new PRD
3. **Should `--semantic` opt-in include a confirm prompt warning about noise?** → answered in new PRD
4. **Should L1 enrichment work (tags/topics/aliases auto-generation) be part of v1.2.0 or v1.3.0?** → CTO推荐 separate cycle to avoid scope creep
5. **Should Sub-PRD-2.4 中文 temporal pattern normalization stay in the new v1.2.0 cycle?** → Yes, it cleanly targets C3 weak spot under keyword-only model
