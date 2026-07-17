# CI Hard Checks - SSOT

Status: public CI inventory
Scope: Life Index CLI repository

This file records the required CI checks, the matching local commands, and the
maintenance protocol for keeping workflow definitions, local scripts, and this
inventory in sync.

## Purpose

Required CI checks should be discoverable without relying on memory. When a
blocking gate changes, update the workflow, local gate script, and this file in
the same commit. A gate that exists in CI but not in the documented local
inventory is drift.

<!-- PLATFORM-SSOT:PUBLIC-BLOCKER-EXECUTION:START -->
## Public blocker execution contract

A public hard blocker is green only when at least one core assertion executed.
All-skipped assertion sets are not green. Private-only assertions are advisory
and cannot be the sole evidence for a Tier 1 public blocker.

The public #163 ownership invariant is implemented: the Tier 1 no-LLM check
scans every Python AST in search/smart-search/eval for known provider imports
and aliases, normalized LLM/provider/model-client declarations and storage,
simple provider bindings, provider-specific SDK call suffixes regardless of
owner name, and generic provider verbs only with structural provider provenance.
It also rejects legacy prompt/trust/synthesis ownership and constant-string
dynamic imports supplied as the first positional argument or `name=` keyword.
Syntax/parse failure is non-green. This is a
static structural boundary, not a universal proof against computed strings or
arbitrary runtime metaprogramming.

The blocker job first runs `.github/scripts/run_public_core_assertions.py`. Its
JSON sentinel is the assertion-count authority: green requires at least one
executed public synthetic token-match assertion. Zero collected, missing,
deselected, all-skipped, or setup-skipped assertions are non-green. Private
eval and broad/noise/quality metrics remain advisory and cannot satisfy this
count or defend result deletion.
<!-- PLATFORM-SSOT:PUBLIC-BLOCKER-EXECUTION:END -->

Platform-boundary checks follow the active C1–C7 authority in
`CHARTER.md §1.10` and the exact 31-route mapping in the
`PLATFORM-SSOT:PUBLIC-COMMAND-CLASSIFICATION` block of
`docs/ARCHITECTURE.md`; this CI inventory does not duplicate either SSOT.
Distribution/Host Operations remain non-Core when co-packaged, and `weather`
remains the #166 Legacy External Adapter exception.

## Workflows

| Workflow file | Trigger | Tier | Notes |
|---|---|---|---|
| `.github/workflows/tests.yml` | push to main/develop and ready pull requests to main | Tier 1 + Tier 2 | blocker, contract, deterministic eval contracts, and coverage are Tier 1. Coverage runs on ready/non-draft pull requests targeting main and on push to main; it does not run merely on push to develop. Quarantine runs after merge as Tier 2. |
| `.github/workflows/quality.yml` | push to main/develop and pull requests to main | Tier 1 | doc sync, public diff name scan, public surface allowlist scan, L2 no-LLM scan, lint, format, security, and type checks |
| `.github/workflows/nightly.yml` | push to main, scheduled run, and manual dispatch | Tier 2 | full suite and package/onboarding smoke |
| `.github/workflows/benchmark.yml` | push to main and manual dispatch | Tier 2 | performance measurement |
| `.github/workflows/release.yml` | manual dispatch | Release | publishing workflow, not part of PR readiness |

## Tier 1 Blocking Checks

| # | Check | CI command or scope | Source workflow | Local command |
|---|---|---|---|---|
| 1 | blocker gate | public Core assertion sentinel, then `pytest -m blocker --timeout=120` | tests.yml | `python .github/scripts/run_public_core_assertions.py` then `pytest -m blocker -q --timeout=120` |
| 2 | contract gate | `pytest -m contract --timeout=120` | tests.yml | `pytest -m contract -q --timeout=120` |
| 3 | deterministic eval contracts | `scripts/run_eval_gate.sh` owns the provider-retirement, fail-fast, metrics, serialization, and report compatibility inventory plus the public Core sentinel | tests.yml | `scripts/run_eval_gate.sh` |
| 4 | coverage gate | `bash scripts/run_coverage_gate.sh` | tests.yml | `bash scripts/run_coverage_gate.sh` |
| 5 | doc-sync | `python .github/scripts/check_doc_sync.py` | quality.yml | same |
| 6 | public-diff-names | `python .github/scripts/check_public_diff_names.py` | quality.yml | same |
| 7 | public-surface-allowlist | `python .github/scripts/check_public_surface_allowlist.py` | quality.yml | same |
| 8 | l2-no-llm | `python .github/scripts/check_l2_no_llm.py` | quality.yml | same |
| 9 | lint flake8 | `flake8 tools/ --count --max-complexity=40 --max-line-length=100 --show-source --statistics` | quality.yml | same |
| 10 | format black | `black --check --diff tools/` | quality.yml | `python -m black --check tools/` |
| 11 | security bandit | `bandit -r tools/ -ll -c pyproject.toml` | quality.yml | same |
| 12 | typecheck mypy | `mypy tools/ --ignore-missing-imports` | quality.yml | same |

