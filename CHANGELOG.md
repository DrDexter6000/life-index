# Life Index Changelog

This changelog records user-visible releases for the Life Index CLI line.

Versioning follows [`docs/VERSIONING.md`](docs/VERSIONING.md). Earlier exploratory tags are treated as pre-contract history and no longer define formal release semantics.

## [Unreleased]

## [1.5.2] - 2026-07-19

### Changed

- `life-index upgrade --plan/--apply --json` is now read-only: update or
  program inconsistency reports `UPGRADE_REINSTALL_REQUIRED` and points to a
  fresh dedicated install, while healthy/current apply is a truthful no-op.
- Upgrade guidance preserves user data and leaves shared/global environments
  and developer/user-owned checkouts untouched instead of attempting in-place
  git, pip, or skill repair.

### Fixed

- Search keeps embedded or suffixed date-like identifiers as keywords instead
  of misreading them as date filters, while standalone calendar dates continue
  to produce deterministic date ranges.
- `life-index confirm` now reaches the confirmation handler and rejects invalid
  or out-of-tree journal paths with a non-zero, zero-write failure.
- `life-index verify` excludes `.revisions/` history from the canonical journal
  inventory while preserving real missing and orphaned index detection.

## [1.5.1] - 2026-07-17

### What users get

- Safer writes and recovery: a write either rolls back safely before commit or
  preserves the journal and reports follow-up failures honestly after commit.
  Recovery refuses unsafe or incomplete restores, and rolled-back imports do
  not remain searchable.
- The separate GUI's first-use write, search, and detail flows continue through
  the CLI data authority, rather than creating a second data path.
- Optional host-agent integration stays narrow: approved host agents can use
  exactly `health`, `journal.get`, and `search`. Search may refresh only
  rebuildable indexes; it cannot edit journals, attachments, or entities.
- Clearer licensing and maturity: clarifies why Life Index is AGPL-3.0-only.
  The CLI remains Production/Stable; GUI maturity is separate and pre-1.0.

### Included in this release

- Safe write, restore, and rolled-back-import cleanup.
- GUI/Core first-use interoperability and the optional three-tool MCP bridge.
- AGPL and CLI/GUI maturity clarification.

## [1.4.5] - 2026-07-08

### Fixed

- Added and hardened `life-index upgrade --plan/--apply --json` as a
  deterministic host-agent upgrade atom.
- Completed editable/source upgrade loops: safe git fast-forward,
  `python -m pip install -e <repo>`, version consistency check,
  `sync-skill` delivery, and health verification.
- Kept current states quiet: when code, package metadata, health, and skill
  delivery are current, `recommended_next_step.id` is `none`.
- Preserved fail-closed behavior for dirty/ahead/diverged checkouts, unknown
  installs, and unreachable git remotes.

### Notes

- `upgrade` is for host-agent CLI upgrades only. It does not replace the
  developer release workflow and does not operate the GUI repository.

## [1.4.4] - 2026-07-08

### What users get

- Entity review queue actions now expose stable GUI/host-agent payloads and
  structured `action_choices[]` data for review cards.
- `entity --review --action preview` can preview a specific review action with
  explicit `--review-action` and `--source-id`.
- Review queue items now carry stable `source_id` and `target_id` fields so
  GUI review consent cards do not need private guessing rules.

### Included in this release

