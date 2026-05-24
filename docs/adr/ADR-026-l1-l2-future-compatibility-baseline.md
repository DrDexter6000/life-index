# ADR-026: L1/L2 Future Compatibility Baseline

> **Status**: Accepted as strategic direction; Charter amendment pending RFC/cooldown
> **Date**: 2026-05-13
> **Decision type**: Architecture / governance boundary
> **Context / review records**: archived in private local governance docs; this ADR is the public architecture decision.
> **RFC**: `docs/rfc/RFC-2026-05-13-l1-l2-future-compatibility-baseline.md`

## Context

The user clarified that advanced ideas such as digital letters, personality analysis, and long-running personal-memory reasoning are not immediate roadmap requests. They are terminal-state pressure tests: future user or community modules should be able to build on a stable Life Index CLI foundation without requiring L1/L2 rewrites.

The key architectural question is therefore not "which advanced module should be implemented now?" but:

> What must Life Index L1/L2 provide so future long-running, agent-orchestrated modules can safely compose the CLI over 10, 20, or 50 years of journals?

## Decision

Adopt the **L1/L2 Future Compatibility Baseline** as a strategic target for the next major CLI foundation.

Life Index CLI should be judged major-version-ready when L1/L2 provide stable, deterministic, composable contracts that allow external L3 modules to run long-horizon analysis without modifying L1/L2.

This baseline is not a commitment to build persona, digital-letter, or emotional-reasoning products now. It is a foundation contract for future modular development.

## Baseline Components

1. **Stable CLI contract**
   - Structured JSON output.
   - Schema/version fields where needed.
   - Backward-compatible error codes and result shapes.
   - Public contract documented in `docs/API.md`.

2. **Evidence Pack / Claim Envelope**
   - Advanced L3 modules must ground outputs in explicit evidence.
   - Claims should declare type, confidence, supporting evidence, counter-evidence where relevant, and limitations.
   - Initial claim types: `measurable_exact`, `measurable_approximate`, `interpretive_evidence_backed`, `creative_emulation`, `not_measurable`.
   - This generalizes the `aggregate_result` exactness/evidence discipline beyond deterministic counts.

3. **Navigable Index Tree**
   - Index Tree should provide stable navigation over year/month/topic/entity-style nodes.
   - It may act as sitemap, candidate narrowing layer, checkpoint anchor, and hierarchical summary skeleton.
   - It must not become a store of default LLM-derived persona/emotion/relationship conclusions.

4. **Batch / cursor / pagination support**
   - L2 tools should support chunk-wise operation for 50-year corpora.
   - Future L3 modules may run for hours; L2 primitives should remain fast, deterministic, and resumable.

5. **Addressable intermediate artifacts**
   - Long-running L3 modules need `run_id`-addressable intermediate files, idempotent writes, resume/retry semantics, and lifecycle rules.
   - These artifacts are not original user journals.

6. **Evaluation contract**
   - Evaluation must expand beyond search quality where needed.
   - Future baselines should measure evidence coverage, factual correctness, contract stability, and regression safety for advanced modules.

7. **L2 anti-requirements**
   - L2 must not implement persona interpretation, emotion interpretation, relationship judgment, narrative synthesis, digital letters, creative emulation, cross-journal LLM reasoning, or any LLM call.
   - Such capabilities belong in L3/L4 modules that compose L2 primitives.

## Index Tree Role

Index Tree is promoted from "browse/search convenience" to a **future-compatible navigation substrate**:

- Sitemap for long-running modules.
- Stable checkpoint anchor.
- Hierarchical summarization skeleton.
- Failure and progress localization mechanism.

Index Tree remains a deterministic/rebuildable structure. LLM-derived node metadata, if ever introduced, must be explicit, provenance-bearing, optional, and excluded from default deterministic retrieval/ranking unless separately approved.

## Versioning Implication

A future major version should not be gated by any single advanced feature.

The stronger gate is:

> Can an external or separable advanced module produce a credible long-running narrative or analysis result, with Evidence Pack / Claim Envelope output, without modifying L1/L2?

If yes, the foundation has reached the intended compatibility threshold. If no, the foundation is not ready regardless of how polished a single built-in module appears.

The first validation module for this gate is not selected by this ADR. It should be selected in a separate RFC or roadmap decision when the foundation contracts are concrete enough to test.

## Consequences

- Near-term work should focus on contracts, evidence, navigability, batching, and evaluation, not on shipping persona/digital-letter features.
- `CHARTER.md` should eventually receive a compact invariant/anti-requirement update, but only through the Charter amendment process.
- `docs/ARCHITECTURE.md` and `docs/API.md` should carry the implementation details once each contract becomes concrete.
- Roadmap items should distinguish **foundation-facing requirements** from **future product modules**.
- RFC open questions should be resolved component by component as each baseline contract enters implementation.
- Until a Charter amendment is approved, the L2 anti-requirements in this ADR have architecture-decision-level force. Any proposal to introduce those capabilities or data shapes into L2 must first revise or supersede this ADR.

## Non-Goals

- No immediate roadmap commitment to digital letters, persona emulation, emotional analysis, or "father loves me" style products.
- No relaxation of L2 performance/determinism: L2 primitives remain fast and deterministic; only L3 orchestration may be long-running.
- No direct storage of LLM-derived conclusions in original journals.
- No direct CHARTER edit without RFC, cooldown, and explicit user approval.