## Tier 2 Visible Checks

Tier 2 checks are visible post-merge or on scheduled/manual runs. They do not
block pull request readiness, but failures must be triaged.

| # | Check | Command or scope | Source workflow | Trigger |
|---|---|---|---|---|
| Q | quarantine | `pytest -m quarantine --timeout=300` | tests.yml | push to main |
| N | full suite | `pytest tests --timeout=600` | nightly.yml | push to main, schedule, manual |
| P | package/onboarding smoke | build package, install in clean environment, run version/bootstrap/health smoke | nightly.yml | push to main, schedule, manual |
| B | benchmarks | `pytest tests/benchmark --timeout=300` | benchmark.yml / nightly | push to main, manual |

## Scope Notes

- Format, lint, security, and type checks intentionally target `tools/`.
- The l2-no-llm check scans imports across deterministic tools and applies the
  structural AST policy above to `tools/search_journals`, `tools/smart_search`,
  and `tools/eval`.
- The blocker marker set spans the files collected by `pytest -m blocker`.
- Deterministic eval contract checks are Tier 1 because they protect provider
  retirement, fail-fast, serialization, and sentinel wiring. The workflow and
  pre-push gate delegate to `scripts/run_eval_gate.sh` so its no-argument path
  is the sole test-target inventory. Private corpus,
  broad/noise, ranking, and quality evaluation run through
  `scripts/run_eval_advisory.sh` and are not PR blockers.
- Full suite, quarantine, package smoke, and benchmarks are visible
  Tier 2 checks, not PR-blocking checks.
- Benchmark tests run on shared GitHub runners. Hard assertions use
  shared-runner-safe fail-safes; exact local performance targets should be read
  from printed measurements or a dedicated benchmark environment, not from
  sub-100ms wall-clock gates.

## Local Gate Entrypoints

Fast PR-readiness feedback:

```bash
scripts/tier1-gate.sh
```

Full merge-batch verdict:

```bash
scripts/pre-push-gate.sh
```

Before running the full gate, run cheap checks that match the current diff:

```bash
git diff --check
python .github/scripts/check_doc_sync.py
python .github/scripts/check_public_diff_names.py
python .github/scripts/check_public_surface_allowlist.py
python .github/scripts/check_l2_no_llm.py
```

Use focused tests for the changed behavior before launching the long gate.

## Required CI Report For Failures

When reporting a red required check, include:

```text
Workflow:
Conclusion:
Head SHA:
Failing job:
Failing test or step:
Relevant log excerpt:
Classification:
Recommended next action:
Files likely involved:
Does this need a maintainer decision? yes/no
```

## Maintenance Protocol

Any Tier 1 gate addition, deletion, or scope change must update all relevant
surfaces in the same commit:

1. GitHub workflow file.
2. Local gate script.
3. This inventory file.
4. Tests for any new gate logic.

The commit message should include `ci-hard-check inventory updated`.

Tier 2 changes must update the corresponding workflow and this inventory.

## Version History

- v1.2.1-public (2026-07-02): clarified Tier 2 benchmark thresholds as
  shared-runner fail-safes, not precise local performance gates.
- v1.2-public (2026-06-20): added public-surface-allowlist as a Tier 1 hard check.
- v1.1-public (2026-06-19): added L2 no-LLM scan as a Tier 1 hard check.
- v1.0-public (2026-06-18): curated the CI inventory for public visibility.
- v0.4 (2026-06-17): added public-diff-names as a Tier 1 hard check.
