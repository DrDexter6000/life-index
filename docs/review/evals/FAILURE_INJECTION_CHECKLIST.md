# Failure Injection Checklist

> **Document role**: Checklist for validating degraded behavior, recovery expectations, and truth-preserving error handling during Phase 2 review work
> **Audience**: Reviewers, implementers, and future agents working from the review bundle in `docs/review/`
> **Authority**: Review-scoped evaluation artifact; does not redefine runtime SSOT
> **Related artifacts**: `docs/review/execution/WRITE_FAILURE_SEMANTICS.md`, `docs/review/execution/WEATHER_EDIT_BOUNDARY.md`, `docs/review/execution/INDEX_CONSISTENCY_POLICY.md`, `docs/review/evals/WORKFLOW_EVAL_CASES.md`, `docs/review/evals/RETRIEVAL_EVAL_CASES.md`

---

## 1. Purpose

This checklist is for deliberately stress-testing the system’s behavior when parts of the journal workflow degrade.

The goal is **not** simply to see whether something fails.

The goal is to verify whether the system preserves the correct distinctions under failure:

- unsaved vs saved
- saved vs saved-but-unconfirmed
- saved vs saved-but-not-searchable-yet
- edit succeeded vs weather alignment incomplete
- retrieval failure vs empty result vs stale index state

---

## 2. How to use this checklist

For each failure mode:

1. Inject or simulate the failure condition
2. Observe tool output and caller behavior
3. Check whether the system preserves the correct contract distinctions
4. Mark pass/fail
5. Record gaps between current behavior and review-phase policy

This file is intentionally implementation-agnostic. It defines what should be checked, not the exact low-level test harness.

---

## 3. Checklist

## A. Weather capability failures

### FI-01 — Weather lookup fails during write enrichment

- [ ] Simulate weather lookup failure during a write flow that would normally attempt weather enrichment
- [ ] Verify the system distinguishes core journal durability from weather enrichment completeness
- [ ] Verify the system does **not** automatically describe the whole write as failed if the journal was durably saved
- [ ] Verify the system can describe the outcome as saved-with-degraded-enrichment or equivalent

### FI-02 — Weather lookup fails during edit-location correction flow

- [ ] Simulate a workflow where the user wants location + weather updated together
- [ ] Break the weather lookup step before the edit fully completes
- [ ] Verify the system preserves the distinction between journal edit status and weather refresh status
- [ ] Verify the system does **not** falsely imply that weather is current if it was not refreshed

### FI-03 — Caller skips weather refresh on location edit

- [ ] Simulate a location-only edit where semantic alignment with weather matters
- [ ] Verify the review contract flags this as a weather/edit boundary issue rather than silently pretending full semantic alignment exists
- [ ] Verify any resulting state is described as successful edit + incomplete field alignment, not as automatic full success

---

## B. Write durability vs side-effect failures

### FI-04 — Core write failure before journal durability

- [ ] Simulate a failure before the journal file is durably written
- [ ] Verify the system reports this as a real write failure
- [ ] Verify no downstream success language implies the journal exists when it does not

### FI-05 — Index side-effect failure after durable write

- [ ] Simulate successful journal durability followed by failure in index update side effects
- [ ] Verify the system preserves “journal saved” separately from “indexing incomplete”
- [ ] Verify the system does **not** collapse this into generic write failure
- [ ] Verify the system leaves conceptual room for reconcile/rebuild follow-up

### FI-06 — Confirmation pending after successful write

- [ ] Simulate a write flow that returns `needs_confirmation`
- [ ] Verify the system does not stop at `success: true`
- [ ] Verify the state is described as saved-but-unconfirmed rather than unsaved

---

## C. Retrieval-layer degradation

### FI-07 — Search stack failure

- [ ] Simulate retrieval tool failure or a broken retrieval sub-layer
- [ ] Verify the system distinguishes retrieval failure from empty result
- [ ] Verify the system does not falsely say “nothing found” when the real issue is retrieval degradation

### FI-08 — Empty result with healthy retrieval

- [ ] Simulate a query that truly has no useful matches
- [ ] Verify the system reports an honest empty-result outcome
- [ ] Verify the system does **not** inflate this into system failure

### FI-09 — Stale search visibility after successful write

- [ ] Simulate a journal that exists durably but is not yet visible through search
- [ ] Verify the system preserves the distinction between source truth and retrieval visibility
- [ ] Verify the system does not describe the journal as missing if only index freshness is degraded

---

## D. Metadata / FTS / vector inconsistency

### FI-10 — Metadata layer stale relative to source journal

- [ ] Simulate a case where the journal file is updated but metadata-related retrieval layers lag behind
- [ ] Verify the system can still reason about source truth vs metadata freshness
- [ ] Verify the problem is classified as repairable drift rather than journal loss

### FI-11 — FTS/content search layer stale or inconsistent

- [ ] Simulate a case where content search does not reflect the latest journal text
- [ ] Verify the system does not equate FTS inconsistency with missing durable file state
- [ ] Verify the state is treated as retrieval/index inconsistency

### FI-12 — Vector/semantic layer stale or unavailable

- [ ] Simulate semantic/vector retrieval degradation while exact/keyword retrieval still works
- [ ] Verify the system preserves the difference between semantic weakness and total retrieval failure
- [ ] Verify concept-search quality degradation is not described as journal disappearance

---

## E. Manual file edits and recovery paths

### FI-13 — Manual source edit not yet reflected in search

- [ ] Simulate a manual journal file change outside the normal tool path
- [ ] Verify the system treats source file state as primary truth
- [ ] Verify search lag is described as stale visibility rather than source absence

### FI-14 — Recovery/reconcile path needed after manual edits

- [ ] Simulate a case where manual edits require rebuild/reconcile follow-up
- [ ] Verify the system leaves room for explicit recovery action rather than pretending the system is fully current
- [ ] Verify rebuild/reconcile is treated as an operational recovery path, not as proof of prior write failure

---

## F. Cross-boundary truthfulness checks

### FI-15 — Saved vs failed language correctness

- [ ] Review degraded scenarios and verify the system never says “write failed” when the journal is durably present
- [ ] Verify the system never says “all good” when known degradation remains

### FI-16 — Edit vs write misclassification under failure

- [ ] Simulate ambiguous requests under degraded conditions
- [ ] Verify the system still clarifies workflow intent rather than compensating by guessing the wrong tool path

### FI-17 — Confirmation vs failure confusion check

- [ ] Verify that pending confirmation is never described as equivalent to unsaved state
- [ ] Verify correction follow-up remains distinct from storage failure

### FI-18 — Retrieval visibility vs source truth confusion check

- [ ] Verify the system never equates “not found in search” with “journal does not exist” unless source truth has actually failed

---

## 4. Summary gate

Use this checklist to answer the following question:

> Under degraded conditions, does the system preserve truth about **what succeeded**, **what is incomplete**, and **what is repairable**?

The review should only be considered strong if the answer is consistently **yes** across weather, write, edit, retrieval, and index-drift scenarios.

---

## 5. Minimum expected outputs from a failure review run

After using this checklist, a reviewer should be able to produce:

- a list of failure modes that are handled truthfully
- a list of failure modes that currently collapse too many states together
- a list of failure modes that need better runtime signaling or repair commands
