---
type: charter-rfc
status: accepted
created: 2026-05-14
accepted: 2026-05-14
charter_version: v1.4.0
title: Module-Foundation Contract Boundary
owner: Life Index Developer
lead_reviewer: 主审_GPT
reviewers:
  - CTO Review v2 / 副审_Opus
cooldown: waived_by_three_party_review
---

# RFC-2026-05-14: Module-Foundation Contract Boundary

## 1. Summary

This RFC introduces `CHARTER.md` §1.10, the Module-Foundation Contract Boundary. Life Index CLI is the stable foundation layer (L1/L2) providing deterministic, composable primitives to the agent ecosystem. Advanced L3/L4 modules (Memoir Engine, Mood Map, Digital Letters, etc.) may be intelligent, long-running, and own their own workflow/process state, but their default form must be built around CLI primitives without modifying or depending on CLI core internals. Module-local process artifacts (cursors, checkpoints, intermediate evidence packs, module-local indices) are permitted in the module's own physical directory, subject to CHARTER §1.1 Data Sovereignty and §1.9 Agent-Native Module Principle.

This RFC also amends §2.2 to distinguish data state (L1/L2) from module-local process state (L3), and amends §5.2 to record the three-party review override mechanism for RFC cooldown when explicitly documented.

The CHARTER §5.2 24-hour cooldown for this governance amendment was overridden by recorded three-party review on 2026-05-14: the lead reviewer proposed immediate integration, the secondary reviewer agreed with the substance while flagging cooldown risk, and the author/user made the final override decision. This is recorded as `cooldown: waived_by_three_party_review`.

CHARTER §5.2 Gold Set regression was run despite this being a governance-only amendment: `.venv\Scripts\python.exe -m tools eval --compare-baseline tests/eval/baselines/round-19-phase1d-baseline-v4.json --no-semantic --no-overlay` exited 0, with MRR@5 0.5559 → 0.5977, Recall@5 0.7957 → 0.8495, Precision@5 0.4628 → 0.4655, and nDCG@5 0.5932 → 0.6286.

## 2. Trigger Evidence

The CTO review on 2026-05-14 (Opus advisory review, Maestro session context) identified that Life Index's boundary between "CLI core" and "advanced modules" was only implicitly understood, not codified as a charter-level invariant. Without explicit codification:

- Advanced modules could silently grow their own LLM clients, provider configs, and data exposure surfaces (violating §1.9).
- Module workflow state (cursors, checkpoints, run_id artifacts) had no defined home, risking pollution of L1 user data or L2 CLI core.
- The "promotion" path from "module-specific helper" to "CLI primitive" had no governance process, risking either CLI bloat (over-stuffing) or module re-invention (over-delegation).
- §2.2's "L3 must be stateless" was in tension with the reality that long-running L3 modules need process-local state.

## 3. User Decision Record

The following decisions were explicitly accepted by the author during the 2026-05-14 review cycle:

| # | Decision | Status |
|---|---|---|
| 1 | Principle accepted: CLI is stable foundation; modules own workflow/process state | Accepted |
| 2 | Scope covers both official (in-repo) and third-party (external) modules | Accepted |
| 3 | Module-local state lives with the installed skill/plugin/module directory (e.g. `.openclaw/workspace/skills/life-index/models/{module_name}/`, or an equivalent module-owned subdirectory), NOT under `~/Documents/Life-Index` | Accepted |
| 4 | Do not implement plugin loader / entry-point discovery / runtime module registry now | Accepted |
| 5 | Build contract-style hot-plug architecture guidance and placeholders/docs | Accepted |
| 6 | CLI primitive promotion threshold: multiple modules, clearly cross-module reusable, or explicit developer/user determination | Accepted |
| 7 | Three-party review override allowed: lead reviewer + secondary reviewer propose, user makes final decision; RFC cooldown can be overridden when recorded explicitly | Accepted |
| 8 | Interpret L3 "stateless" as "no long-term user-data truth source"; module-local process state is allowed | Accepted |
| 9 | "Hot-pluggable" means physical/contract-level decoupling, NOT runtime dynamic loading | Accepted |

## 4. Accepted CHARTER Change

### §1.10 Module-Foundation Contract Boundary (new)

See CHARTER.md §1.10 for the full invariant text. The core principle:

- Life Index CLI provides deterministic, stable, composable primitives (L1/L2): read/write, index, search, aggregate, entity, eval, health, index navigation.
- Advanced L3/L4 modules may be intelligent, long-running, slow, and own workflow/process state.
- Modules default to consuming CLI primitives through stable JSON contracts; they must not modify CLI core internals or create second authority writes outside L1.
- Module-local process artifacts (cursor, checkpoint, intermediate evidence, module-local index) live in the module's own directory, not in user data.
- Promotion from "module helper" to "CLI primitive" requires RFC: deterministic, cross-module reusable, low-LLM, 50-year semantic stable.

### §2.2 Amendment (L3 state distinction)

§2.2 "L3 must be stateless" is refined to:
- **Data state** (journal, frontmatter, entity_graph, metrics) remains L1/L2 responsibility.
- **Process state** (run_id artifacts, cursor, checkpoint, iteration intermediate conclusions, module-local cache) is permitted in L3 module-local directories, still subject to §1.1 Data Sovereignty (no outbound upload, clearable, not entering L1 truth source).

### §5.2 Amendment (three-party review override)

The standard §5.2 RFC cooldown may be overridden by explicit three-party review when:
1. Lead reviewer proposes the override.
2. Secondary reviewer (or read-only advisory reviewer) concurs.
3. Author/user makes the final decision.
4. The override is recorded in the RFC metadata (`cooldown: waived_by_three_party_review`) and in the charter-history archive.

