# Life Index Versioning Contract

> **Document purpose**: Versioning and release policy for Life Index CLI
> **Audience**: Maintainers, agents, and release reviewers
> **Authority level**: This document defines release/versioning practice for Life Index CLI. It is subordinate to [`CHARTER.md`](../CHARTER.md); package version source remains [`pyproject.toml`](../pyproject.toml).
> **Effective baseline**: `v1.0.0`
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

## 9. Release Checklist

Before creating a release tag:

1. Decide version bump using this contract.
2. Update `pyproject.toml`.
3. Update `bootstrap-manifest.json`.
4. Update README version wording if present.
5. Update `CHANGELOG.md`.
6. Run version tests.
7. Run relevant quality gates.
8. Create annotated tag `vX.Y.Z`.
9. Push commit and tag.

## 10. Tag Policy

Git tags are release anchors. They should point to commits where:

- Version metadata is already updated.
- Changelog entry exists.
- Required checks have passed or are expected to pass.

Exploratory historical tags before this contract do not define formal version semantics.

## 11. Changelog Policy

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

## 12. Non-Versioned Work

The following do not trigger a version bump by themselves:

- `.kimi-learnings/` diagnostic reports.
- `.strategy/` plans.
- Sandbox verification.
- Unmerged experiments.
- Local user data changes such as `~/Documents/Life-Index/entity_graph.yaml`.
- Agent handoff notes.

They may support a later release, but they are not releases.

## 13. Governance

PATCH releases may be prepared by agents after passing relevant gates.

MINOR releases require explicit user confirmation of release scope.

MAJOR releases require explicit user approval plus migration and rollback planning.
