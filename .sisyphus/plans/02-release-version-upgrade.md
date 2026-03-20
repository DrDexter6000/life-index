# Release / Version / Upgrade

Status: open
Priority: P1
Owner: current CTO discussion track
Scope: define how Life Index should publish new versions and how users should safely upgrade.

## Core question

What is the smallest release and upgrade model that gives users predictable updates without introducing unnecessary operational burden?

## Why this topic matters

- Shipping new capabilities without a clear upgrade path increases support burden.
- Version semantics affect trust, rollback expectations, and compatibility promises.
- Local-first applications must be explicit about data safety during upgrades.

## Decision target

Produce a short conclusion set that answers:

1. What versioning scheme to use
2. How releases are published
3. How users upgrade
4. What compatibility guarantees exist for user data and config
5. What kinds of changes require special migration guidance

## Required subtopics

### 1. Version number policy

Questions to answer:
- Should the project use SemVer strictly, loosely, or a simpler variant?
- What qualifies as major / minor / patch in this repo?
- How should documentation-only releases be handled?

### 2. Release packaging model

Questions to answer:
- Is the supported user path still git clone + venv + pip install -e .?
- Should tagged releases become the official upgrade anchor?
- Is there a future need for packaged distribution beyond the current repo-first path?

### 3. User upgrade workflow

Questions to answer:
- What exact commands should an existing user run to upgrade safely?
- When should they rebuild indexes, rerun health, or rerun onboarding verification?
- What is the minimal post-upgrade validation checklist?

### 4. Data and config compatibility

Questions to answer:
- What compatibility promise is made for `~/Documents/Life-Index/` contents?
- What compatibility promise is made for `.life-index/config.yaml`?
- How should breaking changes be announced and migrated?

### 5. Migration triggers

Questions to answer:
- Which kinds of changes require explicit migration notes?
- Which kinds of changes require automatic migration tooling, if any?
- Which kinds of changes should block release until upgrade instructions exist?

## Evaluation criteria

For each proposed release/upgrade policy, evaluate:

- simplicity for end users
- maintainability for the project owner
- safety for local data
- clarity of operator instructions
- support burden when users skip versions
- consistency with the current repo-first distribution model

## Guardrails

- Do not design an enterprise release process unless the project truly needs it.
- Do not promise compatibility levels the repo cannot realistically uphold.
- Do not force migration machinery unless manual guidance is insufficient.
- Keep the policy understandable enough that an external agent can execute it correctly.

## Open questions to resolve in discussion

1. What is the official supported upgrade path today?
2. What should count as a breaking change for this product?
3. Should every user-visible change require a changelog entry and upgrade note?
4. When should a version bump be patch vs minor vs major?
5. What is the minimum safe “upgrade validation” after pulling a new version?

## Expected deliverables from this discussion

- a recommended versioning policy
- a minimal release checklist
- a minimal upgrade checklist for existing users
- a compatibility statement for data/config expectations

## First-round repo-grounded findings

### Current release reality

- The actual supported user path today is **repo-first**:
  - `git clone`
  - `python -m venv .venv`
  - `pip install -e .`
  - `life-index health`
  - `life-index index`
- This path is consistently reflected by:
  - `README.md`
  - `README.en.md`
  - `AGENT_ONBOARDING.md`
  - `docs/review/execution/DISTRIBUTION_STRATEGY.md`
- `pyproject.toml` currently declares `version = "1.2.0"`, so the repo does already maintain a formal version field.
- The project has maintainer-side release capability signals (release automation / archived release playbook), but these are not yet the clear user-facing upgrade contract.

### Current distribution truth

- The preferred and actively justified distribution strategy is still:
  - git repository + local virtual environment + editable install
- `docs/review/execution/DISTRIBUTION_STRATEGY.md` explicitly says no alternative path is currently justified.
- PyPI, Homebrew, Docker, and MCP distribution are all documented as not pursued / deferred.

### Current changelog truth

- `docs/CHANGELOG.md` exists, but it is milestone/date oriented rather than versioned user-upgrade guidance.
- It records important project history, but it does not yet function as a clear release-notes contract for users upgrading from one version to another.

