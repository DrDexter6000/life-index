# Targeted Fix Ultrawork Plan

Status: open  
Priority: P0  
Owner: current targeted-fix execution track  
Scope: execute the next evidence-backed fix wave after the baseline unit blockers were already cleared.

## Core directive

This file is a **planning artifact only**. It does not authorize opportunistic implementation.

The plan must stay aligned with these proven facts from `docs/review/evals/BASELINE_RUN_RESULTS.md`:

- P0, P1, P2, and P3 are already completed
- `.venv/Scripts/python.exe -m pytest tests/unit -q` is now green
- the remaining gaps are no longer basic test-readiness gaps
- the remaining work is mainly about **agent/tool boundary proof, degraded-state truthfulness, index-state observability, and retrieval quality evidence**

## Planning guardrails

- English only
- TDD-first for every runtime change
- one problem class at a time
- no broad refactors during bug-fix work
- preserve existing architectural boundaries unless failing proof forces expansion
- do not modify `SKILL.md` in the default path for this track
- in future examples/reporting, use `/life-index [user custom trigger phrase]`

## Current evidence snapshot

### Already verified

- `tools.query_weather` package-surface mismatch around `main` is fixed
- `build_index.show_stats()` test/readiness mismatch is fixed
- `write_journal` now exposes clearer side-effect state fields
- `query_weather` timeout handling now follows the structured error surface
- the full unit baseline is green
- E2E runner availability is confirmed
- retrieval architecture is structurally strong and test-backed at unit level

### Still unproven or weakly proven

1. **Agent/tool boundary correctness**
   - clarification truthfulness
   - confirmation handling truthfulness
   - write-vs-edit routing correctness
   - empty-vs-degraded search response truthfulness

2. **Scenario-level degraded-state truthfulness**
   - most `FAILURE_INJECTION_CHECKLIST.md` scenarios are still unexecuted
   - the biggest remaining risk is not capability absence but caller-visible ambiguity

3. **Index-state observability**
   - durable save, index freshness, and search visibility are conceptually separated
   - runtime proof of consistent separation is still incomplete

4. **Retrieval quality proof**
   - exact / lexical / semantic / fusion capability exists
   - corpus-backed quality proof is still missing

## Binary definition of done for ultrawork

This targeted-fix track is complete only when all of the following are true:

- the unit suite stays green throughout the track
- the highest-risk workflow claims are covered by failing-then-passing proof artifacts
- the most important degraded states are distinguishable as:
  - saved
  - saved but degraded
  - not saved
  - confirmation required
- runtime status surfaces cleanly separate:
  - durable file success
  - index update state
  - search visibility state when relevant
- retrieval quality claims are backed by a small deterministic evaluation harness
- docs/reporting do not overclaim beyond proven runtime behavior

## Acceptance criteria model

Every implementation slice in this track must follow this binary acceptance model:

1. define the smallest failing proof first
2. verify the failure is for the expected reason
3. implement the smallest fix
4. rerun the targeted proof
5. rerun the smallest relevant regression slice
6. commit only after the slice is green

Shared history should remain green. The red phase is local only.

## Preflight workstream — Re-baseline before any new code

### Objective

Confirm the working branch still matches the post-fix baseline state before starting any new fix slice.

### Required commands

- `.venv/Scripts/python.exe -m pytest tests/unit -q`
- `.venv/Scripts/python.exe -m tests.e2e.runner --help`
- `.venv/Scripts/python.exe -m tests.e2e.runner --dry-run`

### Pass/fail acceptance criteria

- **PASS** if the unit suite is green and the E2E runner remains callable
- **FAIL** if any previously closed blocker reappears or the runner becomes unusable

### Output required before moving on

- one short re-baseline note in the work log
- exact command outputs captured for any failure

## Workstream 1 — Agent/tool boundary proof first

### Why this is first

Baseline evidence is stronger at the tool layer than at the user-visible workflow boundary. That is now the highest-value truth gap.

### Main proof targets

- `WF-02` ambiguous intent clarification
- `WF-03` confirmation flow handling
- `WF-10` degraded write-state description
- explicit write-vs-edit routing correctness
- explicit search empty-vs-degraded truthfulness