- feat(entity): stabilize review action contract (#155).

## [1.4.3] - 2026-07-08

### What users get

- Fix `sync-skill --install` canonical host skill slot.
- Recover safely from the `1.4.2` parent-slot bad state.
- `1.4.3` supersedes `1.4.2` for skill delivery.

### Included in this release

- fix(sync-skill): enforce canonical host skill slot (#153).

## [1.4.2] - 2026-07-07

### What users get

- Fix PyPI wheel `sync-skill --install` delivery by packaging `SKILL.md` and
  `references/` into wheel-accessible package data.
- `1.4.2` supersedes `1.4.1` for PyPI clean installs.

### Included in this release

- fix(sync-skill): package skill artifacts in wheels (#151).

## [1.4.1] - 2026-07-07

### What users get

- JSON stdout is clean for Entity profile materialization:
  `life-index abstract --entities --json` can be parsed directly with
  `json.loads(stdout)`.
- User-confirmed relationship facts now have a preview-first primitive:
  `life-index entity maintain --add-relationship --preview/--apply --json`.
- `health --help` is real help; health suggested commands include side-effect
  metadata; green Entity maintenance no longer suggests unnecessary review.
- `v1.4.0` was tagged on GitHub but intentionally skipped on PyPI. `v1.4.1`
  is the first PyPI release carrying the 1.4 Entity Graph payoff surface.

### Included in this release

- fix(abstract): keep `abstract --entities --json` stdout pure JSON (#147).
- feat(entity): add `maintain --add-relationship` preview/apply primitive
  (#148).
- fix(health): harden pre-release help and side-effect metadata (#149).

## [1.4.0] - 2026-07-07

### What users get

- Entity Graph now pays visible rent in retrieval: search JSON explains entity
  expansion attribution, relationship-aware queries can expand from confirmed
  graph edges, and standard "my + relationship" queries resolve from an
  explicit self anchor.
- Entity profiles are first-class deterministic views. Agents can ask for
  `entity profile`, then read materialized `Entities/<entity_id>.md` profile
  documents and follow recent mention pointers before falling back to search.
- Entity outputs have a deterministic name floor: stats, audit/review,
  candidates, search hints, and evidence-pack entity matches carry
  `primary_name` beside opaque entity IDs so weaker host agents do not
  reconstruct names from IDs.
- Agent-facing maintenance signals are cleaner: read-only entity primitives
  advertise workflow hints, profile freshness appears in `health`, dirty host
  checkouts are warned during upgrade freshness checks, and JSON stdout remains
  directly parseable even when Chinese tokenization dependencies log while
  loading.
- License changed to AGPL-3.0-only from this release. Local use is unaffected;
  hosted derivative services must publish corresponding source.

### Breaking and migration

- BREAKING: Entity Graph uses the cutover L1 type vocabulary
  `actor`, `place`, `project`, `event`, `artifact`, and `concept`, with
  `attributes.kind` for finer distinctions. Legacy graphs containing
  `type: person` fail closed with `ENTITY_SCHEMA_LEGACY`; migrate with
  `life-index entity maintain --normalize --preview --json`, then apply after
  reviewing the plan.
- BREAKING: The project license is AGPL-3.0-only starting with v1.4.0. Existing
  local personal use is unchanged; hosted derivative services need to comply
  with AGPL source-sharing obligations.

### Added

- Entity Graph self anchors via `entity --set-self` / `entity --unset-self`;
  search can deterministically expand standard "my + relationship" queries
  such as "my mother" or "我妈妈" from the confirmed self entity.
- `entity profile` assembles identity, confirmed relationships, mentions,
  evidence, and stats for one entity.
- `life-index abstract --entities` materializes deterministic profile
  documents under `Entities/` and links them from the root Index.

### Changed

- License changed to AGPL-3.0-only from v1.4.0. Local use is unaffected; hosted
  derivative services must publish corresponding source.
- Entity-facing JSON now carries deterministic `primary_name` fields beside
  entity IDs across stats, audit/review, write-time candidates, search hints,
  and evidence-pack entity matches.
- Search JSON now exposes entity expansion attribution so agents can explain
  whether a query expanded through aliases or confirmed relationships.

### Fixed

- JSON-mode search stdout is pure JSON; dependency loading messages are kept
  off stdout so callers can use `json.loads(stdout)` directly.

### Included in this release

- docs: switch project license to AGPL-3.0-only and preserve owner relicense
  terms (#134, #135).
- docs(entity): tighten signal hygiene playbook (#136).
- feat(search): expose entity expansion attribution (#138).
- feat(entity): add profile assembly primitive (#139).
- feat(health): warn on dirty host checkouts (#140).
- feat(search): add relation-aware entity expansion (#141).
- feat(entity): materialize profile docs (#142).
- feat(entity): signal stale profile docs (#143).
- feat(entity): add self anchor and name floor (#144).
- fix(cli): keep JSON stdout pure (#145).

## [1.3.7] - 2026-07-06

### What users get

- Entity Graph is now a human-in-the-loop maintenance surface: review items
  carry `why`, `evidence`, and action choices; relationship edges carry
  provenance; merge decisions are reversible; keep-separate judgments persist;
  and host-agent proposals stay in the candidate lane until a user confirms
  them.
- Entity maintenance is easier to operate through three workflow gates:
  `entity build`, `entity audit`, and `entity maintain`. Cold-start journal
  scanning is preview-only, batch imports are preview/apply and idempotent, and
  destructive deletion now requires the maintain facade plus backup.
- Entity schema has cut over to the stable `type` +
  `attributes.kind` model. Active entities now use
  `actor`, `place`, `project`, `event`, `artifact`, or `concept`; legacy graphs
  fail closed with a clear normalize command instead of being silently guessed.
- Agent-facing signals are cleaner: read-only entity commands emit
  `workflow_hint`, `health` exposes the entity maintenance light, zero journal
  references are marked as neutral facts, and monthly review prompts point at
  the real `life-index abstract --month YYYY-MM` artifact generator.
- Upgrade delivery is smoother because `sync-skill --install` can auto-converge
  the managed nested `skills/life-index/life-index` duplicate into the
  canonical single skill slot while leaving unrelated ambiguities fail-closed.

### Breaking

- BREAKING: Entity Graph schema now accepts only the cutover L1 types
  `actor`, `place`, `project`, `event`, `artifact`, and `concept`. Legacy graphs
  containing `type: person` fail closed with `ENTITY_SCHEMA_LEGACY` and point
  agents to `entity maintain --normalize --preview --json`; normalize migrates
  active entities and merge tombstones before apply.
- BREAKING: Removed the top-level Entity Graph primitives `--seed`, `--update`,
  `--merge`, and `--delete` by owner decision on 2026-07-05. Replacements:
  `entity build --from-journals --preview --json`, `entity --add-alias`,
  `entity --review --action preview/merge_as_alias`, and
  `entity maintain --delete --preview/--apply --backup`. Calls to removed flags
  return `ENTITY_PRIMITIVE_REMOVED` with the replacement command.

### Included in this release

- fix(sync-skill): auto-converge managed nested duplicates (#114).
- feat(entity): add HITL relationship provenance, reversible merge tombstones,
  and the interview playbook (#116).
- feat(entity): add source-authority audit semantics, candidate dual lane,
  `--propose`, batch apply, and entity maintenance rhythm (#118).
- fix(entity): persist and undo keep-separate decisions (#120).
- docs(entity): specify the build/audit/maintain UX surface (#121).
- feat(entity): add audit, normalize, build-batch, and journal-build facades
  (#122, #123, #124, #125).
- fix(entity): harden normalize migration and keep family-role records human
  (#126, #128).
- feat(entity): remove retired primitive surface and cut over schema types
  (#127, #129).
- feat(entity): add workflow hints and signal hygiene for host agents (#130).

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