### Current upgrade truth

- The repo implicitly supports upgrade-by-repulling-source and reinstalling editable dependencies.
- The strongest existing hint appears in `DISTRIBUTION_STRATEGY.md`:
  - update simplicity is effectively `git pull && pip install -e .`
- However, this is not yet elevated into a fully explicit, official end-user upgrade policy.

## First-round gap analysis

### Gap 1 — Upgrade anchor is unclear

The repo does not yet clearly state whether users should conceptually upgrade by:

- following `main`
- following tagged releases
- following GitHub Releases notes

### Gap 2 — Version semantics are not yet defined

The repo has a version number, but not yet a public rule for:

- patch vs minor vs major
- what counts as breaking change
- when migration guidance becomes mandatory

### Gap 3 — No official post-upgrade validation contract

The repo has the ingredients (`health`, `index`, write/search workflows), but not yet a concise upgrade verification checklist.

### Gap 4 — Compatibility statement is missing

There is not yet one explicit statement that differentiates:

- durable user assets that should remain backward-compatible
- rebuildable indexes/caches that may be regenerated safely

## First-round strategic recommendation

### Core recommendation

Treat Life Index v1.x as:

- **repo-first**
- **release-tagged**
- **data/config backward-compatible by default**
- **index/cache rebuildable rather than compatibility-critical**

### Why this is the cleanest direction now

- It matches the repo's actual installation and distribution reality
- It avoids prematurely introducing package/distribution surface area
- It fits a local-first product where user journals and config matter more than index internals
- It creates a clear rule for future versioning and upgrade communication

## First-round versioning recommendation

### Proposed policy: SemVer-lite with strong data-compatibility bias

#### Patch

- bug fixes
- docs fixes
- onboarding/schedule wording
- internal refactors with no user migration or compatibility impact

#### Minor

- new user-visible capability
- expanded tool behavior
- new optional workflows
- still backward-compatible for journals and config

#### Major

- required manual migration
- on-disk compatibility break
- frontmatter/config contract break
- CLI semantics break that invalidates existing user workflows

## First-round upgrade-path recommendation

### Minimum official upgrade path candidate

1. Back up `~/Documents/Life-Index/`
2. Update the repo to the intended version/tag
3. Re-run `pip install -e .` inside the project venv
4. Run `life-index health`
5. Run `life-index index`
6. Use `python -m tools.build_index --rebuild` only if release notes require it or health/search signals a problem
7. Verify with at least one known search against existing data

## First-round compatibility stance

### Should be treated as durable/backward-compatible by default

- `~/Documents/Life-Index/Journals/`
- attachments
- `~/Documents/Life-Index/.life-index/config.yaml`

### Should be treated as rebuildable cache/state

- `.index/`
- metadata/search/vector index artifacts

## First-round minimum post-upgrade verification candidate

1. `life-index health`
2. one known search against existing journals
3. if release notes mention index/search changes, run `life-index index`
4. if health or search still looks wrong, use rebuild flow

## First-round conclusion

Before changing formal release docs, the maintainer should explicitly settle one contract:

> v1.x is repo-first, release-tagged, backward-compatible for user data/config by default, and allowed to rebuild indexes when needed.

That single contract should drive the next round of concrete policy writing.

## Second-round policy draft

### Policy 1 — Versioning policy draft

#### Recommended rule set

Use **SemVer-lite** for v1.x, with a stronger standard for user data/config compatibility than for internal implementation details.

#### Patch version bump

Use patch when changes are any combination of:

- bug fixes
- docs corrections or workflow clarifications
- onboarding/schedule/reporting wording fixes
- internal refactors with no required user action
- performance/reliability improvements that do not change user migration needs

#### Minor version bump

Use minor when changes introduce:

- new user-visible capabilities
- meaningful expansion of existing commands/workflows
- new optional review/automation/reporting patterns
- new metadata/search behavior that remains backward-compatible for existing data and config

