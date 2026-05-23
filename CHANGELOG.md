# Life Index Changelog

This changelog records user-visible releases for the Life Index CLI line.

Versioning follows [`docs/VERSIONING.md`](docs/VERSIONING.md). Earlier exploratory tags are treated as pre-contract history and no longer define formal release semantics.

## [Unreleased]

## [1.1.1] - 2026-05-23

### What users get

- Six generating commands (`search`, `index`, `eval`, `entity`, `maintenance`, `trajectory`) now emit a top-level `schema_version: "v1.1.1"` and a `provenance` envelope with stable source hash, tool version, timestamp, and generator identity. This makes every JSON output auditable and reproducible without changing any result semantics.
- `search --explain`, `smart-search --explain`, and `index --explain` now include a deterministic `diagnostics` block showing input count, cache hits/misses, latency breakdown, and fallback path — zero LLM calls, purely additive.
- `index --cache-dry-run` lets you preview whether a cache rebuild would be triggered before any write happens.
- `health --cache-audit --json` provides a read-only cache version status check.
- Four intermediate structures (`QueryPlan`, `SearchPlan`, `IndexManifest`, `EntityExpansion`) now carry an explicit `schema_version: "v1.1.1"` so downstream consumers can recognize field semantics forward-compatibly. No behavior changes.
- Entity Graph aliases now support optional metadata (`source`, `confidence`, `created_at`) while remaining fully backward-compatible with old string-only alias lists.
- `entity --audit` and `entity --stats` echo a `boost_decay` placeholder formula as a v1.2.0 calibration preview. This is metadata-only and does not affect search ranking.

### Included in this release

- Provenance envelope: `schema_version`, `source_hash`, `tool_version`, `generated_at`, `generator`, `params_hash`, `fixture_version` (Sub-PRD-1, A1-A2).
- Step diagnostics for `--explain`: `input_count`, `filter_drops`, `cache_hits`, `cache_misses`, `latency_ms`, `fallback_path` (Sub-PRD-1, A3).
- Cache version governance: `.life-index/cache/_version.json` sidecar with `invalidation_history`; `index --cache-dry-run` and `health --cache-audit` read-only audit surfaces (Sub-PRD-1, A4).
- Intermediate contract schema versioning: `QueryPlan`, `SearchPlan`, `IndexManifest`, `EntityExpansion` all expose `schema_version: "v1.1.1"` (Sub-PRD-3, B3.1-B3.2).
- Entity Graph alias metadata backcompat: aliases accept string or `{name, source, confidence, created_at}` objects; defaults `source=system`, `confidence=1.0` (Sub-PRD-4, B4.1).
- `boost_decay` schema placeholder: echo-only metadata in `entity --audit/--stats` with `formula`, `k`, and calibration note; no search ranking effect (Sub-PRD-4, B4.2).
- Contract tests: 28+ provenance envelope tests, 13 diagnostics contract tests, 20 cache version contract tests, 20+ intermediate contract tests, 15+ entity graph schema tests (Gate 1 + Gate 2).
- docs/API.md: v1.1.1 Observability Contract section (provenance, diagnostics, cache governance) plus Phase B Intermediate Contracts section (QueryPlan, SearchPlan, IndexManifest, EntityExpansion, alias metadata, boost_decay).
- Version metadata alignment: `pyproject.toml`, `bootstrap-manifest.json`, `docs/VERSIONING.md`, and version unit tests aligned to `1.1.1`.

## [1.1.0] - 2026-05-21

### What users get

- Six new CLI capabilities matured into stable contract surface: graph ablation eval, opt-in source-tier ranking, candidate edge discovery, dry-run maintenance cycle, recall search modes, and trajectory observation extraction. All default paths remain deterministic — zero LLM imports — preserving Life Index's local-first privacy stance.
- All public CLI commands now expose a top-level `schema_version` field for forward-compatible contract evolution.
- New L3 recall and trajectory modules follow a strict subprocess-to-L2 boundary, codified by hard layer-invariant tests.

### Included in this release

- `entity-graph-eval` command: graph ablation evaluation across 8 pipeline combinations (entity_graph × semantic × hybrid) reporting P@5 / R@5 / MRR@5 deltas. Output schema `gbrain-ablation.v1`. (gbrain absorption Phase A)
- `search --enable-source-tier`: opt-in source-tier ranking boost using evidence-quality multipliers (`journal_rich` 1.08× / `journal_standard` 1.04× / `journal_basic` 1.00×). Default off to preserve exact backward compatibility. Ablation eval shows flat delta on current fixture; documented in `.strategy/cli/2026-05-21-source-tier-eval-result.md`. (Phase B)
- `entity --candidate-edges --output=json`: read-only candidate relationship edge report scanning journal `people` co-occurrence, `related_entries`, wikilinks, and body co-occurrence. Outputs deduplicated JSON with evidence paths, confidence scores, and suggested actions. Zero production graph writes. (Phase C)
- `maintenance` command: dry-run/report-only maintenance cycle aggregating six health checks (index freshness, entity audit, orphan related entries, search eval smoke, backup verification, candidate edges count) without production writes. All external CLI calls delegated via subprocess. Default path is fully deterministic — zero LLM imports. (Phase D)
- `recall` command: L3 recall module providing three search modes (`default` / `recall` / `deep`) via subprocess delegation to L2 search/smart-search. `default` uses pure FTS; `recall` uses hybrid search; `deep` requires explicit `--use-llm` opt-in (degrades to `recall` without it). Zero default LLM calls. (Phase E)
- `trajectory` command: read-only typed observation extraction for `weight`, `sleep`, `mood`, `location`, and `project` across a month range. Consumes the L2 `search` CLI via subprocess, returns traceable `evidence_paths`, performs zero L1 schema writes, and has no default LLM calls. (Phase F)
- Public JSON outputs for `search`, `smart-search`, `aggregate`, `entity`, `timeline`, and `health` now include a top-level `schema_version` field for forward-compatible contract tracking.
- `on-this-day` command is now discoverable in agent navigation docs (`AGENTS.md`, `SKILL.md`).
- L3 boundary invariant tests for `trajectory` and `candidate-edges` modules.
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
