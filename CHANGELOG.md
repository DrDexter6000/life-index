# Life Index Changelog

This changelog records user-visible releases for the Life Index CLI line.

Versioning follows [`docs/VERSIONING.md`](docs/VERSIONING.md). Earlier exploratory tags are treated as pre-contract history and no longer define formal release semantics.

## [Unreleased]

### Added

- `entity audit --json` provides a read-only Entity Graph health facade that
  combines structural checks, quality audit results, graph statistics, and a
  traffic-light next step for host agents.
- Entity Graph HITL review now exposes `why`, `evidence`, and
  `action_choices` so host agents can interview users before applying entity
  decisions. Relationship edges support v1.2 additive metadata
  (`evidence`, `source`, `created_at`, `status`, optional `start`/`end`) while
  legacy bare `{target, relation}` edges still load as confirmed.
- `entity --unmerge --id MERGED_ID --target-id TARGET_ID` restores an entity
  from the merge tombstone created by `entity --merge`.
- Entity maintenance rhythm is now visible in `health` through an
  `entity_maintenance` traffic light, pending review count, audit age, and
  `life-index entity --review` next step.
- `entity --propose` lets host agents persist entity/relationship hypotheses as
  `status=candidate` review items without affecting confirmed search expansion.
- `entity --apply-batch <file>` previews and applies user-confirmed JSON/YAML
  batches with idempotent clean writes, conflict queuing, and atomic failure on
  invalid rows.

### Fixed

- `sync-skill --install` now auto-converges a managed
  `skills/life-index/life-index` duplicate into the canonical
  `skills/life-index` slot when that nested duplicate is the only discovery
  ambiguity. Unrelated or unsafe duplicate candidates still fail closed with
  `HOST_SKILL_DIR_AMBIGUOUS`.
- `entity --merge` is now reversible: merges preserve the absorbed entity's
  original record, transferred aliases, transferred relationships, and rewired
  reverse references for later `--unmerge`.
- Entity audit now treats zero journal references as a neutral fact. User-owned
  `source=user,status=confirmed,evidence=[]` facts are healthy and are not
  framed as archive/delete recommendations.
- `entity --review --action keep_separate` now persists user-confirmed
  non-duplicate decisions and audit respects them; `undo_keep_separate` removes
  that mark so the pair can be reviewed again.

## [1.3.6] - 2026-07-03

### What users get

- More trustworthy journal linking: confirming a related-entry association now
  binds to the entry you saw at write time, even if the candidate list changes
  before you confirm — no more silent mis-association.
- Clearer upgrades: `health --json` surfaces an `upgrade_freshness` signal your
  host agent can read each session, and `sync-skill --install` repairs nested
  skill duplicates.
- A migration section documenting the removal of legacy semantic/vector search.

### Migration

- Semantic/vector compatibility switches are now documentation-only migration
  surfaces. `search --semantic`, `search --no-semantic`,
  `search --semantic-policy`, `search --semantic-weight`, `index --vec-only`,
  `index --with-semantic`, `eval --semantic`, and `eval --semantic-report`
  are accepted for old scripts but do not build, read, or rank with a vector
  index. `health` reports `semantic_status: "disabled"`.
- Scripts, skills, or dashboards that depended on in-tool semantic/vector
  behavior should migrate to deterministic `smart-search --include-evidence`
  plus host-agent query rewriting, multi-pass retrieval, and synthesis.

### Included in this release

