# Write Failure Semantics

> **Document role**: Classify write-path steps as blocking, non-blocking, or repairable during Phase 1 review work
> **Audience**: Project Owner, reviewers, implementers, and future agents
> **SSOT relationship**: This document is review-scoped execution guidance. Runtime interface truth remains in `docs/API.md`, workflow truth remains in `SKILL.md`, and architecture truth remains in `docs/ARCHITECTURE.md`.
> **Scope for this first cut**: The current `write_journal` path and its immediate caller-facing implications

---

## 1. Why this document exists

The current write flow mixes several kinds of work into one user-facing outcome:

- core journal creation
- enrichment behavior
- index side effects
- confirmation follow-up

If these are not separated semantically, future maintainers will keep asking the wrong question:

> “Did the write succeed?”

when the system actually needs to distinguish:

1. Did the core journal write succeed?
2. Did enrichment complete?
3. Did index side effects complete?
4. Does the user still need to confirm or correct some values?

This document narrows that semantic boundary for Phase 1.

---

## 2. Classification model

Every write-path step should be classified as one of three types:

### A. Blocking

If this step fails, the system must not claim that the journal write succeeded.

### B. Non-blocking

If this step fails, the core journal write may still be considered successful, but the user/caller must not be misled about the degraded state.

### C. Repairable

If this step fails or remains incomplete, the system may proceed with the write outcome, provided the incomplete part can be reconciled later through explicit follow-up work.

---

## 3. Core semantic rule

The final contract should preserve a strict distinction between these three states:

1. **Write failed**
2. **Write succeeded but enrichment/side effects are incomplete**
3. **Write succeeded and the user still owes confirmation/correction**

These states must not be collapsed into a single generic “success” or “failure” message in future workflow design.

---

## 4. Proposed write-path classification

## 4.1 Blocking steps

These are the steps that should be treated as **blocking** in the write contract.

### A. Minimum payload viability

The agent must be able to prepare a payload that satisfies the write flow’s minimum required input.

Reason:

- without a viable payload, the tool cannot safely perform deterministic write behavior

Contract effect:

- if the caller cannot construct the minimum payload, the workflow must clarify before tool invocation

### B. Core validation owned by the write tool

Validation that protects the correctness of the journal file itself is blocking.

Reason:

- if the input cannot be validated for the actual write operation, the system must not claim that the journal exists correctly

### C. Journal path / sequence preparation required for file creation

If the system cannot determine where/how to write the file safely, the write must fail.

Reason:

- file identity and path are part of the write itself, not an optional side effect

### D. Atomic file creation / replacement

The atomic file write is blocking.

Reason:

- the journal’s durable existence is the core success condition of the workflow

### E. Any deterministic step without which the journal file is not durably present

This includes the minimum write-owned work necessary to ensure the journal is actually stored.

---

## 4.2 Non-blocking steps

These are the steps that should not define the success of the core journal write by themselves.

### A. User-facing confirmation completion

If the journal file has already been written but the system still needs user confirmation about auto-filled values, that is **not** the same as write failure.

Reason:

- confirmation belongs to conversational correctness, not the durable existence of the file itself

Required reporting behavior:

- do not say “write failed” if the file is already saved
- instead distinguish “write succeeded, confirmation still needed”

### B. Optional enrichment completeness

Enrichment-like behavior that improves the entry but is not the same as durable journal creation should be treated as non-blocking unless the product later explicitly decides otherwise.

Current examples that appear enrichment-like in the present design:

- weather auto-fill
- extra derived metadata that is not the minimum file viability condition

Reason:

- a missing enrichment result should not automatically erase the fact that the journal itself may already exist safely

### C. Conversational follow-up after successful file creation

If the system still needs to ask the user whether an auto-filled value is correct, this is non-blocking from the storage perspective.

---

## 4.3 Repairable steps

These are the steps that may be incomplete after a successful journal write, but can be reconciled later.

### A. Index consistency side effects

Search/index side effects should be treated as repairable unless and until the project explicitly chooses a stricter product contract.

This includes, conceptually:

- topic/project/tag side effects
- vector index side effects
- any other downstream search visibility side effects

Reason:

- the user’s primary success condition is “my journal was saved”
- full search visibility is important, but secondary to durable data capture

Required reporting behavior:

- distinguish “journal saved but indexing incomplete” from “journal failed to save”
- make room for later repair / reconcile behavior

### B. Deferred correction after successful write

If auto-filled values later need correction, the journal may still be valid while some parts remain operationally incomplete.

Reason:

- the original write and the later cleanup are related, but not identical success conditions

---

## 5. Step-by-step write semantic table

| Write-path step | Classification | Why |
|:---|:---:|:---|
| Agent determines this is a write request | Blocking (pre-tool) | Wrong workflow choice means wrong operation |
| Agent prepares minimum viable payload | Blocking (pre-tool) | Tool cannot safely write without it |
| Write tool validates write-owned input | Blocking | Invalid core write input must stop write success |
| Journal path / sequence preparation | Blocking | Required for durable file creation |
| Atomic file write | Blocking | Core success condition |
| Attachment processing required for the actual write payload | Context-dependent, treat as Blocking if required for requested write | If the requested write meaning depends on it, write is incomplete without it |
| Weather enrichment | Non-blocking by default in this review contract | Helpful enrichment, not the same as durable journal storage |
| Return of `needs_confirmation` | Non-blocking | Indicates follow-up needed, not write failure |
| Topic/project/tag/vector indexing | Repairable by default in this review contract | Search visibility should not erase durable capture |
| Later correction of auto-filled values | Repairable / follow-up | Journal may exist even if enrichment needs cleanup |

---

## 6. Caller-facing reporting rules

The caller/agent should preserve these distinctions in future workflow behavior.

### Case A — Core write failed

Use when:

- the journal file was not durably created
- a blocking precondition or blocking write step failed

Caller should say, in effect:

- the journal was **not** successfully saved

### Case B — Core write succeeded, but confirmation is still required

Use when:

- the journal file exists
- the tool signals follow-up confirmation is still needed

Caller should say, in effect:

- the journal is saved, but confirmation/correction is still needed

### Case C — Core write succeeded, but repairable side effects are incomplete

Use when:

- the journal file exists
- indexing or related repairable side effects are incomplete

Caller should say, in effect:

- the journal is saved, but some downstream visibility/repair work remains

---

## 7. Provisional contract decisions made here

For Phase 1 review purposes, this document makes these provisional choices:

1. **Durable journal storage is the primary success condition**
2. **User confirmation is not itself a blocking storage condition**
3. **Index/search side effects should be modeled as repairable by default**
4. **Enrichment should not automatically be treated as equivalent to durable write success**

These decisions are intentionally conservative and aligned with the project’s design bottom line:

- reliability over complexity
- durable user data over ancillary automation

---

## 8. What this document does not settle yet

This document does **not** yet settle:

- the exact runtime response schema needed to represent these distinctions in tool output
- whether any current implementation should be refactored immediately to match this semantic model
- whether some enrichment behavior should later be upgraded from non-blocking to blocking in narrow product-defined cases

Those are later decisions and should be informed by the remaining Phase 1/2 artifacts rather than guessed here.

---

## 9. Relationship to other Phase 1 artifacts

- `docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md` explains who owns which responsibilities
- `docs/review/execution/CANONICAL_WORKFLOWS.md` explains when write flow branches into clarification, confirmation, or failure paths
- `docs/review/execution/WEATHER_EDIT_BOUNDARY.md` should later clarify weather/location coupling in more detail
