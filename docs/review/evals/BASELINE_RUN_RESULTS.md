# Baseline Run Results

> **Document role**: Record the first real baseline diagnostic run against the `docs/review/` bundle
> **Audience**: Project Owner, reviewers, implementers, and future agents
> **Authority**: Review-scoped baseline result artifact; does not redefine runtime SSOT and does not authorize implementation changes by itself
> **Run mode**: Assessment-first, non-destructive, no code changes

---

## 1. Run scope

This baseline run followed the intent of:

- `docs/review/evals/BASELINE_EXECUTION_PLAN.md`
- `docs/review/evals/BASELINE_EVALUATION_REVIEW.md`

The run focused on:

1. evidence inventory
2. non-destructive validation checks
3. actual-vs-expected gap recording

This run did **not** include:

- implementation changes
- quick fixes
- failure-injection execution
- full empirical semantic quality benchmarking

---

## 2. Methodology guardrails used in this run

To keep the baseline honest, findings were interpreted using these evidence classes:

- **Runtime-observed** — directly observed through commands executed during this run
- **Test-backed** — supported by existing tests in the repo
- **Static code-backed** — supported by code inspection but not directly exercised during this run
- **Doc-backed** — supported by upstream docs or review docs, but not proven in this run
- **Contract-only** — defined in the review bundle as expected behavior, not yet proven
- **Unknown** — current evidence is insufficient

Additional rigor rule from the Oracle review:

> review documents are contract inputs, not proof of runtime behavior

So this document does **not** treat `docs/review/` artifacts as self-certifying evidence.

---

## 3. Actual checks performed in this run

## 3.1 Unit test baseline check

### Command

`python -m pytest tests/unit -q`

### Observed result

- **FAIL during collection**
- Collection stopped on `tests/unit/test_query_weather.py`

### Observed failure

- `ImportError: cannot import name 'main' from 'tools.query_weather'`

### File evidence

- `tests/unit/test_query_weather.py` imports `main` from `tools.query_weather`
- `tools/query_weather/__init__.py` exports `geocode_location`, `get_weather_code_description`, `simplify_weather`, and `query_weather`, but no `main` function is present in the inspected module file

### Interpretation

- This is a **runtime-observed** mismatch between test expectation and currently importable module surface
- It is evidence of a real baseline issue in test readiness
- This run does **not** diagnose root-cause ownership beyond recording the mismatch

### Status

- **Divergent**

---

## 3.2 E2E runner availability check

### Commands

- `python -m tests.e2e.runner --help`
- `python -m tests.e2e.runner --dry-run`

### Observed result

- E2E runner is callable
- Help output is available
- Dry-run enumerates Phase 1 and Phase 2 scenarios and emits report paths

### Observed warning

- Runtime warning about `tests.e2e.runner` already being present in `sys.modules` before execution

### Interpretation

- E2E infrastructure exists and is operational enough to enumerate planned scenarios
- This is **runtime-observed** evidence of runner readiness
- It is **not** proof that the E2E scenarios actually pass
- The runtime warning should be recorded as an observation, but this run does not classify it as a confirmed functional failure

### Status

- **Confirmed (runner availability)**
- **Unknown (actual E2E correctness)**

---

## 3.3 Static evidence inventory

Using code/test/doc inspection plus review-bundle mapping, this run established the following high-confidence evidence.

---

## 4. Evidence summary by domain

## 4.1 Workflow domain

### Confirmed / high-confidence

- `write_journal` core implementation exists with:
  - atomic write behavior
  - file locking
  - weather-related enrichment path
  - confirmation-related signaling
  - index update behavior
- `edit_journal` implementation exists with:
  - deterministic mutation
  - content append/replace
  - index synchronization
  - no visible built-in weather auto-refresh path in the inspected implementation surface
- `query_weather` implementation exists as a capability tool
- `build_index` capability exists

### Evidence mode

- Mostly **static code-backed**
- partially **test-backed**

### Still not fully proven

