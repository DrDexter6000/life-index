# Baseline Execution Plan

> **Document role**: Stepwise plan for running baseline diagnostic validation without changing code
> **Audience**: Project Owner, reviewers, implementers, and future agents
> **Authority**: Review-scoped execution plan for evaluation work only; does not authorize implementation changes by itself
> **Primary constraint**: This plan is for **assessment-first execution**. It is not a code-change plan.

---

## 1. Objective

Run a baseline diagnostic pass that answers:

- what the current system demonstrably does
- where it aligns with the review bundle
- where it diverges
- where it remains unknown

without changing implementation behavior during the assessment.

---

## 2. Non-goals

This plan must **not** be used to:

- refactor code
- “quick-fix” failures during evaluation
- rewrite tools to satisfy eval cases on the fly
- silently update runtime SSOT because a review doc says something better

If a gap is found, record it. Do not fix it inside the baseline run.

---

## 3. Inputs required before starting

### Review contracts

- `docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md`
- `docs/review/execution/CANONICAL_WORKFLOWS.md`
- `docs/review/execution/WRITE_FAILURE_SEMANTICS.md`
- `docs/review/execution/WEATHER_EDIT_BOUNDARY.md`
- `docs/review/execution/INDEX_CONSISTENCY_POLICY.md`

### Eval corpus

- `docs/review/evals/WORKFLOW_EVAL_CASES.md`
- `docs/review/evals/RETRIEVAL_EVAL_CASES.md`
- `docs/review/evals/FAILURE_INJECTION_CHECKLIST.md`
- `docs/review/evals/BASELINE_EVALUATION_REVIEW.md`

### Existing evidence sources

- code in `tools/`
- current unit tests
- current e2e runner
- existing project docs (`docs/API.md`, `docs/ARCHITECTURE.md`, `SKILL.md`)

---

## 4. Output required from the baseline run

The baseline run should produce one or more result artifacts that clearly separate:

1. **Confirmed code-backed behavior**
2. **Contract-aligned but not yet fully proven behavior**
3. **Observed gaps**
4. **Unknown / not yet validated areas**

Recommended result document:

- `docs/review/evals/BASELINE_RUN_RESULTS.md`

If multiple runs happen later, supersede old result docs rather than rewriting history.

---

## 5. Execution phases

## Phase A — Evidence inventory

### Goal

Confirm what evidence already exists before trying to evaluate behavior.

### Tasks

- inventory relevant implementation files
- inventory relevant tests
- inventory relevant docs and current review contracts
- classify each major claim as:
  - code-backed
  - doc-backed
  - contract-only
  - unknown

### Output

- an evidence table in the baseline result doc

---

## Phase B — Workflow diagnostic pass

### Goal

Assess workflow routing, clarification, confirmation, and degraded-state handling against the workflow eval corpus.

### Input

- `docs/review/evals/WORKFLOW_EVAL_CASES.md`

### Method

For each workflow case, record:

- expected workflow
- expected tool path
- whether current code/tests provide direct support
- whether the case is only contract-backed
- whether current evidence is insufficient

### Output categories

- Supported now
- Plausibly supported but not directly proven
- Not yet validated

---

## Phase C — Retrieval diagnostic pass

### Goal

Assess search architecture readiness against the retrieval eval corpus.

### Input

- `docs/review/evals/RETRIEVAL_EVAL_CASES.md`

### Method

For each retrieval pattern, record:

- whether the required retrieval mode exists in implementation
- whether quality is actually proven or merely assumed
- whether a concrete dataset is still needed

### Important rule

Do not confuse:

- retrieval capability exists
with
- retrieval quality is proven

---

## Phase D — Failure/degraded-state diagnostic pass

### Goal

Assess whether the current system appears capable of preserving truthful distinctions under failure.

### Input

- `docs/review/evals/FAILURE_INJECTION_CHECKLIST.md`

### Method

For each failure class, record:

- direct code/test evidence if any
- policy-only support if any
- whether current behavior is unknown without explicit injected testing

### Important rule

Do not mark a failure scenario as “handled” solely because a checklist item exists.

---

## Phase E — Gap summary and prioritization

### Goal

Summarize what matters most before any implementation work begins.

### Required categories

- Highest-confidence strengths
- Highest-risk unknowns
- Contract/code mismatches
- Areas that are evaluation-ready vs not yet evaluation-ready

### Important rule

This phase may recommend **what to validate next**, but must not start changing code.

---

## 6. Evaluation recording format

Use the following status vocabulary:

| Status | Meaning |
|:---|:---|
| Confirmed | Directly supported by code/tests/evidence |
| Supported by docs | Strongly documented, but not directly proven in runtime evidence |
| Contract-only | Present in review contract, not yet proven |
| Unknown | Current evidence is insufficient |
| Divergent | Current evidence appears to conflict with review expectation |

This vocabulary prevents the baseline from pretending certainty it does not have.

---

## 7. Minimum acceptance criteria for a valid baseline run

The baseline run should not be considered valid unless it:

- [ ] explicitly separates code-backed vs contract-only claims
- [ ] covers workflow, retrieval, and failure domains
- [ ] records at least one concrete evidence source for each major confirmed claim
- [ ] refuses to overstate semantic quality or failure resilience when evidence is weak
- [ ] records gaps without fixing them during the same pass

---

## 8. Escalation rule

If the baseline run encounters a major ambiguity, use this rule:

- clarify documentation interpretation first
- inspect code/tests second
- record the ambiguity if still unresolved
- do **not** patch implementation during the diagnostic pass

---

## 9. What should happen after the baseline run

Only after the baseline run is recorded should the project decide whether to:

1. continue with more validation work
2. refine review contracts
3. start targeted implementation changes

This preserves the intended order from the roadmap:

1. define contracts
2. define evals
3. run baseline diagnosis
4. only then fix gaps

---

## 10. Bottom line

This plan exists to stop the project from skipping directly from “good ideas in documents” to “random implementation changes.”

The purpose of the baseline run is simple:

> **Make the current truth visible before changing the system.**
