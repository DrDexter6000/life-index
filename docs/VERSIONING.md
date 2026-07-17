# Life Index Versioning Contract

> **Document purpose**: Public version semantics and release artifact contract for Life Index CLI
> **Audience**: Maintainers and users reading the public repository
> **Authority level**: This document defines public release/version semantics for Life Index CLI. It is subordinate to [`CHARTER.md`](../CHARTER.md); package version source remains [`pyproject.toml`](../pyproject.toml).
> **Release state source**: package version comes from [`pyproject.toml`](../pyproject.toml); formal releases are recorded in [`CHANGELOG.md`](../CHANGELOG.md) and anchored by Git tags.
> **Status**: Active

---

## 1. Purpose

Life Index uses conservative product versioning. Version numbers describe the maturity and public contract of the CLI product, not the number of development rounds, experiments, or internal implementation phases.

Starting from `v1.0.0`, earlier exploratory tags are treated as pre-contract history and no longer define formal version semantics.

### Maturity-classifier boundary

`Development Status :: 5 - Production/Stable` in `pyproject.toml` describes the
released CLI product line and its stable public contracts. It does not assign
constitutional Core/non-Core ownership, certify every current route or option,
imply GUI 1.0 maturity, promise future features, or authorize a candidate for
merge, release, or publication. The GUI owns its separate `0.4.x` / pre-1.0
maturity statement in its own versioning contract.

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

## 7. Release Baselines

`v1.0.0` is the formal Life Index CLI Core baseline:

- Local-first Markdown journal storage.
- Agent-native CLI workflow.
- Search and smart-search.
- Eval quality gates.
- Entity Graph operating contract and relationship search.
- CI hard gates.
- Privacy-clean public repository history.

`v1.1.1` extends this baseline with additive observability contracts (provenance envelope, step diagnostics, cache version governance) and intermediate schema contracts (`QueryPlan`, `SearchPlan`, `IndexManifest`, `EntityExpansion`), plus Entity Graph alias metadata and `boost_decay` echo-only placeholder. No product behavior changes; all v1.1.0 clients remain compatible.

`v1.2.0` extends the baseline with Search Truthfulness / Recall-First as a
MINOR release because it changes user-visible search behavior across a complete
capability area while preserving CLI/data compatibility:

- L2 default search semantics reset to keyword-only under CHARTER §1.11, which
  was enshrined in commit `d5a2ad2`.
- Retrieval and presentation truncation are decoupled so evaluation and review
  can inspect the full candidate pool while user-facing output remains capped.
- Chinese temporal pattern normalization and the pure-temporal date-only branch
  recover date/month-only journal queries.

The frozen Cycle 2 multi-signal fixture measured Overall R@5 `0.7857`, C3
temporal R@5 `1.0000`, and no C1/C4 regression. The overall score is a marginal
miss versus the `0.79` target, accepted by the release owner as compatible with
the CHARTER §1.11 recall-first precision trade-off.

Life Index can remain on the `1.x` line for a long time. That is expected.

## 8. Source of Truth

Release authority is split by role. Do not duplicate the current package
version in general-purpose docs.

| Surface | Role |
|---------|------|
| [`pyproject.toml`](../pyproject.toml) `[project].version` | Package version source of truth |
| [`bootstrap-manifest.json`](../bootstrap-manifest.json) `repo_version` | Machine-readable checkout/bootstrap compatibility version; must match `pyproject.toml` for formal releases |
| [`CHANGELOG.md`](../CHANGELOG.md) | Human-readable release history |
| Git tag `vX.Y.Z` | Release anchor |

For a formal release:

- `pyproject.toml` and `bootstrap-manifest.json` must agree.
- `CHANGELOG.md` must contain the release entry.
- The Git tag must point to the release commit.
- README/API docs should point to `life-index --version`, `CHANGELOG.md`, or
  this contract instead of hardcoding the current package version.

### Cross-Consumer Intake At Version Planning

When a new version line, milestone PRD, or contract-affecting release is being
planned, maintainers should review any local cross-consumer intake queue
available in the workspace. In the current Life Index CLI + GUI workspace, that
queue is `.strategy/CLI_CAPABILITY_REQUESTS.md`.

This intake queue is not a second roadmap and does not override the CLI release
contract. Its role is to make GUI and advanced-module needs visible before CLI
scope is locked:

- Accepted or planned request IDs must be recorded in the existing CLI PRD,
  roadmap milestone, or release planning notes.
- Delivered requests must have CLI docs, tests, schema/contract evidence, and a
  delivered version recorded before being treated as complete.
- Consumed requests may be summarized in the shared contract registry instead
  of remaining as active planning material.

Routine internal PATCH work with no public contract or consumer-interoperability
impact does not require a strategy intake review.

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
1.3.1
1.3.2
1.3.3
1.3.4
1.3.5
1.3.7
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

Before publishing a PyPI release, check `https://pypi.org/pypi/life-index/json`
for the target version. If the upload succeeds, add that version to the
known-used list in the next release-maintenance change so future filename
availability checks stay accurate.

## 10. Public Release Readiness

A public release is valid only when:

- The version bump follows this contract.
- Public version surfaces agree.
- `CHANGELOG.md` records the user-visible change.
- A GitHub Release exists for the same `vX.Y.Z` tag and is marked as the
  repository's latest release when it is the newest stable release.
- Required quality gates have a clear passing verdict.
- Contract-affecting releases have reviewed cross-consumer intake and recorded
  any accepted, rejected, deferred, or delivered request IDs in the existing
  planning/release artifacts.
- The release is anchored by a Git tag `vX.Y.Z`.

Detailed local release choreography and approval routing belong in private local
governance docs, not in this public versioning contract.

## 11. Tag Policy

Git tags are release anchors. They should point to commits where:

- Version metadata is already updated.
- Changelog entry exists.
- Required checks have passed or are expected to pass.

Updating `pyproject.toml`, `bootstrap-manifest.json`, and `CHANGELOG.md`, then
pushing the release commit, does not update the GitHub Releases sidebar by
itself. Formal release closeout must also create and push the matching
`vX.Y.Z` tag, create the GitHub Release from that tag, and verify that the
GitHub Release points at the intended release commit.

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
