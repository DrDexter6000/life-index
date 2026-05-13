# RFC: L1/L2 Future Compatibility Baseline

> **Status**: Draft
> **Created**: 2026-05-13
> **Decision record**: `docs/adr/ADR-026-l1-l2-future-compatibility-baseline.md`
> **Raw discussion archive**: `docs/concepts/CN-002-life-index-terminal-architecture-discussion-record.md`
> **Review archive**: `docs/concepts/CN-003-life-index-future-compatibility-review-record.md`
> **Charter impact**: Proposed; no direct Charter edit in this RFC
> **Authors / reviewers**: Life Index author, 主审_GPT, 副审_Opus; DeepSeek review requested
> **Cooldown**: At least 24 hours after RFC creation before Charter approval, per `CHARTER.md` §5.2
> **Status transitions**: Draft (2026-05-13) → user review / cooldown → accepted or revised

## 1. Problem

Life Index's terminal vision is broader than search. Future modules may perform long-running, agent-orchestrated analysis over decades of journals: multi-pass search, evidence collection, hierarchical summarization, interpretive answers, persona snapshots, or creative emulation.

These examples are not immediate roadmap commitments. They are pressure tests for the L1/L2 foundation.

The core question is:

> What must L1/L2 provide so future L3/L4 modules can safely compose Life Index over a 50-year corpus without modifying the data layer or deterministic core?

## 2. Triggering Evidence

D2 proved that some natural-language questions are not retrieval failures. "过去60天我有多少天晚睡" is better treated as deterministic aggregate/analyze than as smart-search synthesis.

This suggests a broader pattern:

- Deterministic predicates should be answered by deterministic L2 primitives.
- LLMs should orchestrate, interpret, and synthesize only after evidence is collected.
- Long-running advanced modules need navigability, checkpoints, and evidence contracts more than they need a smarter single-pass prompt.

## 3. Proposal

Define a **L1/L2 Future Compatibility Baseline** consisting of:

1. Stable CLI JSON contracts.
2. Evidence Pack and Claim Envelope schemas.
3. Navigable Index Tree API.
4. Batch/cursor/pagination support.
5. Addressable intermediate artifacts with checkpoint/resume semantics.
6. Evaluation contracts for evidence and factuality.
7. Explicit L2 anti-requirements.

## 4. Layer Boundaries

### L1 Data Layer

Owns original Markdown/YAML journals and rebuildable machine indexes.

Must not store LLM-generated conclusions as original facts.

### L2 CLI Core

Owns deterministic primitives:

- search / retrieval
- aggregate / analyze
- index generation
- entity graph operations
- future compare/diff primitives if deterministic
- batch/cursor/chunk access

L2 must remain fast, deterministic, idempotent, and free of LLM calls.

### L3 Intelligence Orchestration

Owns long-running plans:

- multi-pass search
- task graph / checkpoint / retry
- LLM calls
- evidence packing
- claim classification
- interpretive synthesis
- creative emulation

L3 may be slow and may run for hours if it reports expected cost/time/work to the user.

### L4 Interface

Owns presentation, progress, cancel/resume affordances, and user-facing warnings.

## 5. Index Tree Contract Direction

Index Tree should become a navigable substrate for long-running modules:

- enumerate year/month/topic/entity nodes
- provide stable node IDs
- map nodes to source paths and summaries
- support progress/checkpoint localization
- support hierarchical roll-up

Index Tree must not become a default store for persona, relationship, emotion, or narrative conclusions. If LLM-derived node annotations are ever allowed, they must be optional, provenance-bearing, rebuildable, and excluded from deterministic default retrieval/ranking unless separately approved.

## 6. Claim Envelope / Evidence Pack Direction

Future L3 outputs should distinguish:

- `measurable_exact`
- `measurable_approximate`
- `interpretive_evidence_backed`
- `creative_emulation`
- `not_measurable`

ADR-026 owns the initial claim-type list; this RFC repeats it only to show the proposed contract direction.

Every non-trivial claim should carry:

- source paths
- relevant snippets or hashes
- confidence/exactness
- limitations
- counter-evidence where applicable

## 7. L2 Anti-Requirements

L2 must not implement:

- persona interpretation
- emotion interpretation
- relationship judgment
- narrative synthesis
- digital letters
- creative emulation
- cross-journal LLM reasoning
- any LLM call

These are L3/L4 modules that consume L2 output.

ADR-026 owns the canonical anti-requirements list. This RFC mirrors it for review context.

## 8. Major Version Gate

A future major CLI foundation version should be gated by contracts, not by a single advanced feature.

Suggested gate:

> At least one external or separable advanced module can run a long-horizon analysis using only stable L1/L2 contracts, produce Evidence Pack / Claim Envelope output, and pass evaluation without modifying L1/L2.

The first validation module is a structural gate-selection item and should be chosen in a separate RFC or roadmap decision. This RFC does not choose it.

## 9. Proposed SSOT Updates

If accepted after review/cooldown:

1. Add a compact principle to `CHARTER.md` clarifying that future advanced modules are L3/L4 consumers of deterministic L2 primitives.
2. Add L2 anti-requirements to the Charter anti-patterns or layer charter section.
3. Add implementation details to `docs/ARCHITECTURE.md`.
4. Add concrete JSON schema details to `docs/API.md` when Claim Envelope / Evidence Pack / Index Tree navigation APIs are implemented.
5. Link this RFC and ADR from `docs/adr/INDEX.md`.

## 10. Gate Validation Follow-up

The first external/separable advanced module used to validate the major-version gate remains unselected. It must be selected before the gate can be claimed as passed.

## 11. Open Questions

1. Where should addressable intermediate artifacts live: `.index/intermediate/`, `.life-index/runs/`, or another local path?
2. Should `Claim Envelope` be introduced first as an internal schema or public CLI output contract?
3. Should navigable Index Tree API be a new command (`life-index index-tree`) or an extension of existing `index` / `generate-index` commands?
