# Fix Candidates and Priorities

> **Document role**: Review-scoped planning artifact for targeted fix candidates after three baseline diagnostic passes
> **Audience**: Project Owner, reviewers, implementers, and future agents
> **Authority**: Planning-only artifact. Does not change code, does not redefine runtime SSOT, and does not convert unvalidated hypotheses into implementation tasks.
> **Primary constraint**: This document ranks only **evidenced candidates**. Unknowns remain in investigation, not in the immediate fix queue.

---

## 1. Planning rule for this document

This document follows the sequencing discipline established after the baseline passes:

1. **Evidence gate first**
2. **User impact second**
3. **Blast radius third**

This means:

- only issues with sufficiently strong evidence enter the ranked fix queue
- user-facing harm outranks engineering neatness
- between similar issues, choose the narrower and safer change surface first

This document is therefore **triage, not solution design**.

---

## 2. Evidence tiers used here

### Tier A — Confirmed

Directly confirmed by runtime observation, logs, repeated baseline findings, or clear concrete mismatch.

### Tier B — Strongly indicated

Strongly supported by code + docs + baseline synthesis, but missing one final runtime confirmation.

### Tier C — Hypothesis / not yet validated

Still too uncertain to enter the immediate fix queue.

### Queue rule

- **Immediate fix queue**: Tier A first, then Tier B if appropriately bounded
- **Investigation queue**: Tier C only

---

## 3. Immediate fix queue (validated candidates)

## Fix Candidate 1 — `query_weather` package-surface / test-readiness mismatch

### Priority

- **P0**

### Status

- **Completed**

### Evidence tier

- **Tier A — Confirmed**

### Why it is in the fix queue

This is the clearest, narrowest, and most directly evidenced issue found across the baseline runs.

### Evidence

- `docs/review/evals/BASELINE_RUN_RESULTS.md` first pass: full `tests/unit` collection blocked on `tests/unit/test_query_weather.py`
- third pass: weather CLI path is healthy, write-side weather helper path is healthy, but `tests/unit/test_query_weather.py` still fails during collection
- `tests/unit/test_query_weather.py` imports `main` from `tools.query_weather`
- `tools/query_weather/__init__.py` does not export `main`
- `tools/query_weather/__main__.py` defines `main`

### Why it matters

- blocks a clean unit-test baseline
- weakens project confidence disproportionally relative to the narrow fault boundary
- is already localized as a **module-surface / test-readiness issue**, not a broad feature-health issue

### Scope touched

- `tools/query_weather/` package surface and/or test import surface

### Blast radius

- **Low**

### Why now

- high evidence
- high leverage for test readiness
- narrow change boundary

### What must NOT be bundled into this fix

- no weather API refactor
- no write-side weather behavior changes
- no weather/edit contract redesign

---

## Fix Candidate 2 — `write_journal` result-state signaling does not yet fully match review contract

### Priority

- **P1**

### Status

- **Completed**

### Evidence tier

- **Tier B — Strongly indicated**

### Why it is in the fix queue

The review bundle repeatedly requires the system to preserve distinctions such as:

- write failed
- write succeeded but confirmation still needed
- write succeeded but repairable/index-related side effects remain

The baseline evidence shows this distinction is central to the project’s intended truth model, while runtime proof of distinct signaling remains incomplete.

### Evidence

- `docs/review/execution/WRITE_FAILURE_SEMANTICS.md`
- `docs/review/execution/INDEX_CONSISTENCY_POLICY.md`
- `docs/review/evals/BASELINE_EVALUATION_REVIEW.md`
- `docs/review/evals/BASELINE_RUN_RESULTS.md` repeatedly records weaker proof around runtime separation of durability, index freshness, and retrieval visibility

### Why it matters

- this is a central contract issue, not a cosmetic one
- affects agent truthfulness and future workflow correctness
- influences how later diagnostics and fixes can be interpreted

### Scope touched

- `write_journal` result signaling surface
- possibly adjacent caller expectations

### Blast radius

- **Medium**

### Why now

- strong contract importance
- bounded enough to consider after the P0 test-readiness issue
- should still be treated as a local contract-alignment fix, not as a broad write-path redesign

### What must NOT be bundled into this fix

- no broad write-flow refactor
- no index architecture redesign
- no weather-policy redesign

---

## Fix Candidate 3 — `query_weather` failure-surface consistency (narrow error-surface alignment)

### Priority

- **P2**

### Status

- **Completed**

### Evidence tier

- **Tier B — Strongly indicated**

### Why it is in the fix queue

Baseline evidence suggests the weather path has uneven error-surface behavior between related capability functions. This is not as urgent as the import mismatch, but it is bounded and relevant to consistency.

### Evidence

- weather-related tests and baseline evidence indicate working capability
- review synthesis identified narrower error-surface inconsistencies rather than broad weather failure

### Why it matters

- keeps weather-path behavior easier to reason about
- improves consistency for future caller logic

### Scope touched

- `tools/query_weather/` error-surface semantics only

### Blast radius

- **Low to Medium**

### Why now

- only after the P0 mismatch is resolved
- still smaller and safer than broader orchestration issues

### What must NOT be bundled into this fix

- no weather contract redesign
- no changes to write/edit orchestration model

---

## Fix Candidate 4 — `build_index.show_stats()` cache-path expectation mismatch

### Priority

- **P3**

### Status

- **Completed**

### Evidence tier

- **Tier A — Confirmed**

### Why it is in the fix queue

After P0 removed the `query_weather` import blocker, the full unit baseline exposed two concrete failing tests in `tests/unit/test_build_index.py`.

The failure boundary is narrow and now localized:

- tests expect `show_stats()` to exercise a cache directory derived from mocked `USER_DATA_DIR`
- current implementation uses `get_model_cache_dir()` directly instead
- the mocked `mock_cache_dir.exists()` is therefore never called