- end-to-end caller handling of `needs_confirmation`
- agent-layer clarification correctness
- agent-layer write-vs-edit routing correctness

### Domain verdict

- **Tool-layer workflow readiness: strong**
- **Agent-layer workflow proof: incomplete**

---

## 4.2 Retrieval domain

### Confirmed / high-confidence

- keyword retrieval exists
- layered retrieval exists (L1/L2/L3)
- semantic retrieval implementation exists
- fusion/hybrid ranking exists

### Evidence mode

- **static code-backed**
- **test-backed** for major search architecture pieces

### Still not fully proven

- empirical semantic retrieval quality
- whether fusion improves ranking on the review corpus’s harder conceptual cases
- whether empty-result vs failure distinction is consistently surfaced at runtime in user-facing flows

### Domain verdict

- **Retrieval capability readiness: strong**
- **Retrieval quality proof: incomplete**

---

## 4.3 Failure-handling domain

### Confirmed / high-confidence

- structured error taxonomy exists
- weather failure handling exists in some form
- lock-timeout/error handling exists in the write path
- graceful-degradation concepts appear partially supported by implementation/tests

### Evidence mode

- **static code-backed**
- **test-backed** for some tool-level failure cases

### Still not fully proven

- the 18 failure-injection scenarios from `FAILURE_INJECTION_CHECKLIST.md`
- full truth-preserving reporting under degraded states
- explicit runtime separation of “saved but degraded” vs “unsaved” across all major paths

### Domain verdict

- **Failure-handling design maturity: good**
- **Failure-injection proof: not yet executed**

---

## 4.4 Index consistency domain

### Confirmed / high-confidence

- index update mechanisms exist in write/edit paths
- rebuild capability exists
- vector index support exists

### Evidence mode

- **static code-backed**

### Still not fully proven

- that runtime signaling cleanly separates:
  - durable write success
  - index freshness
  - search visibility
- that all intended best-effort / repairable semantics are consistently exposed to callers

### Domain verdict

- **Index/update capability readiness: good**
- **Index-state observability proof: incomplete**

---

## 5. Evidence-class matrix for this run

| Area | Best current evidence class | Baseline status |
|:---|:---:|:---|
| Major tool implementations exist | Static code-backed | Confirmed for baseline purposes |
| Unit test readiness | Runtime-observed | Divergent due to collection failure in weather tests |
| E2E runner availability | Runtime-observed | Confirmed |
| E2E scenario correctness | Unknown | Not executed in this run |
| Workflow contract clarity | Doc-backed | Strong |
| Agent-layer workflow correctness | Contract-only / unknown | Not yet proven |
| Retrieval architecture exists | Static code-backed + test-backed | Confirmed |
| Retrieval quality is good | Unknown | Not yet proven |
| Failure taxonomy is coherent | Doc-backed | Strong |
| Failure resilience is proven | Contract-only / unknown | Not yet proven |
| Index consistency policy exists | Doc-backed | Strong |
| Runtime index-state separation is proven | Unknown | Not yet proven |

---

## 6. Actual-vs-expected findings

## 6.1 Expected

From the review bundle, the project was expected to be ready for a baseline diagnostic run, but not yet ready to claim full contract compliance.

## 6.2 Actual

This expectation was largely correct.

### Confirmed during the run

- the review bundle is mature enough to guide diagnosis
- the codebase is substantial enough to make diagnosis meaningful
- the project has enough implementation/test surface to support evaluation

### Newly observed during the run

- unit test collection currently fails at least once due to `tools.query_weather` vs test import mismatch
- E2E infrastructure exists and can enumerate scenarios, but scenario success remains unproven in this run

---

## 7. Major gaps recorded by this run

## Gap 1 — Unit test readiness is not clean

### Evidence

- runtime-observed pytest collection failure in `tests/unit/test_query_weather.py`

### Classification

- **Divergent**

### Why it matters

- weakens the claim that the current test surface is immediately executable as baseline proof

---

## Gap 2 — Agent-layer claims remain less proven than tool-layer claims

### Evidence