- fix(confirm): resolve related ids from a write-time snapshot (#109).
- fix(upgrade): expose freshness and repair skill install (#107); host-env test
  isolation + semantic/vector purge migration doc (#110).
- chore(search): purge the legacy hybrid ranking dead-code tail (#105).

## [1.3.5] - 2026-07-02

### Removed

- Purged the retired semantic/vector runtime implementation and old
  vector-specific tests after the 108-query golden set showed no four-decimal
  gain from in-tool semantic retrieval. Deprecated `--semantic*` and vector
  flags remain accepted as no-op compatibility inputs.
- Removed `numpy` from the core install path now that the legacy vector runtime
  is gone.

### Fixed

- Corrected the top-level `smart-search` help text so it describes deterministic
  host-agent evidence scaffolding instead of claiming in-tool LLM orchestration.
- Stopped writing new `semantic_baseline_p25` index metadata; existing old
  databases are left untouched because no active read path consumes it.
- Relaxed entity-graph benchmark hard assertions to shared-runner-safe
  fail-safes while keeping printed measurements for trend review.

### Documentation

- Added the MCP architecture boundary: a future MCP layer is constitutional only
  as a 1:1 CLI JSON projection with zero new capability and zero new write path.
- Split the full grounded query playbook into `references/` so ordinary host
  agents keep a smaller always-loaded `SKILL.md` and load the detailed query
  playbook only when needed.
- Updated README metrics to the 108-query `Recall@5 = 0.9231` baseline and
  current pytest-collected scale.

## [1.3.4] - 2026-06-21

### Improved

- Clearer tool surface for agents: `recall` 降为 `search` 的弃用兼容壳(改用 `search`/`smart-search`);`aggregate`(计数/分桶/claim envelope)与 `trajectory`(typed observation series)边界明确;`index-tree nodes/lens/shadow` 降为 debug-only legacy,宿主导航主路径为 `ensure → discover → navigate`。受影响命令均保留,仅指引/呈现变化。
- Single data-doctor surface: `maintenance audit` 成为数据完整性问题检测的唯一来源,`health --data-audit` 改为指向它的摘要;`verify` 保留为只读完整性检查。data doctor 现可检出并安全归档散落的 `entity_graph.yaml.backup*` 副本(移入 `.trash`,canonical 图谱不动)。

## [1.3.3] - 2026-06-21

### Improved

- **Install / upgrade update awareness**: `bootstrap` now checks the release
  channel, reports whether a newer version is available, and suggests the
  matching refresh step for editable and PyPI installs. Offline environments
  degrade cleanly with `freshness: "unknown"` and can disable the check with
  `LIFE_INDEX_NO_NET=1`.
- **Simplified onboarding**: the installation / upgrade guide is now a
  one-page bootstrap-driven script. `bootstrap --json` emits a structured
  `execution_policy`, so host agents execute a deterministic plan instead of
  reconstructing decisions from prose.

## [1.3.2] - 2026-06-21

### Fixed

- **Reliable agent playbook delivery**: upgrades now reliably deliver the
  current `SKILL.md` and references to the host skill library. `sync-skill`
  automatically recognizes nested host layouts such as
  `.hermes/skills/<category>/life-index` and
  `.claude/skills/<category>/life-index`, and reports `delivered: false`
  explicitly when no host directory is found instead of silently skipping
  playbook delivery.

## [1.3.1] - 2026-06-21

### What users get

- **Topic navigation**: index-tree now exposes the `topic` facet, so agents can
  navigate journals by topic (work/learn/health/relation/think/create/life);
  the write-schema `topic` field was previously not navigable.
- **Runnable health guidance**: when the index needs rebuilding, `health` now
  suggests a command that actually runs (`generate-index --all-months`) instead
  of an erroring hint.
- **Entity-aware facet values**: facet values are canonicalized through the
  entity graph, so variants like `Life Index` / `Life-Index` / `life-index`
  collapse into one navigable bucket (case-insensitive lookup; canonical
  display preserves your naming).
- **Upgrade delivers the agent playbook**: upgrading now rebuilds the
  search/navigation indexes and syncs the current `SKILL.md` + references to
  the host agent (`sync-skill`), so tools and their usage playbook stay in sync.
- **Data-doctor archive**: `maintenance` can detect and safely archive stray
  timestamped journal copies (moved to `.trash`, never deleting the canonical
  entry).
- **Correct agent playbook**: `SKILL.md` no longer references a removed command;
  it points to `life-index abstract` / `generate-index`.

### Maintenance / internal

- Evaluation data is now local-only; the public test suite skips quality-gate
  checks when the private evaluation corpus is absent.
- Repository hygiene: development-process surfaces removed from the public tree;
  a public-surface allowlist check and a retired-flag check now guard the public
  surface.

## [1.3.0] - 2026-06-20

### What users get

- **Agent-native grounded query generation**: grounded answers now run through
  host-agent ACP sessions with deterministic evidence validation and advisory
  labels, so answers can be shown with `GROUNDED`, `PARTIAL`, `UNGROUNDED`, or
  `UNVERIFIABLE` status instead of being hidden behind a blocking gate.
- **Index B navigation and freshness**: materialized index-tree documents now
  expose deterministic facet navigation, freshness checks, stale-subtree
  regeneration, and safe fallback when navigation artifacts are missing or
  stale.
- **Deterministic narrowing tools**: agents can discover facet values, combine
  selected values into bounded intersections, batch-read journal candidates, and
  traverse entity-neighbor relationships without moving reasoning into tools.
- **Tool boundary hardening**: core CLI tools no longer expose embedded LLM modes;
  `smart-search` and related helpers remain deterministic scaffolds for host
  agents, guarded by a CI no-LLM check.

### Included in this release

- Index-tree materialization, navigation, freshness manifest, stale detection,
  incremental regeneration, and deletion fallback coverage.
- Deterministic facet discovery, multi-signal navigation, bounded batch journal
  reads, and entity-neighbor navigation with qrels/eval coverage.
- Retirement of core tool LLM flags and helpers, with `_optional` and eval-only
  LLM code kept isolated from default tool paths.
- Public docs for the upgraded install/sync flow so existing installations can
  detect the newer manifest and reinstall the refreshed package.

## [1.2.5] - 2026-06-08

### What users get

- **Non-blocking onboarding**: `life-index health` and bootstrap flow now complete
  without waiting for semantic index builds. FTS5 keyword search is available
  immediately after install; semantic vector indexing runs in background and
  degrades gracefully when unavailable. This fixes onboarding timeouts on fresh
  installs and machines without sentence-transformer models.
- **Lightweight base install**: `pip install life-index` no longer pulls the
  heavy ML stack (torch + CUDA, ~1.3 GB / ~16 min). Semantic search is now an
  opt-in extra: `pip install 'life-index[semantic]'`. When not installed,
  `life-index health` degrades gracefully with a warning and install hint.
- **Explicit httpx dependency**: Declared `httpx` as a core dependency
  (previously an undeclared transitive of the ML stack exposed by the
  `[semantic]` split).
- **Bootstrap manifest in wheel**: `bootstrap-manifest.json` is now included in
  the built wheel package, so `life-index bootstrap --json` works correctly from
  a `pip install` without a source checkout.
### Included in this release

- P0 non-blocking onboarding: FTS-first index with async semantic fallback.
- CI tiered gate hardening: PR-level blocker/contract/eval gates plus post-merge
  full-suite and package smoke.
- CJK word-count fix for `word_count` metadata (previously undercounted CJK
  characters).
- Write-journal flow refactoring and enforced coverage gate.
- Vector index storage split and SimpleVectorIndex search vectorization.

## [1.2.4] - 2026-06-04

### What users get

- `bootstrap --json` adds a read-only onboarding state detector for agents and
  maintainers. It reports existing data, installed and manifest versions,
  route decisions, human-needed blockers, and safe next steps without mutating
  user data.
- Agent onboarding and README prompts now route fresh agents through the
  bootstrap gate and clarify existing-data protection during install, upgrade,
  and clean-context onboarding tests.
- Search result metadata now includes `word_count` from the L2 metadata cache,
  giving GUI and agent consumers a stable word-count field without re-reading
  journal files.

### Included in this release

- Public schema `m34.bootstrap.v0` and API documentation for
  `life-index bootstrap --json`.
- Bootstrap unit and contract coverage for data detection, checkout assessment,
  route decisions, temp data-dir read-only behavior, and CLI exposure.
- Onboarding safety guidance aligned with `bootstrap-manifest.json` and the
  project data/code separation rules.

## [1.2.3] - 2026-06-01

### What users get

- `maintenance` adds the Data Doctor command family for deterministic user-data
  maintenance: `audit`, `plan`, `repair`, and `proposal validate`.
- `maintenance audit --json` emits complete `m33.maintenance_audit.v0` issue
  inventories with per-domain counts, detector status, non-truncation metadata,
  stable issue IDs, relative evidence paths, and redacted secret/path output.
- `maintenance repair --apply` is limited to rebuildable derived artifacts
  such as generated Markdown indexes, `.index/`, `.cache/`, and
  `.life-index/cache/`; journals, attachments, entity graph, import sources,
  config secrets, migrations, and human-curated Markdown are not auto-mutated.
- `maintenance proposal validate --file ... --json` gives GUI/L3/user flows a
  deterministic validator for metadata/entity/relation repair proposals without
  calling an LLM or applying changes.

### Included in this release

- Public schema family `m33.maintenance_audit.v0`,
  `m33.maintenance_plan.v0`, `m33.maintenance_repair.v0`, and
  `m33.maintenance_proposal.v0`.
- Legacy `m16.maintenance.v0` and `m16.health.v0` compatibility preserved.

## [1.2.2] - 2026-05-31

### What users get

- `index-tree` adds read-only Index Tree Evidence Navigation JSON envelopes for
  node summaries, derived frontmatter lenses, and Search Shadow Mode diagnostics.
  The new surface is local-first, journal-derived, and designed for GUI,
  `on-this-day`, `smart-search` diagnostics, and approved advanced modules.
- `index-tree shadow` is diagnostic-only: it reports candidate paths,
  recall-preservation status, freshness blockers, and dropped-path evidence
  without changing default `search` or `smart-search` ranking/output semantics.

### Included in this release

- Public schema family `m31.index_tree.v1` with `nodes`, `lens`, and `shadow`
  subcommands.
- GUI/consumer constraints: no private artifact consumption, no durable writes
  outside CLI owner commands, and all derived lenses remain
  rebuildable navigation aids rather than truth claims.

## [1.2.1] - 2026-05-26

### What users get

- README, README.en, and API docs now show the exact Recall@5 measurement
  `0.7857` (keyword-only honest floor) instead of the rounded `0.79`, with
  explicit notation that this is a marginal miss versus the 0.79 target and
  that C2 paraphrase remains a known gap.
- Search tool docstrings and CLI help text corrected to reflect the actual
  default behavior: keyword-only retrieval with `--semantic` as explicit
  opt-in for dual-pipeline parallel search.
- `edit_journal` append-only revision history has passing contract tests
  enforcing that `save_revision()` is called before every write, backing the
  P1 Growth Rings promise.
- MCP discovery-only layer accepted as a read-only capability discovery surface.

## [1.2.0] - 2026-05-24

### What users get

- Search System Upgrade: v1.2.0 now combines the recall-first deterministic
  retrieval foundation with an agent-ready `smart-search` v1 contract.
- Search defaults now preserve recall-first truthfulness: L2 search remains
  keyword-only by default, semantic/vector retrieval stays explicit opt-in, and
  ranking changes are evaluated against a frozen Cycle 2 multi-signal fixture.
- `smart-search` default output is now a provider-free scaffold for agents:
  `agent_instructions`, `answer_scaffold`, and `query_plan` tell the calling
  agent how to synthesize, cite, and diagnose the returned evidence without
  hidden LLM calls.
- `smart-search --use-llm` now consumes LLM query decomposition as a bounded
  outer loop: up to three sub-queries are run through keyword-first search,
  fused, deduplicated, and marked with `source_queries` provenance before
  optional filtering/synthesis.
- `smart-search --use-llm` now also consumes rewrite metadata: `expanded_terms`
  can fill bounded sub-queries, `time_range` can become deterministic
  `date_from` / `date_to` filters for exact ISO-like ranges, and `intent_type`
  is reflected in the truthful `query_plan.strategy`.
- Pure temporal Chinese queries such as date-only or month-only requests now
  return journal entries from the requested date range instead of falling
  through to empty-keyword BM25 and returning zero results.
- Search result truncation is separated from retrieval, so internal candidate
  pools remain available for evaluation and review while the user-facing
  presentation layer still controls display limits.

### Included in this release

- B-A reset default search semantics to the CHARTER §1.11 recall-first model.
- B-B decoupled presentation truncation from retrieval/evaluation surfaces.
- B-C added the date-only branch for fully temporal queries and covered it with
  unit tests.
- smart-search v1 added the default agent scaffold contract plus explicit
  `--use-llm` bounded multi-query orchestration. Default mode remains
  deterministic and does not initialize a provider client.
- smart-search rewrite metadata consumption now covers `expanded_terms`,
  `intent_type`, and deterministic `time_range` filters within the v1 contract.
- Cycle 2 final eval on `tests/fixtures/eval/gold/cycle2-multi-signal/`:
  overall R@5 `0.7857`, MRR@5 `0.7417`; C1 `1.0`, C2 `0.1429`,
  C3 `1.0`, C4 `1.0`. Overall R@5 is a marginal miss versus the
  `0.79` target; release owner accepted it because C1/C3/C4 gates passed,
  C2 matched the baseline floor, and the recall-first precision trade-off is
  intentional under CHARTER §1.11.
- C3 temporal R@5 reached `1.0000`, exceeding the `0.95` target.
- Gold Set Recall@5 improved `0.7957` to `0.8172`; Precision@5 moved from
  `0.4628` to `0.4468`, a disclosed boundary trade-off of the recall-first
  retrieval model.
- The local pre-push gate contract timeout is calibrated to 1800 seconds after
  measured contract-suite runtime showed distributed slowness rather than a
  single outlier test.
- GitHub Actions Tests / Quality / Benchmark were green on pushed main
  `0408590`.

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