### Preferred proof layer

- first choice: E2E scenarios in `tests/e2e/`
- second choice: integration-style tests if the E2E runner cannot isolate the contract clearly enough

### Candidate files to touch

- `tests/e2e/phase1-core-workflow.yaml`
- `tests/e2e/phase3-edge-cases.yaml`
- `tests/e2e/phase4-edit-abstract.yaml`
- `tests/e2e/runner.py` only if a new assertion primitive is truly required
- production code only after a failing proof exists

### Must-do rules

- prove caller-visible wording and state distinctions, not just internal helper behavior
- prefer test additions over contract rewrites
- if host-agent behavior outside this repo is the blocker, stop and write a decision note instead of faking proof

### Must-not-do rules

- do not reopen already-completed P0-P3 work
- do not broaden into retrieval tuning
- do not change `SKILL.md` unless scope is explicitly re-opened later

### Exit criteria

- the highest-risk workflow claims are no longer contract-only
- clarification, confirmation, and degraded-write wording are all test-backed at the user-visible layer

## Workstream 2 — Failure-injection truthfulness and degraded states

### Why this is second

The review bundle treats degraded-state honesty as a core product promise. This workstream converts that promise into executable proof.

### Priority execution order

Start with the smallest high-impact scenarios:

1. `FI-01` weather failure after durable write
2. `FI-04` durable write failure before completion
3. `FI-05` index side-effect failure after durable write
4. `FI-06` confirmation pending after successful write
5. `FI-15` saved-vs-failed language correctness
6. `FI-17` confirmation-vs-failure confusion
7. `FI-18` retrieval visibility vs source truth confusion

Only after those are stable, expand to edit and stale-index scenarios.

### Candidate files to touch

- `tests/unit/test_write_journal_core.py`
- `tests/unit/test_edit_journal_new.py`
- `tests/e2e/phase1-core-workflow.yaml`
- `tests/e2e/phase3-edge-cases.yaml`
- `tools/write_journal/core.py`
- `tools/write_journal/weather.py`
- `tools/write_journal/index_updater.py`
- `tools/edit_journal/__init__.py` only if failing proof shows a real contract gap

### High-risk coupling warning

`tools/write_journal/core.py` is a coordination hotspot. Any change here must be validated against downstream index-update behavior, not just the direct return payload.

### Exit criteria

- the highest-value degraded states are distinguishable in both tests and runtime outputs
- saved, degraded, unsaved, and confirmation-required outcomes no longer collapse into vague success language

## Workstream 3 — Index-state observability

### Why this is separate

Index-state ambiguity can quietly corrupt user trust even when durable writes succeed. This deserves a dedicated slice instead of being hidden inside failure work.

### Main proof targets

- durable save status is visible
- index update status is visible
- search visibility lag is distinguishable from source-of-truth durability

### Candidate files to touch

- `tests/unit/test_write_journal_core.py`
- `tests/unit/test_build_index.py`
- `tests/unit/test_search_journals_core.py`
- targeted E2E YAML where user-visible state wording matters
- `tools/write_journal/core.py`
- `tools/build_index/__init__.py` only if proof shows a real observability gap

### Safe-boundary rule

Avoid `tools/lib/config.py` and `tools/lib/frontmatter.py` in this workstream unless a failing proof demonstrates they are the root cause. They are SSOT hotspots with broad blast radius.

### Exit criteria

- runtime result surfaces expose the state distinctions required by the review contract
- tests prove that “saved but not yet searchable” is not silently reported as a fully healthy success

## Workstream 4 — Retrieval quality proof before any tuning

### Why this is fourth

The repo already has strong retrieval structure. The missing piece is proof quality, not architecture churn.

### Main proof targets

- exact retrieval cases
- fuzzy lexical retrieval cases
- semantic retrieval cases
- fusion quality on harder conceptual cases
- empty-vs-degraded retrieval distinction

### Source artifacts to use

- `docs/review/evals/RETRIEVAL_EVAL_CASES.md`
- existing unit coverage in:
  - `tests/unit/test_search_journals_core.py`
  - `tests/unit/test_semantic_search.py`
  - `tests/unit/test_ranking.py`
  - `tests/unit/test_search_index.py`