Minor is still acceptable only if an existing user can upgrade without manual data migration.

#### Major version bump

Use major when any of the following becomes true:

- manual migration is required for journals, frontmatter, config, or attachments
- old CLI behavior is intentionally broken or removed in a way that affects normal users
- existing installation/upgrade instructions are no longer sufficient without special handling
- compatibility promises for durable user assets can no longer be maintained

#### Breaking-change definition for this project

For Life Index, a breaking change should be defined primarily by **user asset compatibility and operator workflow breakage**, not by internal refactors alone.

That means:

- journal/frontmatter/config incompatibility is breaking
- required operator action beyond the normal upgrade path is breaking unless explicitly documented as a minor-but-mandatory maintenance step
- rebuild-only index changes are not automatically breaking if the durable user assets remain intact

### Policy 2 — Official upgrade path draft

#### Official supported upgrade anchor for v1.x

Treat the official upgrade anchor as:

- **release-tagged repo updates** when formal releases are cut
- otherwise, the current repo-first update path still exists for advanced/operator users, but should not be the ideal end-user contract long term

#### Minimum supported upgrade workflow

1. Back up `~/Documents/Life-Index/`
2. Update the local checkout to the intended release tag or approved target revision
3. Re-run `pip install -e .` inside the existing project venv
4. Run `life-index health`
5. Run `life-index index`
6. Only run rebuild flow if release notes, health, or search validation indicate it is needed
7. Verify at least one known search result against existing journals

#### Recovery rule

If the venv is stale or broken after Python changes or interrupted installs:

- recreate `.venv/`
- reinstall with `pip install -e .`
- continue with the same post-upgrade validation flow

### Policy 3 — Post-upgrade validation checklist draft

#### Minimum safe checklist

Every supported user upgrade should be verifiable with this minimum checklist:

1. `life-index health` succeeds and does not report an unhealthy state
2. one known search against existing data returns expected results
3. if release notes mention index/search/semantic changes, run `life-index index`
4. if health/search still look wrong, escalate to rebuild flow

#### Optional stronger checklist

For cautious operators or releases that touched retrieval/indexing:

1. confirm current config can still be read
2. perform one small write test
3. perform one search for the just-written entry

### Policy 4 — Compatibility and migration statement draft

#### Durable compatibility promise

During v1.x, the project should aim to keep these backward-compatible by default:

- `~/Documents/Life-Index/Journals/`
- attachment files
- `~/Documents/Life-Index/.life-index/config.yaml`

#### Rebuildable state promise

The project may treat these as rebuildable operational state rather than durable compatibility-critical assets:

- `.index/`
- search/metadata/vector cache artifacts

#### Migration-note trigger

Release notes and upgrade guidance become mandatory when changes affect:

- frontmatter contract
- config schema or semantics
- search/index behavior that requires explicit operator action
- installation or CLI usage that differs from the normal upgrade path

#### Migration-tool trigger

Automatic migration tooling should be considered only when manual instructions would be too error-prone for ordinary users or when durable user assets would otherwise be at risk.

## Second-round strategic recommendation

Before touching formal release docs, the maintainer should explicitly settle these four policy drafts as the active v1.x contract:

1. SemVer-lite with data-compatibility bias
2. release-tagged repo-first upgrade path
3. minimum post-upgrade validation checklist
4. durable-assets-vs-rebuildable-state compatibility statement

Once these are accepted, the next step is not more strategy expansion — it is converting them into a concise doc cleanup / formalization plan.

## Third-round formalization plan

### Formalization principle

Do not spread release/upgrade policy evenly across every document.

Instead:

- put operator-facing install/upgrade instructions where users and agents already look for them
- keep historical milestone logging separate from upgrade policy
- keep deep rationale in review/planning documents rather than forcing all of it into Tier 1 docs

## File-by-file formalization targets

### 1. `README.md`

**Role after formalization**:

- end-user entry point
- installation path
- short upgrade pointer

**Should include**:

- a short statement that current supported distribution remains repo-first
- a short pointer to the official upgrade instructions once they exist
- a short pointer to release notes / changelog location

