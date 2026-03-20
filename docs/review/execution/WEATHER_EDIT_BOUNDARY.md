# Weather / Edit Boundary

> **Document role**: Define the current boundary between weather handling and edit workflows during Phase 1 review work
> **Audience**: Project Owner, reviewers, implementers, and future agents
> **SSOT relationship**: This document is review-scoped execution guidance. Runtime interface truth remains in `docs/API.md`, workflow truth remains in `SKILL.md`, weather-flow truth remains in `references/WEATHER_FLOW.md`, and architecture truth remains in `docs/ARCHITECTURE.md`.
> **Scope for this first cut**: Location-weather coordination across `write_journal`, `edit_journal`, and `query_weather`
> **状态**: 部分采纳 — 核心 caller-facing contract 已上提到 `docs/API.md` 与 `references/WEATHER_FLOW.md`；本文件保留 review reasoning 与开放问题

---

## 1. Why this document exists

The project currently has an intentional but easy-to-misread asymmetry:

- `write_journal` includes weather-related enrichment behavior in its write path
- `edit_journal` does **not** automatically refresh weather when location changes
- `query_weather` provides capability, but not orchestration or persistence

This is workable, but only if the boundary is made explicit. Otherwise, future callers will assume one of two incorrect models:

1. “Location and weather always stay in sync automatically”
2. “Weather is always a separate concern and never part of write flow”

Both are incomplete descriptions of the current system.

---

## 2. Current canonical boundary

For Phase 1 review purposes, the current boundary is:

### A. `write_journal`

- may participate in weather enrichment during new-entry creation
- may return a result that still requires user confirmation or correction

### B. `edit_journal`

- owns deterministic mutation of an existing journal
- does **not** own automatic weather refresh when location changes

### C. `query_weather`

- owns weather lookup capability
- does not own journal mutation
- does not own orchestration of a full correction flow

### D. Agent / caller

- owns the multi-step reasoning about when a location change should imply weather refresh
- owns the orchestration of “lookup weather first, then edit journal” when required
- owns clarification and user-facing confirmation around weather correctness

---

## 3. Core rule

Changing `location` in an existing journal does **not** automatically guarantee that `weather` is refreshed by the system.

Therefore:

> **If the user expects location and weather to remain semantically aligned during edit flow, the caller must orchestrate that alignment explicitly.**

This rule should remain explicit until the product intentionally changes the contract.

---

## 4. Boundary decisions for the current contract

## 4.1 New journal creation

### Contract

During new-entry creation, weather may be treated as part of the write-side enrichment flow.

### Implication

- the write path may attempt to enrich the entry with weather context
- the resulting weather/location values may still require user confirmation

### Agent obligation

- if the tool returns `needs_confirmation`, do not assume the weather/location outcome is fully accepted yet

---

## 4.2 Editing an existing journal

### Contract

During edit flow, `edit_journal` should be treated as a deterministic mutation tool only.

It does **not** implicitly perform:

- weather lookup
- location normalization business logic equivalent to write-side enrichment
- coupled-field orchestration

### Implication

- changing `location` through `edit_journal` alone may leave `weather` stale if the caller does nothing else

### Agent obligation

If semantic alignment matters, the agent must:

1. determine that a location change should imply weather refresh
2. call `query_weather`
3. call `edit_journal` with both the updated location and weather fields

---

## 4.3 Standalone weather lookup

### Contract

`query_weather` is a capability tool, not a journal state manager.

### Implication

- successful weather lookup alone does not update any journal
- weather lookup failure alone does not mean journal write/edit failed unless the caller has defined it as a blocking precondition for that workflow

---

## 5. Current operational asymmetry: accepted for now

The following asymmetry is accepted in Phase 1 review work:

| Context | Current behavior | Owner of orchestration |
|:---|:---|:---:|
| New write | Weather may be enriched inside the write path | Mixed today, caller still owns confirmation |
| Existing edit | Weather is not auto-refreshed | Caller / agent |
| Standalone weather | Returns capability output only | Caller / agent |

This asymmetry is acceptable **for now**, provided that:

- it is documented clearly
- agents do not assume edit flow behaves like write flow
- future design changes are made intentionally rather than by drift

---

## 6. Caller obligations

## 6.1 When editing location

If the user changes location and also expects weather correctness, the caller must not stop at a bare `edit_journal --set-location` style operation.

Caller should:

1. determine whether weather should be refreshed
2. retrieve weather via `query_weather`
3. update the journal with both location and weather values

## 6.2 When weather lookup fails during correction flow

Caller should preserve the distinction between:

- journal edit status
- weather refresh status

That means:

- do not silently imply weather is correct when refresh failed
- do not necessarily imply the whole edit failed if the journal mutation itself could still be handled meaningfully
- communicate the degraded state honestly

## 6.3 When write flow weather is rejected by the user

Caller should treat rejection as a correction flow, not as proof that the original journal file was never written.

---

## 7. Warning / validation stance for Phase 1

This document makes a narrow Phase 1 choice:

### A. Documentation warning: yes

The current contract should explicitly warn implementers and agents that location edits do not auto-refresh weather.

### B. Runtime validation change: not decided yet

This review document does **not** yet require an immediate code/API change such as:

- forcing weather when location changes
- auto-calling weather lookup inside edit flow
- rejecting location-only edits

Reason:

- those are implementation/product decisions that should be made deliberately after Phase 1 boundary clarification, not implicitly during documentation work

---

## 8. Failure semantics at this boundary

### A. Write flow weather issue

- if the journal is durably written but weather is still under confirmation/correction, the write should not be retroactively treated as unsaved

### B. Edit flow weather issue

- if location is changed without refreshed weather, the edit may still have occurred, but semantic alignment between fields may be incomplete

### C. Weather lookup issue

- weather capability failure should not automatically be collapsed into “journal operation failed” unless that specific workflow explicitly makes weather a blocking precondition

---

## 9. Recommended caller phrases (conceptual)

These are conceptual reporting patterns, not final UX copy.

### Case A — Write succeeded, weather still needs confirmation

- “The journal has been saved, but please confirm whether the auto-filled weather/location is correct.”

### Case B — Edit succeeded, but weather was not refreshed

- “The location update is applied, but weather has not been refreshed yet.”

### Case C — Weather lookup failed during correction flow

- “The journal state and the weather refresh state are not fully aligned yet; weather lookup still needs follow-up.”

---

## 10. What this document does not settle yet

This document does **not** yet settle:

- whether `edit_journal` should eventually surface a warning when location changes without weather
- whether write flow should keep weather enrichment inside the tool path long-term
- whether weather normalization/lookup should be refactored into a more uniform orchestration model

Those questions remain open and should be decided later based on:

- Phase 1 artifact alignment
- Phase 2 evaluation findings
- actual product experience tradeoffs

---

## 11. Relationship to other Phase 1 artifacts

- `docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md` defines which tool owns which responsibility
- `docs/review/execution/CANONICAL_WORKFLOWS.md` defines how write and edit branch operationally
- `docs/review/execution/WRITE_FAILURE_SEMANTICS.md` defines how to separate unsaved, saved-but-unconfirmed, and saved-but-repairable states
