# Life Index Version Policy

> **Document role**: Define the active versioning policy for Life Index v1.x.
> **Audience**: Project owner, contributors, and operators who need to understand release semantics.
> **Authority**: Active policy document for version meaning; package version value remains sourced from `pyproject.toml`.

---

## 1. Scope

This document defines what version numbers mean in the Life Index project during the v1.x series.

It does **not** define the full upgrade workflow or compatibility procedure. Those belong in dedicated upgrade and compatibility guidance.

---

## 2. Current Version Source of Truth

The current package version value is declared in:

- `pyproject.toml`

This document explains **how to interpret** version changes. It does not replace the version field itself.

---

## 3. Versioning Model for v1.x

Life Index uses **SemVer-lite** for v1.x, with a stronger bias toward user data and configuration safety than toward internal implementation purity.

The practical meaning is:

- the project still uses `MAJOR.MINOR.PATCH`
- version decisions are judged primarily by impact on durable user assets and operator workflow
- internal refactors alone do not justify a breaking-version interpretation unless they force user action

---

## 4. Patch

Use a **patch** version bump when changes are any combination of:

- bug fixes
- documentation corrections or clarification
- onboarding, schedule, or operator-flow wording fixes
- internal refactors with no required user action
- performance or reliability improvements that do not change migration needs

### Patch expectation

Patch releases should not require manual migration of user journals or configuration.

If any post-upgrade action is suggested in a patch release, it should normally be limited to lightweight validation or rebuild of non-durable index/cache state.

---

## 5. Minor

Use a **minor** version bump when changes introduce:

- new user-visible capability
- meaningful expansion of existing commands or workflows
- new optional review, automation, or reporting patterns
- new metadata or search behavior that remains backward-compatible for existing user data and config

### Minor expectation

Minor releases may require users to read release notes and may require lightweight maintenance actions such as `life-index index`, but they should still preserve normal upgrade continuity.

An existing user should be able to upgrade to a minor release without manual migration of durable user assets.

---

## 6. Major

Use a **major** version bump when any of the following becomes true:

- manual migration is required for journals, frontmatter, config, or attachments
- old CLI behavior is intentionally broken or removed in a way that affects normal users
- existing installation or upgrade instructions are no longer sufficient without special handling
- compatibility promises for durable user assets can no longer be maintained

### Major expectation

Major releases require explicit migration guidance.

If the project cannot safely preserve normal user upgrade continuity for durable assets, the change should be treated as major rather than hidden inside a minor or patch release.

---

## 7. Breaking Change Definition for Life Index

For this project, a breaking change is defined primarily by **user asset compatibility** and **operator workflow breakage**, not by internal refactoring alone.

### Usually breaking

- journal or frontmatter incompatibility
- configuration incompatibility
- required operator action beyond the normal upgrade path, unless clearly documented as a narrow maintenance step
- CLI behavior changes that invalidate existing normal usage

### Usually not breaking by itself

- internal module refactors
- implementation cleanup with stable user-facing behavior
- rebuild-only index/cache changes, if durable user assets remain intact

---

## 8. Compatibility Bias During v1.x

During v1.x, the project should default to protecting these assets:

- `~/Documents/Life-Index/Journals/`
- attachment files
- `~/Documents/Life-Index/.life-index/config.yaml`

This means version decisions should favor:

- backward compatibility for durable user data
- explicit release notes when operator action is required
- rebuild of indexes/caches instead of risky migration of user-owned data whenever possible

---

## 9. Relationship to Other Release Documents

This document should be read together with:

- `docs/CHANGELOG.md` for release history and release-facing notes
- distribution strategy documentation for the currently preferred install/distribution path
- future upgrade and compatibility guidance when those documents are formalized

---

## 10. Maintainer Rule of Thumb

When deciding between patch, minor, and major, ask these questions in order:

1. Does this require users to migrate journals, config, or attachments?
   - If yes, it is major.
2. Does this add meaningful user-visible capability while keeping durable assets compatible?
   - If yes, it is minor.
3. Is this mainly a fix, clarification, or internal improvement with no migration burden?
   - If yes, it is patch.

If uncertain, prefer the interpretation that is safer and clearer for users upgrading a local-first system.