**Should not include**:

- full versioning policy
- full compatibility policy
- long migration rules

### 2. `README.en.md`

**Role after formalization**:

- English mirror of README-level user guidance

**Should include**:

- the same short upgrade pointer structure as `README.md`

**Should not include**:

- a divergent or simplified release contract different from the Chinese README

### 3. `AGENT_ONBOARDING.md`

**Role after formalization**:

- fresh-install operational guide for agents

**Should include**:

- only a minimal note that upgrades should follow the official upgrade guidance if the task is upgrade rather than fresh install

**Should not include**:

- full release/version policy
- full migration policy
- duplicate upgrade checklist content unless strictly necessary

### 4. `docs/CHANGELOG.md`

**Role after formalization**:

- version and milestone history
- release notes anchor

**Should include**:

- clearer structure for future version-tagged entries
- release-facing notes when user action is required
- explicit mention when an upgrade requires rebuild, migration, or manual action

**Should not include**:

- the full SemVer policy explanation
- the full installation guide

### 5. `docs/review/execution/DISTRIBUTION_STRATEGY.md`

**Role after formalization**:

- rationale document explaining why repo-first distribution remains preferred

**Should include**:

- the strategic justification for repo-first distribution
- revisit conditions for PyPI / installers / MCP

**Should not include**:

- the operator-facing upgrade steps as the main source of truth once those steps are formalized elsewhere

### 6. `pyproject.toml`

**Role after formalization**:

- version source of truth for the package metadata

**Should include**:

- the current version field only

**Should not include**:

- explanatory release policy text

### 7. `.github/workflows/release.yml`

**Role after formalization**:

- maintainer automation implementation detail

**Should include**:

- tag-triggered publish behavior only

**Should not be treated as**:

- the user-facing release contract by itself

## Recommended allocation of the four policy areas

### Policy area A — Versioning rules

**Primary home**:
- new formal policy doc or dedicated active policy section referenced from Tier 1 docs

**Secondary references**:
- `docs/CHANGELOG.md`
- README navigation/reference area

### Policy area B — Official upgrade path

**Primary home**:
- dedicated upgrade guide doc

**Secondary references**:
- README / README.en short pointers
- AGENT_ONBOARDING minimal handoff for upgrade situations

### Policy area C — Post-upgrade validation checklist

**Primary home**:
- the same upgrade guide doc

**Secondary references**:
- release notes/changelog entries when special steps are needed

### Policy area D — Compatibility / migration statement

**Primary home**:
- dedicated compatibility policy doc

**Secondary references**:
- upgrade guide
- changelog entries when compatibility-relevant changes happen

## What should remain review-only for now

These parts are still better kept in planning/review artifacts until formal docs are actually authored:

- broad rationale for choosing SemVer-lite instead of stricter SemVer
- long-form tradeoff analysis about PyPI vs git distribution
- speculative future packaging expansion discussion
- implementation sequencing beyond immediate doc formalization

## Proposed formal-doc rollout order

1. formalize versioning policy
2. formalize upgrade guide
3. formalize compatibility / migration statement
4. align `docs/CHANGELOG.md` to reference the new policy surfaces
5. add short pointers/cross-references in README / README.en / onboarding if needed

## Why this rollout order is best

- versioning policy defines the language used by all later docs
- upgrade guide depends on knowing what counts as normal vs special user action
- compatibility statement clarifies when upgrade notes become mandatory
- changelog alignment should happen after the policy surfaces exist
- README/onboarding should point to settled docs, not draft wording

## Third-round conclusion

The next move toward formal docs should not be a giant rewrite.

It should be a controlled documentation formalization pass that:

- creates or designates the primary homes for versioning, upgrade, and compatibility policy
- keeps README/onboarding lightweight
- preserves `CHANGELOG.md` as historical/release-note surface rather than overloading it with all policy detail

## Exit condition

This topic is not closed until we have:

- a concrete versioning recommendation
- a concrete publish/release flow
- a concrete user-upgrade flow
- an explicit statement about compatibility and migration expectations
