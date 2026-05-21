# Life Index Changelog

This changelog records user-visible releases for the Life Index CLI line.

Versioning follows [`docs/VERSIONING.md`](docs/VERSIONING.md). Earlier exploratory tags are treated as pre-contract history and no longer define formal release semantics.

## [Unreleased]

### Added

- `entity-graph-eval` command: graph ablation evaluation that runs search across 8 pipeline combinations (entity_graph × semantic × hybrid) and reports P@5 / R@5 / MRR@5 for each. Default path is fully deterministic — zero LLM calls. Invoked via `life-index entity-graph-eval --queries <fixture>` or `python -m tools.eval.ablation --queries <fixture>`. Output schema: `gbrain-ablation.v1`. (gbrain absorption Phase A)
- Public JSON outputs for `search`, `smart-search`, `aggregate`, `entity`, `timeline`, and `health` now include a top-level `schema_version` field for forward-compatible contract tracking.
- `on-this-day` command is now discoverable in agent navigation docs (`AGENTS.md`, `SKILL.md`).
- `entity --candidate-edges --output=json`: read-only candidate relationship edge report scanning journal `people` co-occurrence, `related_entries`, wikilinks, and body co-occurrence. Outputs deduplicated JSON with evidence paths, confidence scores, and suggested actions. Zero production graph writes.
- `recall` command: L3 recall module providing three search modes (`default` / `recall` / `deep`) via subprocess delegation to L2 search/smart-search. `default` mode uses pure FTS; `recall` mode uses hybrid search; `deep` mode requires explicit `--use-llm` opt-in (degrades to `recall` without it). Zero default LLM calls.
- `search --enable-source-tier`: opt-in source-tier ranking boost (gbrain absorption Phase B). Applies evidence-quality multipliers based on document frontmatter richness (`journal_rich` 1.08× / `journal_standard` 1.04× / `journal_basic` 1.00×). Default off to preserve exact backward compatibility. Ablation eval shows flat delta on current fixture; documented in `.strategy/cli/2026-05-21-source-tier-eval-result.md`.
- `maintenance` command: dry-run/report-only maintenance cycle aggregating six health checks (index freshness, entity audit, orphan related entries, search eval smoke, backup verification, candidate edges count) without production writes. All external CLI calls delegated via subprocess. Default path is fully deterministic — zero LLM imports.

### Changed

- `docs/API.md` contract documentation aligned with current CLI parameter defaults, error-code classifications, and M16 `schema_version` policy.

## [1.0.1] - 2026-05-20

### What users get

- Historical same-day recall is now available through a stable CLI command.
- The public CLI contract and layer-boundary gates have a Foundation Freeze v1 checkpoint behind this release.

### Included in this release

- `on-this-day` command: deterministic same-month/day recall aid that finds prior-year journal entries sharing today's (or a specified) date. Consumes the existing `timeline` CLI via subprocess. Supports `--date`, `--years-back`, `--limit`, and `--json` flags.
- Public JSON contract documentation and contract tests for core CLI surfaces, including search, smart-search, aggregate, analyze, entity, timeline, health, and generate-index.
- Hard layer-invariant CI guard preventing the L2 default path from importing LLM clients or depending on L3 orchestrators.

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