### Evidence

- full `python -m pytest tests/unit -q` now runs past weather collection and fails in:
  - `TestShowStats::test_show_stats_cache_directory_exists`
  - `TestShowStats::test_show_stats_cache_directory_not_exists`
- both failures assert `mock_cache_dir.exists.assert_called()`
- `tools/build_index/__init__.py` `show_stats()` uses:
  - `cache_dir = get_model_cache_dir()`
  - `cache_dir.exists()`
- the failing tests patch `tools.build_index.USER_DATA_DIR` rather than `get_model_cache_dir()`

### Why it matters

- this is the next runtime-observed blocker in the unit baseline after the weather P0 was removed
- the fault boundary is still narrow and test-readiness focused
- it is suitable for targeted repair without broad refactoring

### Scope touched

- `tools/build_index.show_stats()` cache-path surface and/or test expectation surface

### Blast radius

- **Low**

### Why now

- high evidence
- newly surfaced only because baseline advanced successfully
- localized mismatch with low architectural risk

### What must NOT be bundled into this fix

- no build-index architecture redesign
- no vector/FTS backend redesign
- no broad cache strategy rewrite

---

## 4. Investigation queue (do not fix yet)

These items are real concerns, but they are **not yet good immediate fix candidates** because the evidence is still incomplete, the issue remains contract-level, or the likely blast radius is too large relative to current proof.

## Investigation 1 — Agent-layer confirmation / clarification correctness

### Current status

- **Tier C — Investigation only**

### Why it stays out of the immediate fix queue

- baseline repeatedly shows weaker evidence at the agent/tool boundary than at the tool layer
- current evidence is more about missing proof than directly observed failure

### Why it still matters

- high conceptual importance
- but still not mature enough for immediate fix ranking

---

## Investigation 2 — Weather/edit runtime warning or validation behavior

### Current status

- **Tier C — Investigation only**

### Why it stays out of the immediate fix queue

- `WEATHER_EDIT_BOUNDARY.md` explicitly accepts current asymmetry for now
- baseline did not show a runtime-observed user-facing defect here

### Why it still matters

- likely future UX / workflow-hardening topic
- not yet a validated immediate repair

---

## Investigation 3 — Retrieval quality / semantic relevance / fusion effectiveness

### Current status

- **Tier C — Investigation only**

### Why it stays out of the immediate fix queue

- baseline confirms structural readiness, not quality proof
- no empirical run yet shows a concrete retrieval defect to fix

### Why it still matters

- high long-term product value
- but still an evaluation problem first, not a repair problem first

---

## Investigation 4 — Failure-injection scenario-level truthfulness

### Current status

- **Tier C — Investigation only**

### Why it stays out of the immediate fix queue

- baseline shows most failure scenarios remain unexecuted hypotheses
- should not be converted into implementation work without scenario proof

### Why it still matters

- central to long-term reliability confidence
- but the right next step is more validation, not broad fixing

---

## Investigation 5 — Index-state observability completeness

### Current status

- **Tier C / borderline B, but keep in investigation**

### Why it stays out of the immediate fix queue

- important contract area, but evidence still leans toward “not fully proven” rather than “confirmed defect with narrow boundary”
- easy to accidentally turn this into a broad architecture change

### Why it still matters

- central to truthful saved-vs-searchable semantics
- should be revisited after smaller fixes or stronger scenario evidence

---

## 5. Explicit deferrals

The following are **not** part of the immediate fix plan:

- MCP migration or protocol expansion
- broad workflow refactors
- semantic model changes or search-stack redesign
- large-scale test-suite redesign
- broad index architecture redesign
- broad write-flow redesign

Reason:

- current baseline evidence does not justify those as immediate targeted repairs
- they risk violating the diagnosis-first discipline

---

## 6. Ranked summary

| Rank | Candidate | Evidence tier | User impact | Blast radius | Queue |
|:---:|:---|:---:|:---|:---|:---|
| 1 | `query_weather` package-surface / test-readiness mismatch | A | High for baseline trust, medium direct user impact | Low | Completed |
| 2 | `write_journal` result-state signaling alignment | B | High trust / workflow impact | Medium | Completed |
| 3 | `query_weather` narrow error-surface consistency | B | Medium | Low-Medium | Completed |
| 4 | `build_index.show_stats()` cache-path expectation mismatch | A | Medium for baseline trust, low direct user impact | Low | Completed |
| 5 | Agent-layer confirmation/clarification correctness | C | High conceptually | Medium-High | Investigation |
| 6 | Weather/edit runtime warning/validation behavior | C | Medium | Medium | Investigation |
| 7 | Retrieval quality / semantic relevance / fusion effectiveness | C | Potentially high | High | Investigation |
| 8 | Failure-injection scenario-level truthfulness | C | Potentially high | High | Investigation |
| 9 | Index-state observability completeness | C / borderline B | High conceptually | High | Investigation |

---

## 7. Recommended planning stance

The correct next-stage stance is:

1. take the **narrowest Tier A item first**
2. consider Tier B only when the fix boundary remains local and rollback-friendly
3. keep Tier C items in investigation until new evidence upgrades them

This prevents the project from drifting from:

- targeted repair

into:

- architecture dissatisfaction disguised as a fix plan

---

## 8. Bottom line

After three baseline passes plus the completion of the immediate fix queue items P0/P1/P2/P3, the project now has **no remaining completed-tier immediate items**, and the next meaningful work lies in the investigation queue unless new runtime-observed gaps emerge.

That is a healthy outcome.

It means the baseline work succeeded in doing exactly what it was supposed to do:

> **turn vague unease into a small, ranked, evidence-backed fix queue without forcing premature broad implementation work.**