- baseline evidence is stronger in implementations and unit tests than in agent-orchestration proof

### Classification

- **Contract-only / Unknown** depending on the specific claim

### Why it matters

- many of the most important workflow expectations live at the agent/tool boundary

---

## Gap 3 — Retrieval quality is structurally prepared but empirically unproven

### Evidence

- architecture exists
- eval corpus exists
- actual semantic/fusion quality was not measured in this run

### Classification

- **Unknown** for quality

### Why it matters

- implementation existence is not the same thing as retrieval excellence

---

## Gap 4 — Failure-injection coverage is designed, not yet executed

### Evidence

- checklist exists
- no executed failure-injection evidence was collected in this run

### Classification

- **Contract-only / Untested**

### Why it matters

- degraded-state truthfulness is still more of a designed contract than a proven runtime property

---

## Gap 5 — Index-state reporting remains less explicit than the review contract

### Evidence

- policy distinguishes durability, index freshness, and retrieval visibility
- this run did not observe strong runtime proof that these are always surfaced distinctly

### Classification

- **Unknown / partially aligned**

### Why it matters

- this is one of the central truths the review bundle is trying to protect

---

## 8. Domain-level baseline verdict

| Domain | Verdict |
|:---|:---|
| Workflow contracts | Ready for diagnosis |
| Tool-layer implementation | Ready for diagnosis |
| Agent-layer behavior | Not yet strongly proven |
| Retrieval architecture | Ready for diagnosis |
| Retrieval quality | Not yet proven |
| Failure model | Ready for diagnosis |
| Failure resilience | Not yet proven |
| Index consistency reasoning | Ready for diagnosis |
| Index-state runtime observability | Not yet strongly proven |

---

## 9. Baseline run conclusion

### Bottom line

**This baseline run validates the choice to evaluate before changing code.**

The project is clearly mature enough that diagnosis is meaningful, but it is also clear that several important review-bundle claims are still ahead of runtime proof.

That means the current state is:

- strong enough to justify continued baseline evaluation work
- not yet strong enough to claim runtime conformance to the full review contract

### Most important new factual finding from this run

The unit test baseline is not currently clean because of an observed import mismatch in the weather test path.

This is the first concrete runtime-observed gap recorded by the baseline run.

---

## 10. Recommended next step after this run

Per the execution plan, the next appropriate move is still diagnostic, not implementation-first.

The next review should decide whether to:

1. continue collecting baseline evidence (for example, more runtime validation)
2. refine evidence labeling where claims are still too broad
3. only after that, decide whether a targeted fix phase is justified

This document deliberately stops short of prescribing specific code changes.

---

## 11. Second-pass diagnostic extension

This section records the **second baseline diagnostic pass**, focused on:

- test readiness
- retrieval evidence
- failure-injection readiness

This pass remained non-destructive and did not change code.

---

## 12. Second-pass test readiness findings

## 12.1 Targeted unit-test runs executed

### Commands executed

- `python -m pytest tests/unit/test_write_journal_core.py -q`
- `python -m pytest tests/unit/test_search_journals_core.py -q`
- `python -m pytest tests/unit/test_edit_journal_new.py -q`

### Observed result

- `test_write_journal_core.py` — **PASS**
- `test_search_journals_core.py` — **PASS**
- `test_edit_journal_new.py` — **PASS**

### Observed warnings

- fastembed / vector embedding warning about mean pooling behavior from `vector_index_simple.py`

### Interpretation

- The targeted write/search/edit suites are **runtime-observed clean** in this second-pass run
- This materially strengthens the project’s tool-layer test readiness picture
- The warning should be retained as environmental/compatibility context, but this run does not classify it as a functional test failure

### Updated test-readiness conclusion

- **Write/search/edit unit readiness: Confirmed**
- **Whole-unit-suite readiness: still blocked by weather-test import mismatch observed in first pass**

---

## 13. Second-pass retrieval diagnostics

## 13.1 Retrieval capability findings

The second pass deepened retrieval evidence beyond the first-run summary.

### Confirmed now

