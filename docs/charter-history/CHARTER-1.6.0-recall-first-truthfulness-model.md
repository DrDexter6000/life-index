---
type: charter-history
charter_version: v1.6.0
revision: 6
date: 2026-05-23
title: Recall-First Retrieval Truthfulness Model Adoption
related:
  - '[[RFC-2026-05-23-l2-recall-first-truthfulness-model]]'
  - '[[ADR-028-l2-recall-first-keyword-pure]]'
  - '[[CHARTER]]'
---

# CHARTER v1.6.0 Adoption Note: Recall-First Retrieval Truthfulness Model

## What Changed

CHARTER.md was bumped from v1.5.0 to v1.6.0, revision count from 5 to 6.

### Added

- **§1.11 召回优先检索真实模型（Recall-First Retrieval Truthfulness Model）**
  - Enshrines the product promise "不遗漏您每一个人生碎片" as a 50-year constitutional invariant.
  - Defines three rules:
    1. **Token-match completeness**: L2 default retrieval must return the complete token-match candidate set; no relevance-threshold truncation at retrieval layer.
    2. **Ranking ↔ truncation decoupling**: L2 search core returns full ranked result set + `total_matches`; truncation lives in display layer only with `--limit 0` opt-out and user-visible "still N results" hint.
    3. **Semantic / vector retrieval as explicit opt-in**: L2 default does not call vector retrieval; activated only by explicit `--semantic` flag, L3 agent explicit request, or zero-result keyword fallback (existing ADR-006 behavior).
  - Paraphrase / abstract semantic queries are explicitly assigned to L1 enrichment (allowed LLM) + L3 agentic query rewrite (allowed LLM), NOT to L2 default retrieval.
  - Relationship with §1.5: §1.5 prohibits LLM in L2; §1.11 further restricts L2 default to not call vector retrieval as main path.

### Amended

- **§3.2 双管道作为确定性原语** — added amendment note clarifying that "双管道" continues to exist as a deterministic primitive (FTS5 + vector + RRF all preserved as available, deterministic, non-LLM); the **default runtime activation form** is now governed by §1.11 (default = keyword pipeline only; vector pipeline via explicit opt-in). §3.2's "foundation not replaceable" promise remains intact — the foundation stays; only its default form is tightened.

- **§5.3 不可修订的章节** — added §1.11 to the un-weakenable clause list. §1.11 can only become stricter, never looser. Future proposals to revert L2 default to hybrid must go through §5.2 substantive gate to amend §1.11.

### Not Changed (Explicitly Preserved)

- **§1.5**: unchanged (vector search remains in the "deterministic allowed" column; §1.11 narrows its default usage, but §1.5 text stays)
- **§3.1**: unchanged (Retrieval / Ranking / Presentation three-layer separation already prohibits hard top-K truncation; §1.11 elevates this implementation-layer rule to product-promise invariant)
- **§4.1**: unchanged (existing "硬切 top-K is unconstitutional" anti-pattern stays; §1.11 reinforces and extends)
- **§1.6 backward compatibility**: unchanged (no L1 data format changes; only L2 runtime default behavior changes)
- **§1.9 Agent-Native**: unchanged (modules without LLM provider still complete core value via token-match retrieval; paraphrase is a known L3 responsibility per §1.9's "language work" boundary)
- **ADR-006 (Semantic Adaptive Threshold)**: preserved; its zero-result fallback role fits §1.11 exception (c)
- **ADR-010 (RRF Weight Tuning)**: preserved; only activated when `--semantic` opt-in

## Why

### Triggering Evidence

1. **v1.2.0 cycle2 absorption A6 baseline** (`.agent-reports/v120-search-fusion-m3/phase-a/A6_baseline_result.json`) revealed bimodal distribution: C1/C4 = 1.0 ceiling, C2 paraphrase = 0.14 disaster, C3 temporal abstract month expressions = 0.0/14. CTO initially misread the baseline as Life Index production capability — until 主理人 surfaced that this is keyword-only mode (semantic_enabled: false on line 14 of result), not production mode.

2. **主理人 historical context recall** (2026-05-23 conversation): semantic threshold tuning never reached "两全其美" point — too low = noise flood, too high = zero match. A prior orchestrator agent's silent decision was to set semantic default off, but this decision was never enshrined; eval gate (off) / production runtime (`tools/search_journals/core.py:1026` default hybrid) / dataclass default (`tools/search_journals/query_types.py:89` both pipelines on) were three different defaults across three layers.

3. **Round 19 Phase 1-D hybrid mode data** (CHARTER §4.5 note): R@5=0.8387, P@5=0.4894 — half of hybrid results are noise. Recall gain comes at unacceptable precision cost.

4. **Embedding model is not the bottleneck**: current model is BAAI/bge-m3 (SOTA-tier Chinese embedding); upgrading offers only marginal improvement (and OpenAI text-embedding-3 violates §1.5 / Foundation Freeze offline). Root cause is dense retrieval inherently ill-suited to short Chinese journal corpus, not model quality.

### Strategic Rationale

The "不遗漏每一个人生碎片" promise has lived only in README's spoken language. It has been the unspoken anchor of every search architecture decision for 16+ rounds of iteration. Surfacing it to CHARTER §1.11 status:

1. **Makes the promise inviolable**: future agents/CTOs cannot silently revert to hybrid default for the sake of "paraphrase numbers"
2. **Aligns three layers of default**: eval gate / production runtime / dataclass default all become keyword-only after consequent code changes
3. **Clarifies layer responsibilities**: paraphrase is L1 enrichment + L3 agentic work, NOT L2 main path responsibility
4. **Provides PRD anchor**: future search PRDs can directly anchor on §1.11 rather than re-discovering the model each cycle

## Substantive Gate Compliance (per §5.2)

| Item | Status | Location |
|---|---|---|
| ① rationale | ✅ | RFC §1 |
| ② opposing views addressed (≥2) | ✅ (3 views) | RFC §4 |
| ③ impact inventory | ✅ | RFC §5 |
| ④ 主理人 ack signature | ✅ (acknowledged in 2026-05-23 conversation) | RFC §7 |

All 4 items complete → land immediately, per §5.2 流程 #3 ("起草到 land 无强制最短时间间隔").

## Downstream Consequences

### Documentation (this commit)

- `CHARTER.md`: header + §1.11 + §3.2 amendment + §5.3 updated
- `docs/charter-history/CHARTER-1.6.0-recall-first-truthfulness-model.md`: this file
- `docs/adr/ADR-028-l2-recall-first-keyword-pure.md`: architecture decision record
- `docs/rfc/RFC-2026-05-23-l2-recall-first-truthfulness-model.md`: substantive gate evidence
- `docs/ARCHITECTURE.md`: L2 default behavior description updated to reflect §1.11
- `.strategy/cli/v1.2.0_搜索多信号融合/M1_PRD.md`: marked as SUPERSEDED, points to new cycle
- `.strategy/cli/v1.2.0_搜索truthfulness与recall-first/README.md`: new cycle starting point (placeholder, M1 PRD to follow)

### Code (NOT in this commit; driven by new v1.2.0 cycle)

Following the documentation land, a separate v1.2.0 cycle will execute the code changes:

| Location | Required change |
|---|---|
| `tools/search_journals/core.py:1026` | default mode reset from hybrid to keyword |
| `tools/search_journals/query_types.py:89` | `pipelines` default semantic = False |
| L2 search core | return full result set + `total_matches` |
| CLI display layer | default top-20 + "showing 20 of N" hint + `--limit 0` opt-out |

Code changes go through Gold Set regression as required by §5.2 流程 #2.
