# Index Consistency Policy

> **Document role**: Define how journal durability, index consistency, and search visibility should relate during review-phase execution planning
> **Audience**: Project Owner, reviewers, implementers, and future agents
> **SSOT relationship**: This document is review-scoped execution guidance. Runtime interface truth remains in `docs/API.md`, workflow truth remains in `SKILL.md`, architecture truth remains in `docs/ARCHITECTURE.md`, and implementation truth remains in code.
> **Scope for this first cut**: The semantic contract between journal write success and downstream index/search visibility

---

## 1. Why this document exists

Life Index currently combines several concerns into the user-visible impression of “the write worked”:

- journal durability
- metadata/index side effects
- retrieval visibility

If these are not separated explicitly, the product will keep drifting into one of two bad extremes:

1. **Over-coupled contract**
   - “If any index side effect fails, the whole write failed.”

2. **Over-loose contract**
   - “If the file exists, nothing else matters.”

Neither is a good long-term rule. The system needs a clearer policy for how durable storage and search visibility relate.

---

## 2. Primary principle

For Phase 2 review purposes, the primary product rule is:

> **Journal durability is the primary success condition. Search/index completeness is secondary, but still operationally important.**

This means:

- the user’s most important guarantee is that the journal was safely written
- search visibility should be improved and preserved aggressively
- but search/index incompleteness should not automatically erase durable capture unless the product explicitly chooses that contract later

---

## 3. Index consistency vocabulary

This document uses three policy classes.

### A. Synchronous-required

If this part fails, the workflow should not claim the higher-level operation is fully complete.

### B. Best-effort

The system should try to complete this part in the current operation, but failure does not automatically erase the success of the primary durable outcome.

### C. Repairable

If this part fails or falls behind, the system must preserve enough truth to recover it later via rebuild, reconcile, or targeted follow-up.

---

## 4. Contract layers

To avoid confusion, the system should conceptually separate three layers:

### Layer 1 — Durable journal state

Questions answered here:

- Does the journal file exist durably?
- Was the write itself successful?

This is the primary product guarantee.

### Layer 2 — Metadata/index state

Questions answered here:

- Are topic/project/tag/vector/search side effects up to date?
- Can the system trust that downstream retrieval views reflect the latest journal state?

This is operationally important, but secondary to Layer 1.

### Layer 3 — User-visible retrieval state

Questions answered here:

- Will the journal be immediately discoverable through search paths?
- Is the retrieved view current or lagging behind the source file?

This depends on Layer 2 and should not be confused with Layer 1.

---

## 5. Provisional policy decisions

For the current review contract, the following policy is adopted.

## 5.1 Journal durability

### Classification

- **Synchronous-required**

### Meaning

If the durable journal file is not safely written, the write did not succeed.

### Consequence

- no index or search success can compensate for missing durable storage

---

## 5.2 Immediate write-side index updates

### Classification

- **Best-effort in the current review contract**

### Meaning

The system should attempt to update downstream indexes as part of the write flow, but failure of those side effects should not automatically mean “the journal was not saved.”

### Consequence

- write success and index freshness must be reported separately when they diverge

---

## 5.3 Search visibility after write

### Classification

- **Repairable**

### Meaning

If the journal is durably written but not yet correctly visible in search, that is a recoverable operational inconsistency, not automatically a storage failure.

### Consequence

- the system must preserve the ability to rebuild, reconcile, or otherwise recover search visibility later

---

## 5.4 Search visibility after edit

### Classification

- **Repairable**, with strong preference for immediate update when possible

### Meaning

If a journal edit succeeds but retrieval layers lag behind, the edit itself may still be valid while the search state is temporarily stale.

### Consequence

- the system must not confuse stale retrieval with missing journal state

---

## 5.5 Index rebuild / reconcile operations

### Classification

- **Repairable recovery path**

### Meaning

These operations are the explicit operational escape hatch when Layer 2/Layer 3 drift away from Layer 1.

### Consequence

- rebuild and reconcile behavior should be treated as a formal recovery capability, not an accidental developer-only side effect

---

## 6. Policy table

| Concern | Policy class | Why |
|:---|:---:|:---|
| Durable journal file creation | Synchronous-required | Core success condition |
| Write-side index update attempt | Best-effort | Important side effect, but not the same as durable capture |
| Edit-side index update attempt | Best-effort | Important for freshness, but not identical to edit durability |
| Search visibility freshness | Repairable | Retrieval may lag while source truth remains valid |
| Full rebuild / reconcile capability | Repairable recovery path | Needed when side effects drift from source truth |

---

## 7. Caller-facing reporting rules

The caller/agent should preserve these distinctions in later workflow behavior.

### Case A — Saved and indexed

Use when:

- journal durability succeeded
- current index/update side effects also succeeded sufficiently

Caller should say, in effect:

- the journal is saved and current retrieval state should reflect it

### Case B — Saved, but indexing is incomplete

Use when:

- journal durability succeeded
- index/update side effects are degraded or incomplete

Caller should say, in effect:

- the journal is saved, but search visibility may lag until repair/reconcile work completes

### Case C — Search cannot find it yet, but source truth exists

Use when:

- the journal file exists
- retrieval state is stale, incomplete, or degraded

Caller should say, in effect:

- the journal exists, but search/index state is not fully current yet

### Case D — Write failed at the durable layer

Use when:

- the journal file was not durably written

Caller should say, in effect:

- the journal was not successfully saved

---

## 8. Operational anti-confusion rules

### Rule 1

Do not treat “not searchable right now” as proof that the journal does not exist.

### Rule 2

Do not treat “file exists” as proof that every index layer is current.

### Rule 3

Do not report “write failed” when the durable journal exists but search visibility is degraded.

### Rule 4

Do not report “all good” when retrieval state is known to be stale or incomplete.

---

## 9. Relationship to write failure semantics

This document extends `docs/archive/review-2026-03/WRITE_FAILURE_SEMANTICS.md`.

That document establishes:

- durable write is primary
- confirmation is non-blocking
- index side effects are repairable by default

This document sharpens the indexing part of that model by adding:

- a layered view of durable source truth vs index truth vs retrieval visibility
- a best-effort / repairable contract for index-related freshness

---

## 10. What this document does not settle yet

This document does **not** yet settle:

- the exact runtime response schema that should expose index lag to callers
- whether some specific index layers should later be promoted from best-effort to synchronous-required
- the exact operational UI/CLI command surface for reconcile/rebuild follow-up

These are later design decisions and should be informed by Phase 2 evaluation work, not guessed prematurely.

---

## 11. Practical implication for future work

Future implementation and review work should assume this ordering of truth:

1. **Source-of-truth journal file**
2. **Index/update freshness**
3. **Search visibility**

When these diverge, the system should preserve the divergence explicitly rather than hiding it behind an oversimplified success/failure label.
