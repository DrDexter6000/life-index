---
type: charter-rfc
status: accepted
created: 2026-05-14
accepted: 2026-05-14
charter_version: v1.3.0
title: Agent-Native Module Principle
owner: Life Index Developer
lead_reviewer: 主审_GPT
reviewers:
  - CTO Review v2 / 副审_Opus
cooldown: waived_by_author_override
---

# RFC-2026-05-14: Agent-Native Module Principle

## 1. Summary

This RFC introduces `CHARTER.md` §1.9, the Agent-Native Module
Principle. Life Index modules must not bundle or implicitly call their own LLM
on default execution paths. The default output of CLI and advanced modules
should be deterministic evidence, indexes, aggregates, claim envelopes,
scaffolded prompts, and agent instructions. Language synthesis remains the
responsibility of the calling agent, unless the user explicitly opts into a
named provider fallback.

The author explicitly waived the CHARTER §5.2 24-hour cooldown on 2026-05-14
for special circumstances and authorized immediate adoption. This RFC records
that override instead of treating it as an ordinary cooldown-compliant
amendment.

CHARTER §5.2 Gold Set regression is marked N/A for this Phase 0 adoption
because the commit changes governance documents only and does not change search
code, ranking parameters, indexes, or evaluation baselines.

## 2. Trigger Evidence

The CTO review on 2026-05-14 identified an active governance/code mismatch:

- `CHARTER.md` §1.5, §2.3, and §4.1 prohibit L2 from calling an LLM.
- `tools/lib/llm_extract.py` is an L2 shared library that calls an
  OpenAI-compatible API for metadata extraction.
- `tools/write_journal/prepare.py` imports `extract_metadata_sync` from that
  library and can use it in the write preparation path when LLM configuration
  is available.

The same review also identified a future architecture risk: without an explicit
Agent-Native module invariant, advanced modules such as Memoir Engine, Digital
Soul, virtual-family dialogue, or social-media import could each grow their own
provider client, API key path, and hidden data exposure surface.

## 3. Accepted CHARTER Change

`CHARTER.md` v1.3.0 adds §1.9 after §1.8. The accepted principle is:

- L2 / L3 modules must not hold, configure, or call an LLM on their default
  execution paths.
- Modules default to deterministic data and auditable scaffolding:
  search results, entity graph, aggregate/analyze results, evidence packs,
  claim envelopes, scaffolded prompts, and agent instructions.
- Calling agents perform language work by default.
- Explicit provider fallback is allowed only when the user opts in and the
  provider/data-exposure boundary is clear.

This RFC also revises `CHARTER.md` §3.3 to generalize Agent orchestration from
search-only wording to L3 workflow/module orchestration, and appends §4.1
anti-patterns covering bundled LLM defaults, hidden per-module provider
configuration, and L2 tools that take on language/interpretive work for
advanced modules.

## 4. Intended Non-Goals

- This RFC does not ban LLM use in Life Index.
- This RFC does not prevent terminal-only users from choosing an explicit
  provider fallback.
- This RFC does not implement Phase 1 code migration.
- This RFC does not decide the final long-term provider adapter architecture.
  The strict two-location whitelist discussed in the handoff is treated as a
  short-term migration guard, not a permanent architecture commitment.

## 5. Impact

Immediate consequences:

- `CHARTER.md` is bumped from v1.2.0 to v1.3.0.
- The existing write-path LLM extraction becomes an explicitly recognized
  violation to be remediated in Phase 1.
- `smart-search` and future advanced modules must be designed so the default
  path produces evidence/scaffold output without owning an LLM.

Future consequences:

- Advanced modules can be intelligent and long-running, but their durable
  architecture is evidence/scaffold first and calling-agent synthesis second.
- Provider-specific synthesis paths remain explicit opt-in fallbacks.
- A future RFC may introduce a unified optional provider adapter/registry after
  Phase 1-3 migration proves the boundary.

## 6. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Terminal-only users lose automatic synthesis by default | Keep an explicit provider fallback with clear consent and data-exposure disclosure. |
| Strict short-term whitelist becomes long-term rigidity | Treat it as migration guard only; revisit via provider adapter RFC after Phase 1-3. |
| Existing code violates the new principle immediately after adoption | Record the violation and migrate it in Phase 1 instead of pretending the code already conforms. |
| §1.9 is confused with completion of the broader Life Index baseline | Record that this amendment sets architecture direction only; it does not satisfy major-version readiness gates. |

## 7. Implementation Plan

| Phase | Scope | Deliverables |
|---|---|---|
| 0 | Charter adoption | `CHARTER.md` v1.3.0, this RFC, charter-history adoption note |
| 1 | Write-path migration | Remove default LLM extraction from `write_journal`, move optional helper, add contract test and ADR |
| 2 | Smart-search refactor | Default evidence/scaffold output; explicit provider fallback |
| 3 | Regression guard | CI/pre-commit check preventing default-path LLM SDK/API-key leakage |
| 4 | Advanced module template | Evidence/scaffold-first module skeleton |
| 5 | SSOT docs alignment | ARCHITECTURE/API/SKILL/AGENT_ONBOARDING/README updates |
| 6 | Successor verification | Different human + different agent completes a non-trivial PR |

## 8. Override Record

The author instructed on 2026-05-14 that the recent strategic conclusions
should be integrated immediately and that the 24-hour cooldown should be
temporarily ignored for this special case. The implementation records that
authorization in CHARTER metadata and in the charter-history adoption note.

Source context:

- `.opus-learnings/CTO_Review_2026-05-14.md`
- `.opus-learnings/Handoff_Charter_19_Implementation.md`
- 副审_Opus focused review in Maestro session
  `4a9195a7-2d84-4426-a20e-5accaf21d8a2`

## 9. Rollback

If §1.9 proves harmful, rollback must use the normal CHARTER revision process
unless the author again explicitly overrides it. Rollback would revert
`CHARTER.md` to v1.2.x semantics, archive the failure rationale under
`docs/charter-history/`, and document whether default bundled LLM behavior is
being restored or replaced with a narrower principle.