This mechanism does not weaken §5.3 (unchangeable sections); §5.3 remains absolute.

## 5. Opus Advisory Summary

副审_Opus reviewed the boundary framework in an advisory capacity and recommended:

- The boundary direction is correct and consistent with §1.4 / §1.5 / §1.9 / ADR-026.
- Four adjustments needed: (a) clarify stable CLI contract dimensions (JSON shape + field semantics + error codes + SLO), (b) narrow "hot-pluggable" to physical/contract decoupling not runtime loading, (c) reconcile §2.2 "stateless" with module process state via data/process distinction, (d) codify the "primitive promotion" flow as a governance rule not just a slogan.
- Recommended path: RFC → CHARTER §1.10 → ARCHITECTURE/API mirror.
- Warned against two-way risks: over-stuffing CLI (L2 bloat, test matrix explosion) vs over-delegating to modules (reinvention, L1 bypass, schema drift).
- All four adjustments and risk warnings are incorporated into this RFC and the resulting CHARTER §1.10.

## 6. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Module state directory location becomes contested | Fixed in user decision #3: module-local, not under `~/Documents/Life-Index`. Revisit via RFC if future deployment contexts change. |
| "Hot-plug" misinterpreted as plugin loader | Explicitly narrowed in §1.10 and user decision #9. No runtime registry until a future RFC explicitly approves it. |
| CLI primitive promotion threshold too vague | Criteria codified in §1.10: deterministic + low LLM + 50-year semantic stable + (multiple modules OR explicit developer/user determination). Threshold left to RFC review judgment to avoid premature quantification. |
| Three-party override erodes cooldown discipline | Override requires two reviewers + user + explicit record; §5.3 unchangeable sections still absolute. |
| §2.2 amendment creates loophole for data in L3 | "Process state" definition is narrow (cursor/checkpoint/cache); any schema/entity/topic/user-content state still L1/L2. |

## 7. Relationship to Existing Invariants

- §1.10 ↔ §1.3 (CLI as SSOT): §1.3 says "read/write must be CLI-exposed"; §1.10 adds "which new primitives should be promoted to CLI vs stay module-local."
- §1.10 ↔ §1.4 (Layer Isolation): §1.4 draws layers; §1.10 adds "module state ownership" detail between L2 and L3.
- §1.10 ↔ §1.5 (Deterministic/Intelligent Divide): §1.5 says "L2 must not call LLM"; §1.10 adds "L2 must not implement language/interpretive capability for a single module."
- §1.10 ↔ §1.6 (Backward Compatibility): §1.10 decomposes "stable CLI contract" into JSON shape / field semantics / error codes / SLO dimensions.
- §1.10 ↔ §1.7 (Three Bottom Lines): §1.10 operationalizes "宁可功能简单" by keeping module burden in modules and CLI burden in CLI.
- §1.10 ↔ §1.8 (Long-Termism): §1.10's promotion flow is §1.8 applied — invest early when real demand meets high-migration-cost category.
- §1.10 ↔ §1.9 (Agent-Native): §1.9 governs "modules must not bundle LLM by default"; §1.10 governs "modules must not modify foundation layer"; together they form the two agent-native module invariants.
- §1.10 ↔ ADR-026: ADR-026 §3–§5 (Index Tree / batch-cursor / addressable artifacts) and §7 (anti-requirements) are implementation-side anchors for §1.10.

## 8. Rollback

If §1.10 proves harmful, rollback must use the normal CHARTER revision process (§5.2). Because §1.10 is an addition (not a weakening of existing constraints), rollback would simply remove §1.10, revert §2.2 to its prior "stateless" wording, remove the §5.2 override record, and archive the failure rationale under `docs/charter-history/`. No existing code or data would be invalidated by such rollback.

## 9. Implementation Plan

| Phase | Scope | Deliverables |
|---|---|---|
| 0 | Charter adoption | CHARTER.md v1.4.0, this RFC, charter-history snapshot |
| 1 | Architecture/API mirror | ARCHITECTURE.md §1.4 update, API.md stability contract section |
| 2 | Internal pilot | Select one consumer (recommended: `aggregate`) to validate "module discovers gap → RFC promotion" flow |
| 3 | Recall-preservation eval fixture | Minimal eval gate for future T3/T4 module development |
| 4 | Module template (future) | Evidence/scaffold-first module skeleton when first real advanced module is designed |
| 5 | SSOT docs alignment | AGENT_ONBOARDING / AGENTS.md pointer updates |

## 10. Override Record

The three-party review override was recorded on 2026-05-14: lead reviewer (主审_GPT) proposed immediate integration, secondary reviewer (副审_Opus) agreed with the §1.10 substance and explicitly flagged cooldown-risk concerns, and the author/user made the final override decision with that risk visible. This override is recorded in RFC metadata (`cooldown: waived_by_three_party_review`) and in the charter-history adoption note.

This instance is self-bootstrapping in the strict governance sense: the three-party override mechanism is introduced by this RFC and also used to adopt this RFC. The final authority for that self-bootstrap rests with the author/user's explicit override decision after lead-reviewer proposal and secondary-reviewer risk review. This exception does not create a routine bypass pattern; future §5.2 amendments must either observe the cooldown or invoke an override mechanism that is already in force.

Source context:
- `.opus-learnings/advanced-module-boundary/report.md` (副审_Opus advisory review)
- 副审_Opus advisory review in Maestro session
- User explicit acceptance of decisions #1–#9 above

## 11. Non-Goals

- This RFC does not implement a plugin loader, entry-point registry, or dynamic module discovery mechanism.
- This RFC does not define the final module directory layout for all possible installation contexts (only the principle: module-local, not in user data).
- This RFC does not create any new CLI commands or tools.
- This RFC does not modify product code or tests.
