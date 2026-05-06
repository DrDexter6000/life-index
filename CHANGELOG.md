# Life Index Changelog

This changelog records user-visible releases for the Life Index CLI line.

Versioning follows [`docs/VERSIONING.md`](docs/VERSIONING.md). Earlier exploratory tags are treated as pre-contract history and no longer define formal release semantics.

## [Unreleased]

- No unreleased changes yet.

## [1.0.0] - 2026-05-06

### What users get

- Life Index CLI Core reaches the first formal stable baseline under the conservative versioning contract.
- The public repository history has been privacy-cleaned and normalized for future public maintenance.
- The CLI remains the product source of truth for local-first journal writing, search, eval, and Entity Graph workflows.

### Included in this release

- **Local-first journal archive**: Markdown + YAML frontmatter stored outside the code repository in the user's Life Index data directory.
- **Agent-native CLI workflow**: structured commands for write, confirm, search, smart-search, edit, abstract, index, backup, verify, migrate, eval, entity, health, and version operations.
- **Search and eval quality gates**: keyword/hybrid search evaluation, broad-eval soft gate, frozen eval anchors, and regression tests for retrieval behavior.
- **Entity Graph baseline**: operating contract, alias expansion, observer-scoped family role labels, relationship phrase search, and production validation workflow.
- **CI hard gates**: blocker tests, contract checks, quality checks, benchmark workflow, and search eval quality gate.
- **Versioning contract**: conservative product SemVer with long-lived `1.0.x` patch cadence, cautious `1.x.0` minor bumps, and `2.0.0` reserved for product-generation changes such as mobile or multi-device form factors.
