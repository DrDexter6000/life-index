---
type: charter-history
title: CHARTER v1.3.0 Adoption — Agent-Native Module Principle
created: 2026-05-14
charter_version: v1.3.0
rfc: RFC-2026-05-14-agent-native-module-principle.md
---

# CHARTER-1.3.0-agent-native-module-principle

## Adoption Rationale

### Trigger

2026-05-14 CTO Review v2 (Claude Opus 4.7) identified:
1. Active CHARTER §1.5 violation: `tools/lib/llm_extract.py` (L2 library) calls LLM API; consumed by `tools/write_journal/prepare.py` in default write path
2. Structural gap: No invariant prevents future modules from each bundling their own LLM, API key, and provider

### User Override

CHARTER §5.2 requires 24-hour cooldown between RFC and approval. On 2026-05-14, the project author explicitly waived this cooldown, citing:
- Active governance violation in production code
- Delay increases risk of precedent effect ("if llm_extract can do it, so can I")
- Strategic direction pre-approved in 4-round CTO review discussion

**Override authority**: Life Index Developer (project author)
**Override date**: 2026-05-14
**Override scope**: §5.2 cooldown only; all other CHARTER provisions remain in force

## Source Evidence

| Document | Path | Role |
|---|---|---|
| CTO Review v2 | `.opus-learnings/CTO_Review_2026-05-14.md` | Full risk landscape + §1.5 violation discovery + §1.9 rationale |
| Implementation Handoff | `.opus-learnings/Handoff_Charter_19_Implementation.md` | 7-phase execution plan + decision authority + constraints |
| RFC | `docs/rfc/RFC-2026-05-14-agent-native-module-principle.md` | Formal proposal with user override record |

## Opus Review Notes

Key excerpts from CTO Review v2:

> "当前 codebase 缺少一条'agent-native 模块默认形态'的不变量，导致 CHARTER §1.5 已被既存代码违反，且未来所有高级模块都缺少防护栏。"

> "Life Index 是 agent ecosystem 的一部分，不是 LLM 应用。"

> "§1.9 的入宪相当于给 Roadmap 上每一个模块预先装上防护栏。"

## Implementation Scope

### Phase 0 (Complete)
- CHARTER.md: version bumped to v1.3.0, revision count to 3
- New §1.9 inserted after §1.8
- §3.3 generalized from search-only to all L3 modules
- §4.1 appended with 3 anti-pattern bullets
- Footer revision 3 added
- RFC created: `docs/rfc/RFC-2026-05-14-agent-native-module-principle.md`
- This history archive created

### Phase 1-6 (Pending)
See RFC §7 Phased Implementation Plan for details.

## Verification

- [x] CHARTER.md contains §1.9
- [x] CHARTER.md version is v1.3.0
- [x] CHARTER.md revision count is 3
- [x] RFC file exists and cross-references CHARTER
- [x] History file exists and cross-references RFC
- [x] No code or tests modified in Phase 0
- [x] No commit or push performed

---

*Phase 0 implemented by 码农B_Kimi on 2026-05-14.*
*Pending lead reviewer sign-off before commit/push.*