- exact retrieval is implemented through layered search and filtering
- fuzzy lexical retrieval exists through BM25 / multi-keyword / case-insensitive search behavior
- semantic retrieval is structurally implemented via embedding/vector infrastructure
- fusion/hybrid retrieval is structurally implemented via RRF + dual-pipeline integration

### Evidence sources

- `tools/search_journals/core.py`
- `tools/search_journals/ranking.py`
- `tools/search_journals/semantic.py`
- `tools/search_journals/l3_content.py`
- `tools/lib/semantic_search.py`
- `tools/lib/vector_index_simple.py`
- `tools/lib/search_index.py`
- retrieval-related unit tests including ranking / semantic / search-index coverage

### Strengthened retrieval verdict

- **Exact retrieval readiness: Confirmed**
- **Fuzzy lexical retrieval readiness: Confirmed**
- **Semantic retrieval capability: Confirmed structurally**
- **Fusion architecture: Confirmed structurally**

### Still not proven after second pass

- empirical semantic quality on real journal corpus
- whether fusion materially improves hard conceptual cases from the retrieval eval corpus
- cross-language retrieval quality in practice
- runtime-facing distinction quality for empty result vs degraded retrieval under real execution

### Retrieval evidence conclusion

The project is now stronger than “retrieval architecture exists.”

The honest statement after this second pass is:

> **Retrieval modes are structurally well implemented and test-backed, but quality proof remains corpus-bound and not yet established by baseline execution.**

---

## 14. Second-pass failure-injection readiness findings

## 14.1 Failure class mapping

The second pass compared `FAILURE_INJECTION_CHECKLIST.md` against current code/tests and found:

- **5 / 18** failure classes have partial tool-level support with evidence
- **13 / 18** remain unexecuted hypotheses
- **0 / 18** have full scenario-proof status

### Partially supported failure classes

- weather lookup failure during write enrichment
- core write failure before durable completion
- index side-effect failure after durable write (partially supported by rollback logic / partial evidence)
- confirmation pending after successful write
- empty result with healthy retrieval
- plus partial retrieval/vector degradation evidence at tool level

### Important qualification

These are mostly **tool-level** proofs, not full contract-level scenario proofs.

That means:

- code and tests suggest parts of the behavior exist
- but the full review contract for degraded-state truthfulness is still not fully executed end-to-end

### Most important unexecuted hypothesis areas

- edit + weather boundary failure scenarios
- stale visibility / saved-but-not-searchable-yet scenarios
- manual file edit recovery semantics
- cross-boundary truthfulness checks:
  - saved vs failed language correctness
  - confirmation vs failure confusion
  - retrieval visibility vs source-truth confusion

### Failure-readiness conclusion

The honest statement after this second pass is:

> **Failure-handling infrastructure exists and some degradation paths are test-backed, but most failure-injection scenarios remain unexecuted at the scenario-contract level.**

---

## 15. Updated gap picture after the second pass

### Gap A — Whole-suite unit readiness still has a known blocker

Even though write/search/edit targeted suites are clean, the full `tests/unit` baseline is still not clean because of the observed `tools.query_weather` / `test_query_weather` import mismatch.

### Gap B — Retrieval capability is stronger than previously recorded, but quality proof is still missing

The second pass reduces uncertainty around retrieval architecture, but not around retrieval quality.

### Gap C — Failure resilience is still more partially evidenced than actually scenario-proven

The second pass confirms that some failure behaviors exist in code/tests, but the majority of review-level failure scenarios are still unexecuted hypotheses.

### Gap D — Agent-layer proof remains weaker than tool-layer proof

Nothing in the second pass changed the core judgment that agent/tool boundary correctness is less proven than tool implementation correctness.

---

## 16. Updated baseline status after the second pass

