# Life Index Versioning Contract

> **Document purpose**: Public version semantics and release artifact contract for Life Index CLI
> **Audience**: Maintainers and users reading the public repository
> **Authority level**: This document defines public release/version semantics for Life Index CLI. It is subordinate to [`CHARTER.md`](../CHARTER.md); package version source remains [`pyproject.toml`](../pyproject.toml).
> **Effective baseline**: `v1.1.1`
> **Status**: Active

---

## 1. Purpose

Life Index uses conservative product versioning. Version numbers describe the maturity and public contract of the CLI product, not the number of development rounds, experiments, or internal implementation phases.

Starting from `v1.0.0`, earlier exploratory tags are treated as pre-contract history and no longer define formal version semantics.

## 2. Version Format

Life Index CLI uses:

```text
MAJOR.MINOR.PATCH
```

Examples:

```text
1.0.0
1.0.1
1.1.0
2.0.0
```

## 3. Conservative Product SemVer

Life Index intentionally applies SemVer conservatively:

- `PATCH` is the default bump.
- `MINOR` requires a complete user-visible capability domain to mature.
- `MAJOR` requires a product-generation change, not merely an implementation change.

If the correct bump is unclear, choose `PATCH`.

## 4. PATCH: Default Release Lane

Use `1.0.x` for most normal work.

PATCH releases include:

- Bug fixes.
- CI, flaky test, or quality gate fixes.
- Documentation updates.
- Privacy cleanup.
- Eval baseline or golden-query adjustments.
- Search ranking small fixes.
- Entity Graph alias or relationship phrase refinements.
- Internal refactors that preserve user behavior.
- New tests.
- Compatible schema migrations.
- CLI output improvements that do not change the core workflow.

Examples:

```text
1.0.1  privacy-clean public repo and version reset
1.0.2  fix relationship phrase edge case
1.0.3  improve eval gate coverage
1.0.4  harden Entity Graph validation
```

## 5. MINOR: Complete Capability Maturity

Use `1.x.0` only when a full capability area becomes product-stable.

A MINOR bump should satisfy at least two of the following:

- A user-visible workflow has become stable.
- Documentation, tests, eval, or validation coverage are complete enough to support the capability.
- The change represents a product-level stage, not a single patch.
- Existing CLI commands, data, and workflows remain compatible.

Examples:

```text
1.1.0  Entity Graph relationship search becomes a stable maintenance surface
1.2.0  Search quality reaches a new stable generation
1.3.0  GUI companion and CLI reach stable interoperability while CLI remains the core
```

Do not use MINOR for isolated changes such as:

- Adding one relationship phrase.
- Fixing one ranking bug.
- Adding one eval metric.
- Updating one formal document.
- Adding a few aliases to the Entity Graph.

Those are PATCH changes.

## 6. MAJOR: Product Generation Change

Use `2.0.0` only for a product-generation shift.

For Life Index, MAJOR is reserved for changes at the level of:

- Mobile app release.
- Multi-device product generation.
- Cloud sync or account system.
- GUI becoming a first-class primary product instead of a companion.
- Data model generation shift requiring explicit user migration.
- CLI contract changes that make old automation meaningfully incompatible.

Implementation-level breakage alone is not sufficient. A MAJOR bump should mean the product shape has changed.

## 7. Current Baseline

`v1.0.0` is the formal Life Index CLI Core baseline:

- Local-first Markdown journal storage.
- Agent-native CLI workflow.
- Search and smart-search.
- Eval quality gates.
- Entity Graph operating contract and relationship search.
- CI hard gates.
- Privacy-clean public repository history.

`v1.1.1` extends this baseline with additive observability contracts (provenance envelope, step diagnostics, cache version governance) and intermediate schema contracts (`QueryPlan`, `SearchPlan`, `IndexManifest`, `EntityExpansion`), plus Entity Graph alias metadata and `boost_decay` echo-only placeholder. No product behavior changes; all v1.1.0 clients remain compatible.

Pending `v1.2.0` release candidate: Search Truthfulness / Recall-First makes search quality a user-visible product generation within the `1.x` line by aligning default retrieval with CHARTER §1.11, preserving keyword-only L2 defaults, recovering pure temporal Chinese queries through a date-only branch, and validating the change against the frozen Cycle 2 multi-signal fixture. This is not a formal baseline change until release artifacts and Git tag agree.

Life Index can remain on `1.0.x` for a long time. That is expected.

## 8. Source of Truth

Release state must stay aligned across:

| Surface | Role |
|---------|------|
| [`pyproject.toml`](../pyproject.toml) `[project].version` | Package version source of truth |
| [`bootstrap-manifest.json`](../bootstrap-manifest.json) `repo_version` | Agent/bootstrap compatibility version |
| [`README.md`](../README.md) | Public user-facing current version |
| [`CHANGELOG.md`](../CHANGELOG.md) | Human-readable release history |
| Git tag `vX.Y.Z` | Release anchor |

For a formal release, all five surfaces must agree.

## 9. PyPI Distribution Constraint

GitHub Release is the release/version SSOT. PyPI is an optional distribution
channel and must not override this contract.

Due to pre-contract PyPI uploads, several `life-index` distribution filenames
have already been used. PyPI does not allow re-uploading a distribution file
with the same filename, even if the corresponding PyPI release or file is later
deleted.

Known PyPI-used versions:

```text
1.0.0
1.3.0
1.4.0
1.5.0
1.5.5
1.6.0
1.6.5
```

These versions are not available for future PyPI publication. In particular,
do not attempt to publish `life-index` `1.0.0` to PyPI.

The first clean PyPI release after the `v1.0.0` baseline must be a future
natural PATCH release, currently expected to be `1.0.1` or later. Any retained
old PyPI release is only a namespace-reservation artifact and is not an
authoritative Life Index CLI release.

PyPI publishing is manual-only until explicitly re-enabled. Tag pushes must not
automatically publish to PyPI.

## 10. Public Release Readiness

A public release is valid only when:

- The version bump follows this contract.
- Public version surfaces agree.
- `CHANGELOG.md` records the user-visible change.
- Required quality gates have a clear passing verdict.
- The release is anchored by a Git tag `vX.Y.Z`.

Detailed local release choreography and approval routing belong in private local
governance docs, not in this public versioning contract.

## 11. Tag Policy

Git tags are release anchors. They should point to commits where:

- Version metadata is already updated.
- Changelog entry exists.
- Required checks have passed or are expected to pass.

Exploratory historical tags before this contract do not define formal version semantics.

## 12. Changelog Policy

[`CHANGELOG.md`](../CHANGELOG.md) records user-visible release history.

Use:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### What users get
- ...

### Included in this release
- ...
```

Do not use changelog entries to document every internal experiment, diagnostic report, or sandbox verification.

## 13. Non-Versioned Work

The following do not trigger a version bump by themselves:

- Internal planning notes.
- Local diagnostic reports.
- Sandbox verification.
- Unmerged experiments.
- Local user data changes such as `~/Documents/Life-Index/entity_graph.yaml`.
- Agent handoff notes or session state.

They may support a later release, but they are not releases.

## 14. Release Authority

PATCH releases are routine compatible releases.

MINOR releases require explicit owner confirmation of release scope.

MAJOR releases require explicit owner approval plus migration and rollback
planning.

Detailed approval mechanics are private local governance, not public version
semantics.
