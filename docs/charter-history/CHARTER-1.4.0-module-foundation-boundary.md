---
type: charter-history
charter_version: v1.4.0
revision: 4
date: 2026-05-14
title: Module-Foundation Contract Boundary Adoption
related:
  - '[[RFC-2026-05-14-module-foundation-boundary]]'
  - '[[RFC-2026-05-14-agent-native-module-principle]]'
  - '[[CHARTER]]'
---

# CHARTER v1.4.0 Adoption Note: Module-Foundation Contract Boundary

## What Changed

CHARTER.md was bumped from v1.3.0 to v1.4.0, revision count from 3 to 4.

### Added

- **§1.10 模块-基础层契约边界（Module-Foundation Contract Boundary）**
  - Codifies that Life Index CLI is the stable foundation (L1/L2) providing deterministic primitives to the agent ecosystem.
  - Advanced L3/L4 modules may be intelligent, long-running, and own workflow/process state.
  - Modules consume CLI through stable contract (JSON shape + field semantics + error codes + SLO).
  - Module-local process state (cursor, checkpoint, intermediate evidence) lives in module's own directory, not in `~/Documents/Life-Index`.
  - "Hot-pluggable" means physical/contract decoupling, not runtime dynamic loading.
  - Primitive promotion flow: deterministic + cross-module reusable + low-LLM + 50-year semantic stable → RFC to promote to L2.

### Amended

- **§2.2 L3 · Intelligence Layer**
  - Refined "L3 must be stateless" to distinguish:
    - **Data state** (journal, frontmatter, entity_graph, metrics) → L1/L2
    - **Process state** (cursor, checkpoint, run_id artifacts, module-local cache) → permitted in L3 module-local directories
  - Clarified that L3 must not hold long-term user-data truth source.

- **§5.2 修订流程**
  - Added explicit three-party review override mechanism for 24h cooldown:
    - Lead reviewer proposes
    - Secondary reviewer concurs
    - Author/user decides
    - Override recorded in RFC metadata and charter-history archive
  - Explicitly stated this mechanism does not weaken §5.3 unchangeable sections.

## Why

Without explicit codification:
- Advanced modules could silently grow LLM clients and data exposure surfaces (violating §1.9).
- Module workflow state had no defined home, risking L1 pollution.
- The promotion path from "module helper" to "CLI primitive" had no governance process.
- §2.2 "stateless" was in tension with real long-running L3 module needs.

## Decisions Incorporated

See `docs/rfc/RFC-2026-05-14-module-foundation-boundary.md` §3 for the full user decision record. Key decisions:

1. CLI is stable foundation; modules own workflow/process state.
2. Scope covers both official and third-party modules.
3. Module-local state lives in module directory, not `~/Documents/Life-Index`.
4. No plugin loader / runtime registry implemented now.
5. Hot-plug = physical/contract decoupling, not dynamic loading.
6. CLI primitive promotion threshold: multiple modules, cross-module reusable, or explicit dev/user determination.
7. Three-party review can override RFC cooldown when explicitly recorded.
8. L3 "stateless" = no long-term user-data truth source; process state allowed.

## Override Record

The CHARTER §5.2 24-hour cooldown was overridden by recorded three-party review on 2026-05-14: the lead reviewer proposed immediate integration, 副审_Opus agreed with the §1.10 substance while flagging cooldown-risk concerns, and the author/user made the final override decision. Recorded in RFC metadata as `cooldown: waived_by_three_party_review`.

This instance is self-bootstrapping in the strict governance sense: the three-party override mechanism is introduced by this amendment and also used to adopt it. The final authority for that self-bootstrap rests with the author/user's explicit override decision after lead-reviewer proposal and secondary-reviewer risk review. This exception does not create a routine bypass pattern; future §5.2 amendments must either observe the cooldown or invoke an override mechanism that is already in force.

## Risks

- Module state directory location may need revisit for different installation contexts.
- "Hot-plug" narrowing must be reinforced in future docs to prevent plugin-loader misinterpretation.
- Primitive promotion threshold intentionally leaves quantification to RFC review to avoid premature rigidity.

## Rollback

Rollback would remove §1.10, revert §2.2 to prior "stateless" wording, remove the §5.2 override record, and archive failure rationale. No existing code or data would be invalidated.