| Area | First-pass status | Second-pass status |
|:---|:---|:---|
| Write/search/edit unit readiness | Partially inferred | Runtime-observed clean in targeted suites |
| Whole-unit-suite readiness | Divergent | Still divergent due to weather test import mismatch |
| Retrieval architecture | Confirmed structurally | Confirmed with deeper evidence |
| Retrieval quality | Unknown | Still unknown / corpus-bound |
| Failure infrastructure | Good but broad | Better mapped, still mostly unexecuted at scenario level |
| Failure-injection proof | Not executed | Still largely unexecuted |
| Agent-layer evidence | Weak | Still weak relative to tool layer |

---

## 17. Current baseline conclusion after two passes

After two diagnostic passes, the strongest honest conclusion is:

> **Life Index has strong tool-layer implementation maturity, increasingly well-supported retrieval infrastructure, and partially evidenced failure-handling behavior, but it still lacks full runtime proof for agent-layer workflow correctness, retrieval quality, and most scenario-level failure resilience.**

This remains fully consistent with the review-bundle stance:

- diagnosis first
- no code changes during baseline work
- separate capability proof from quality proof
- separate tool proof from agent-orchestration proof

---

## 18. Third-pass diagnostic extension

This section records the **third baseline diagnostic pass**, focused on:

- weather-path diagnosis
- a narrow set of key failure-scenario observations

This pass remained non-destructive and did not change code.

Methodological constraint from Oracle for this pass:

- local probes support local claims first
- blocked probes are not automatically feature failures
- module-surface issues must be separated from feature-health issues

---

## 19. Third-pass weather-path findings

## 19.1 Commands and observations

### Commands executed

- `python -m tools.query_weather --help`
- `python -m pytest tests/unit/test_weather.py -q`
- `python -m pytest tests/unit/test_query_weather.py -q`

### Observed result

- `python -m tools.query_weather --help` — **PASS**
- `tests/unit/test_weather.py` — **PASS**
- `tests/unit/test_query_weather.py` — **FAIL during collection**

### Observed blocking error

- `ImportError: cannot import name 'main' from 'tools.query_weather'`

---

## 19.2 Weather-path diagnosis

The third pass sharpens the previous weather conclusion.

### What is now directly supported

- the **weather CLI surface is healthy**
  - `tools/query_weather/__main__.py` defines `main()`
  - `python -m tools.query_weather --help` works
- the **write-side weather helper path is healthy enough to test**
  - `tests/unit/test_weather.py` passes
  - `tools/write_journal/weather.py` calls weather via module execution subprocess
- the **core weather capability surface in `tools.query_weather.__init__.py` exists**
  - core functions are present and importable

### What is blocked

- `tests/unit/test_query_weather.py` assumes that `main` is importable from `tools.query_weather`
- the inspected package surface in `tools/query_weather/__init__.py` does not export `main`
- `main` lives in `tools/query_weather/__main__.py`

### Narrow interpretation

This third-pass evidence supports a **module-surface / test-readiness mismatch** claim.

It does **not** support the broader claim that:

- the full weather feature is broken
- write-side weather integration is broken
- the CLI weather path is broken

### Third-pass weather verdict

> **Weather capability health is stronger than the full-unit-suite result suggested; the currently observed blocker is specifically a package-surface/test-expectation mismatch around `main`, not a broad weather-feature failure.**

---

## 20. Third-pass key failure-scenario observations

This pass did not execute full failure injection.

Instead, it added a few higher-resolution observations relevant to key failure classes.

## 20.1 Weather failure class interpretation

### Supported more strongly now

- write-side weather behavior has direct passing test evidence via `tests/unit/test_weather.py`
- weather CLI invocation path is directly observable and callable

### Still not proven

- full scenario-level truthfulness for weather degradation in end-user flows
- edit + weather coupling failure scenarios
- saved-vs-unconfirmed-vs-degraded distinctions under full runtime orchestration

### Failure-scenario implication

The weather-related failure readiness map should now be interpreted as:

- **weather capability exists and some weather degradation handling is test-backed**
- **weather scenario-contract proof remains incomplete**

---

## 20.2 Test-readiness failure class interpretation

The weather-path collection failure is now more precisely classified as:

- **module-surface/test-readiness issue**
- not yet evidence of a user-visible weather capability failure