### Candidate files to touch

- a small deterministic retrieval evaluation harness under `tests/`
- `tests/e2e/phase2-search-retrieval.yaml` if the cases belong at the scenario layer
- `tools/search_journals/core.py` only after a repeatable failing case exists
- `tools/search_journals/ranking.py` only after the harness proves a ranking failure

### High-risk coupling warning

`tools/search_journals/core.py` and `tools/lib/semantic_search.py` are not safe “while I am here” edit zones. Do not tune them without deterministic failing evidence.

### Exit criteria

- retrieval quality claims are backed by a small, repeatable corpus-backed proof set
- no ranking or semantic tuning lands without a failing evaluation case that it fixes

## Workstream 5 — Documentation and reporting alignment

### Why this is last

Documentation must follow proven behavior, not lead it.

### Candidate updates

- align operator-facing review notes with the now-proven runtime behavior
- clarify workflow/tool boundaries only where tests have removed ambiguity
- use `/life-index [user custom trigger phrase]` wherever a trigger placeholder is needed

### Must-not-do rules

- do not change `SKILL.md` on the default path for this track
- do not expand scope into onboarding rewrites unless new failing proof makes that necessary

### Exit criteria

- docs/reporting language matches verified runtime behavior
- no documentation claim exceeds the proof established in Workstreams 1-4

## Commit strategy — atomic and TDD-compatible

### Core rule

One user-visible contract slice per commit.

Each commit must contain:

- the failing proof that justified the change
- the minimal implementation change needed to make it pass
- no unrelated cleanup

### What is allowed locally but not in shared history

- local red tests before the fix
- local debug instrumentation removed before commit

### What is forbidden in a single commit

- mixing workflow-boundary fixes with retrieval tuning
- mixing docs with unrelated runtime changes
- mixing SSOT changes (`config.py`, `frontmatter.py`) with unrelated feature fixes

### Recommended commit train

1. `fix: prove clarification and confirmation truthfulness at the workflow boundary`
2. `fix: preserve saved-vs-degraded write outcomes under side-effect failure`
3. `fix: expose search visibility separately from durable save success`
4. `test: add deterministic retrieval quality harness`
5. `fix: correct retrieval ranking only for proven failing cases`
6. `docs: align reporting with verified targeted-fix behavior`

If one commit above grows beyond a single contract slice, split it again.

## Verification matrix

### Required after every runtime slice

- targeted unit test(s) that introduced the red-green cycle
- smallest relevant E2E phase or scenario
- `.venv/Scripts/python.exe -m pytest tests/unit -q` before moving to the next major workstream

### Required after harness-only or docs-only slices

- run the exact tests or dry-run command that proves the changed artifact is valid
- re-read the changed file for claim accuracy

### Manual QA requirement

For every CLI-visible change, run the actual command path and capture the observed output. Do not rely on static reasoning alone.

## Sequencing rules from dependency risk

### Safe-first areas

- tests under `tests/`
- isolated workflow YAML updates
- `tools/query_weather/` if a narrow contract issue reappears

### Use extra caution in these hotspots

- `tools/write_journal/core.py`
- `tools/write_journal/index_updater.py`
- `tools/search_journals/core.py`
- `tools/search_journals/ranking.py`
- `tools/lib/semantic_search.py`
- `tools/lib/config.py`
- `tools/lib/frontmatter.py`

### Sequencing implication

- prove user-visible contracts first
- touch search ranking only after evaluation evidence exists
- touch SSOT files only if narrower layers are proven innocent

## Stop conditions

Stop execution and create a fresh decision note if any of these occur:

- a “minimal” fix requires cross-module refactoring beyond the active workstream
- runtime proof depends on host-agent behavior the repo cannot control or verify
- retrieval evaluation cannot be made deterministic enough for repeatable use
- a proposed fix requires `config.py` or `frontmatter.py` changes with unclear blast radius
- the re-baseline step contradicts the current baseline artifact

## Explicit non-goals

- broad architecture rewrite
- MCP migration
- scheduler work
- speculative retrieval optimization without failing proof
- onboarding expansion beyond proven targeted-fix needs
- changing `SKILL.md` on the default path of this track
