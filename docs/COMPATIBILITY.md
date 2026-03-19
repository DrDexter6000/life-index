# Life Index Compatibility Statement

> **Document role**: Define the active compatibility and migration stance for Life Index v1.x.
> **Audience**: Project owner, contributors, operators, and users who need to understand what upgrades are expected to preserve.
> **Authority**: Active compatibility policy for durable user assets versus rebuildable operational state.

---

## 1. Scope

This document defines the compatibility expectations for Life Index during the v1.x series.

It explains which assets should remain backward-compatible by default, which state can be rebuilt, and when migration guidance becomes mandatory.

---

## 2. Core Compatibility Principle

Life Index is a local-first system.

During v1.x, compatibility decisions should favor protection of user-owned durable assets over preservation of every internal cache or index artifact.

The guiding principle is:

- preserve journals and user configuration when possible
- rebuild operational search/index state when that is the safer path
- require explicit migration guidance whenever durable assets or normal operator workflows are at risk

---

## 3. Durable Assets That Should Remain Backward-Compatible by Default

The project should aim to preserve compatibility for these assets throughout v1.x:

- `~/Documents/Life-Index/Journals/`
- attachment files stored for journal usage
- `~/Documents/Life-Index/.life-index/config.yaml`

### Practical meaning

For normal patch and minor releases, users should not be forced to manually rewrite or migrate these assets under ordinary conditions.

If a change would require such migration, it should be treated as a stronger release event and documented explicitly.

---

## 4. Rebuildable Operational State

The project may treat the following as rebuildable operational state rather than durable compatibility-critical assets:

- `.index/`
- metadata cache artifacts
- search index artifacts
- vector index artifacts

### Practical meaning

If these states become outdated or incompatible with new internals, the preferred remedy is usually:

- refresh
- re-index
- rebuild

rather than risky mutation of user-owned journals or configuration.

---

## 5. Migration-Note Trigger

Release notes and upgrade guidance become mandatory when a release affects any of the following:

- frontmatter contract
- config schema or config semantics
- search/index behavior that requires explicit operator action
- installation or CLI usage that differs from the normal supported upgrade path

### Practical meaning

If an operator must do more than the normal upgrade flow, the release should say so explicitly.

Silently requiring rebuilds, compatibility checks, or data-handling changes is not acceptable once those steps become materially important.

---

## 6. Migration-Tool Trigger

Automatic migration tooling should be considered only when manual instructions would be too error-prone for ordinary users or when durable user assets would otherwise be at risk.

### Use migration tooling only if at least one is true

- manual migration would likely damage journals or config
- the required migration is too repetitive or fragile for normal operators
- the project cannot reasonably expect users to perform the change safely by hand

### Do not add migration tooling by default

Migration tooling should not be introduced merely to avoid writing clear upgrade guidance.

If clear manual guidance is sufficient and safe, that is preferred during v1.x.

---

## 7. Relationship to Versioning

Compatibility affects release version meaning.

In practice:

- durable asset incompatibility is usually a breaking change
- rebuild-only operational state changes are not automatically breaking
- compatibility risk should influence whether a release is treated as patch, minor, or major

See `docs/VERSION_POLICY.md` for the formal versioning interpretation.

---

## 8. Relationship to Upgrade Guidance

This document defines what should remain compatible.

The upgrade guide defines what users should do during an upgrade.

Use this document together with:

- `docs/UPGRADE.md`
- `docs/VERSION_POLICY.md`
- `docs/CHANGELOG.md`

---

## 9. Maintainer Rule of Thumb

Before shipping a release, ask:

1. Does this change risk journals, attachments, or config?
2. If yes, is the change still backward-compatible?
3. If not, has the release been classified appropriately and paired with explicit migration guidance?
4. If the problem is only with indexes/caches, can rebuild be the safe default instead?

If unsure, prefer the path that protects durable user assets and makes required operator action explicit.