This matters because the baseline must not overclaim from a blocked test probe.

---

## 20.3 Updated failure-scenario stance

After the third pass, the most honest statement is:

> **Some priority failure classes are now better localized, but the majority of review-bundle failure scenarios still remain unexecuted at scenario level.**

What improved in this pass is not breadth of failure execution, but **diagnostic precision**.

---

## 21. Updated gap picture after the third pass

### Gap E — Weather-path test blockage is narrower than feature failure

The project should no longer describe the weather issue as a broad weather-path failure.

The better diagnosis is:

- weather CLI path: observed healthy
- write-side weather helper path: observed healthy
- package-surface expectation for `main`: mismatched with test expectations

### Gap F — Third-pass probes increase precision, not compliance

The third pass improves confidence about **where** the problem is, but does not change the larger rule:

- no claim of full failure-resilience proof
- no claim of full weather-contract compliance

---

## 22. Updated baseline status after the third pass

| Area | Second-pass status | Third-pass status |
|:---|:---|:---|
| Weather CLI path | Inferred through code/docs | Runtime-observed healthy |
| Write-side weather helper path | Partially supported | Runtime-observed clean via `test_weather.py` |
| Query-weather unit baseline | Divergent | Still divergent, but now localized to `main` package-surface mismatch |
| Weather feature health overall | Broadly uncertain | Narrower conclusion: partially healthy, partially blocked at module/test surface |
| Failure-scenario proof | Largely unexecuted | Still largely unexecuted, but weather-related failure diagnosis is sharper |

---

## 23. Current baseline conclusion after three passes

After three diagnostic passes, the strongest honest conclusion is:

> **Life Index has strong tool-layer maturity, strong structural retrieval readiness, and increasingly precise failure-path diagnosis. The remaining gaps are no longer just “unknown”; some are now localized to specific boundaries such as package-surface/test-readiness mismatch, while many scenario-level truthfulness claims still await explicit execution.**

This remains fully aligned with the baseline execution plan:

- keep diagnosis ahead of implementation
- distinguish local blocked probes from feature-health claims
- continue separating tool capability from scenario-proof

---

## 24. Post-fix status update — P0 and P3 completed

After the original three baseline passes, two immediate runtime-observed blockers were repaired and re-verified.

### P0 completed

- `query_weather` package-surface / test-readiness mismatch resolved
- `tests/unit/test_query_weather.py` now passes

### P3 completed

- `build_index.show_stats()` cache-path expectation mismatch resolved at the test/readiness boundary
- `tests/unit/test_build_index.py` now passes

### Updated unit-baseline status

- `python -m pytest tests/unit -q` now passes
- remaining output includes only:
  - Unix-only skips
  - fastembed pooling warning

### Interpretation

This does **not** prove full runtime contract compliance.
It does prove that the two narrowest runtime-observed unit-baseline blockers identified during baseline diagnostics have been removed.

---

## 25. Post-fix status update — P1 and P2 completed

After the first two runtime-observed blockers were removed, two additional immediate candidates were completed and re-verified.

### P1 completed

- `write_journal` result-state signaling was extended with explicit side-effect status fields
- the result surface now exposes:
  - `index_status`
  - `side_effects_status`
- this strengthens the contract boundary between core write success and degraded side effects

### P2 completed

- `query_weather` timeout behavior was aligned with the structured error-surface model
- `TimeoutError` is now returned as a structured weather-timeout error instead of propagating uncaught

### Verification results

- `python -m pytest tests/unit/test_write_journal_core.py -q` — PASS
- `python -m pytest tests/unit/test_query_weather.py -q` — PASS
- `python -m pytest tests/unit -q` — PASS

### Updated interpretation

The unit baseline is now green after completing P0, P3, P1, and P2.

This proves:

- the highest-confidence immediate fix queue items were implementable with narrow changes
- the project still benefits from the diagnosis-first approach

This still does **not** by itself prove:

- agent-layer workflow correctness
- semantic retrieval quality
- scenario-level failure-injection resilience
