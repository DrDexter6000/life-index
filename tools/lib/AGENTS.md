# AGENTS.md - tools/lib/

> **最后更新**: 2026-07-02 | **版本**: v1.7 | **状态**: 活跃维护

## OVERVIEW
Shared infrastructure library for all Life Index atomic tools.

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add new error code | `errors.py` | Follow E{module}{type} format, add recovery strategy |
| Modify attachment handling | `attachment.py` | Normalize write-input and stored-metadata attachment entries |
| Modify frontmatter format | `frontmatter.py` | SSOT: update FIELD_ORDER and type mappings (re-exports attachment + schema). `parse_frontmatter()` always returns a mapping; `normalize_indexable_metadata()` is the one "what is indexable metadata" rule for the derived stores |
| Change data directory paths | `config.py` | Update USER_DATA_DIR, all other paths derive from it |
| Decide what kind of file lives under Journals/ | `journal_files.py` | Closed kind rule (fragment / digest / derived_index / unknown) + enumeration helpers + `is_live_fragment_path()` admission predicate; all journals-tree walkers and single-path derived-store writes must use it |
| Debug concurrent write issues | `file_lock.py` | Cross-platform advisory locks for serialization |
| Debug L2 search performance | `metadata_cache.py` | Check SQLite WAL mode, mtime/size detection |
| Fix FTS5 search issues | `search_index.py` | Supports auto-rebuild on corruption |
| Debug FTS search queries | `fts_search.py` | BM25 ranking, snippet extraction, JSON field parsing |
| Debug FTS index updates | `fts_update.py` | Incremental/full rebuild under the shared `.index/index.lock`, read-once single-row write-through insert, (mtime, size) signature scan + `inspect_fts_index()` preflight, raw-text rows for unparsable fragments, journal parsing |
| Debug FTS freshness decisions | `index_freshness.py`, `fs_consistency.py`, `event_detectors.py` | All consult the per-fragment signature check; no timestamp/count freshness rules remain |
| Search retrieval behavior | `search_index.py`, `fts_search.py`, `metadata_cache.py`, `entity_runtime.py` | Active retrieval is keyword + Entity Graph |
| Debug path normalization | `path_contract.py` | Canonical path normalization and route-safe path shaping |
| Modify schema validation | `schema.py` | SCHEMA_VERSION, validate/migrate metadata, required/recommended fields |
| Debug URL download pipeline | `url_download.py` | Shared remote-file download helper used by write/web flows |
| Modify topic taxonomy | `topics.py` | Deterministic `VALID_TOPICS` SSOT (no LLM dependency) |
| Tune search parameters | `search_constants.py` | Reviewed constants for deprecated semantic flag defaults, FTS, confidence, typo correction, and structured metadata |

## MODULES

- **attachment.py**: Attachment normalization for write-input and stored-metadata modes. Extracted from frontmatter.py.
- **config.py**: Centralized configuration, paths, templates. All paths use `pathlib.Path` for cross-platform compatibility.
- **entity_cache.py**: SQLite-backed lookup cache helper for entity graph. Round 7 Phase 1 提供 `is_cache_fresh()` + `resolve_entity_cached()`；当前 search/write 主热路径主要使用 `entity_runtime.py`。
- **entity_candidates.py**: Write-time entity candidate extraction (Round 7 Phase 2). Covers frontmatter + content body alias matching via runtime view.
- **entity_graph.py**: YAML entity graph load/save/resolve. Foundational module for entity operations. `load_entity_graph()` memoizes the validated parse per resolved path and file `(mtime_ns, size)` and returns a deep copy, so repeated loads in one process skip YAML parsing while in-place caller edits cannot corrupt the memo; `save_entity_graph()` updates the memo.
- **entity_relations.py**: Relation vocabulary normalization (Round 7 Phase 3). Canonical mapping + alias helper for search/review/check.
- **entity_runtime.py**: Runtime serving layer for entity graph (Round 7 Phase 1). Provides `EntityRuntimeView` with O(1) by_lookup, reverse_relationships, and phrase pattern registry.
- **entity_schema.py**: Entity graph schema validation. ENTITY_TYPES (new actor/artifact plus legacy person), alias conflict detection, relationship target verification, v1.2 relationship metadata defaults, and merge tombstone validation.
- **errors.py**: Structured error codes (E{module}{type}) with recovery strategies for Agent decision-making.
- **file_lock.py**: Cross-platform file locking for concurrent access control. Uses fcntl (Unix) and msvcrt (Windows).
- **journal_files.py**: Canonical journal file enumeration and closed kind classification under Journals/ (fragment / digest / derived_index / unknown). Path-only rules; dot-directories such as .revisions/ are never enumerated. All journals-tree walkers use these helpers. `is_live_fragment_path(path, journals_dir)` is the single admission predicate for writing one path into a derived per-fragment store (FTS row, metadata-cache row): inside the tree, no dot-directory component, filename classifies as fragment. `scan_journal_files()` walks fragments once and returns `(path, mtime, size)` from `DirEntry.stat()` for stat-only consumers (event detectors, metadata-cache reconcile, FTS signature preflight); its mtime equals `Path.stat().st_mtime`.
- **frontmatter.py**: SSOT for YAML frontmatter parsing/formatting. Re-exports attachment.py and schema.py for backward compat. `parse_frontmatter()` always returns a mapping: a YAML root that is a list or a scalar, an invalid document, and an impossible timestamp all read as "no frontmatter" (`({}, body)`) instead of raising. `normalize_indexable_metadata()` is the one rule for "what is indexable metadata": it returns typed `title`/`date`/`location`/`weather`/`project`/`abstract` (text) and `topic`/`tags`/`mood`/`people`/`links`/`related_entries` (`list[str]`), or `None` when the frontmatter is not parsable. Every derived per-fragment store (FTS row, metadata cache) must go through it; never re-implement it.
- **fs_consistency.py**: `index_is_current()` — the L3 fallback's freshness gate, delegating to the same per-fragment signature check as the search preflight. The old mtime-vs-`last_updated` helpers are gone.
- **fts_search.py**: FTS5 full-text search with BM25 ranking. Extracted from search_index.py.
- **fts_update.py**: FTS5 index building/updating. `inspect_fts_index()` is the read-only signature check (one directory scan + journals/stats reads, never opens a journal) used by the search preflight, event detectors and L3 fallback. Every `update_index` caller holds the shared `<data>/.index/index.lock` (the wrapper takes it by default; `build_all` passes `lock_held=True`); under the lock an orphaned `.rebuilding` marker is removed and the rebuild continues. The incremental scan decides "unchanged" only when an FTS row exists *and* the (mtime, size) signature in `fts_file_stats` matches; pending paths are force-read; vanished files lose row+signature. Every readable live fragment gets a row: unparsable frontmatter is indexed as raw text (empty metadata, filename date) and counted as `unparsable` when it is (re)read. The row's metadata comes from `frontmatter.normalize_indexable_metadata()` (the shared rule; a list field is joined with ", "). Files are read once (bytes); a signature is recorded only when `(st_mtime_ns, st_size, st_ino)` is unchanged across that read. A file whose read raises `OSError` is counted and named in the additive `unreadable` / `unreadable_paths` result keys (incremental and full mode; `total` still counts it). `insert_fts_doc` is the one "file → FTS row" insert shared by rebuild and write-through. Extracted from search_index.py.
- **index_freshness.py**: `check_full_freshness()` — signature-based freshness report for search preflight / `index --check`. Manifest presence/partial and version keys remain build signals; manifest row counts are no longer a freshness rule.
- **metadata_cache.py**: SQLite-based L2 search cache. 50-100x performance improvement over file scanning. `parse_and_cache_journal()` stores the values from `frontmatter.normalize_indexable_metadata()` (listed fields are JSON arrays), so a row never carries a type SQLite cannot bind. A fragment whose frontmatter is not parsable gets the same empty row a file without frontmatter gets — one file's content can never raise from the cache. `CACHE_VERSION_SCHEMA_VERSION` is v2.1.0 (list columns are JSON arrays for scalar/null inputs too; existing installations rebuild once on the version bump).
- **path_contract.py**: Shared path normalization helpers for route-safe, user-safe journal paths.
- **pending_writes.py**: Generation-scoped pending repair queue. `mark_pending` bumps the path's generation; `ack_pending(snapshot, only=repaired)` has no permissive mode and removes a path only when its generation is unchanged and it is in the actual repaired list. The legacy `{"pending": [...]}` list format is still read (generation 0), and an unusable generation/counter value also reads as generation 0 instead of raising. Mutations serialize on a leaf queue lock.
- **schema.py**: Schema version management, metadata validation and migration. Extracted from frontmatter.py.
- **search_index.py**: FTS5 index management (init, stats) + backward-compat wrappers for fts_search.py and fts_update.py. `upsert_fts_row` holds the shared `.index/index.lock` and returns the raw-text row (`unparsable: True`) for a live fragment whose frontmatter does not parse.
- **timing.py**: Performance timing utility for metrics collection. Used in tool outputs for monitoring.
- **topics.py**: Deterministic topic taxonomy SSOT (`VALID_TOPICS`). Importable without LLM dependency.
- **url_download.py**: Shared URL download helper for attachment ingestion and related flows.

## CONVENTIONS

**SSOT Pattern**: `frontmatter.py` is the single source of truth for YAML frontmatter. Any format change must happen here first, then propagate to tools.

**Error Recovery**: All errors include a `recovery_strategy` field (`skip_optional`, `ask_user`, `continue`, `continue_empty`, `fail`, `retry`). `continue` preserves a degraded primary result while the caller follows the error-specific remediation; it is distinct from `continue_empty`, which returns an empty result. After a durable journal commit, `continue` must never instruct retrying the journal write.

**File Locking**: All write operations (journal, edit, index) use `FileLock` to prevent concurrent conflicts. Lock timeout defaults to 30s for journals, 60s for index operations.

**Semantic / vector search**: Removed from active L2 atomic tools. `--semantic*` flags are accepted by callers as deprecated no-ops, and active retrieval is keyword + Entity Graph. Do not add model loading, vector build, or semantic fallback to `tools/lib` without a new charter-level decision.

## ANTI-PATTERNS

- **Never** duplicate frontmatter parsing logic in tools. Always import from `lib.frontmatter`.
- **Never** hardcode paths. Use `config.USER_DATA_DIR` and derived constants.
- **Never** duplicate `USER_DATA_DIR` resolution outside `tools/lib/config.py` (e.g., in `web/runtime.py`). Web/runtime code must import `config.USER_DATA_DIR` / `config.JOURNALS_DIR` directly, not recompute via `Path.home()`.
- **Never** raise bare exceptions. Use `LifeIndexError` with structured codes.
- **Never** reintroduce vector index operations into active search/index/write paths without updating CHARTER, API, docs, and gates in the same change.
- **Never** write journals/indexes without acquiring the appropriate lock first.

## MODULE REGISTRY

> 本表记录每个 lib 模块的集成状态。任何新增模块必须登记；任何激活/弃用变更必须更新。

| 模块 | 消费者 | 集成状态 | 备注 |
|------|--------|---------|------|
| attachment.py | write_journal, frontmatter | ✅ 活跃 | |
| config.py | ALL tools | ✅ 活跃 | 路径 SSOT |
| content_analysis.py | write_journal | ✅ 活跃 | |
| chinese_tokenizer.py | search_journals (fts_search, fts_update, keyword_pipeline) | ✅ 活跃 | Round 8 Phase 1 新增：jieba 中文分词模块（index/query 双模式） |
| entity_cache.py | entity_runtime 相关 helper / tests | ✅ 活跃 | Round 7 Phase 1 已落地 cache-first helper，但不是当前 search/write 主热路径 |
| entity_candidates.py | write_journal | ✅ 活跃 | Round 7 Phase 2 新增：write-time candidate extraction |
| entity_graph.py | write_journal, entity tool, entity_runtime | ✅ 活跃 | Round 7 Phase 1 runtime view 底层 |
| entity_relations.py | entity_runtime, check, review | ✅ 活跃 | Round 7 Phase 3 新增：relation vocabulary normalization |
| index_manifest.py | build_index | ✅ 活跃 | Round 12 Phase 2 新增：索引构建状态 manifest（counts + checksums + partial flag） |
| index_freshness.py | search_journals, build_index (--check) | ✅ 活跃 | 逐 fragment 签名新鲜度；manifest 行数不再参与判定 |
| entity_runtime.py | search_journals | ✅ 活跃 | Round 7 Phase 1 新增：runtime serving layer（by_lookup + reverse_relationships + phrase patterns） |
| entity_schema.py | write_journal, entity_graph | ✅ 活跃 | Round 7 Phase 1 确认活跃；v1.2 负责 relationship metadata defaults 与 merge tombstone validation |
| errors.py | write_journal(core), query_weather, generate_index | ⚠️ 部分集成 | Round 5 Task 3 将全面激活 |
| file_lock.py | write_journal, edit_journal, build_index | ✅ 活跃 | |
| frontmatter.py | write_journal, edit_journal, search, fts_update, metadata_cache | ✅ 活跃 | SSOT；`normalize_indexable_metadata()` 是派生存储的“可索引字段”唯一规则 |
| fts_search.py | search_journals | ✅ 活跃 | |
| fs_consistency.py | search_journals (L3 fallback) | ✅ 活跃 | `index_is_current()` 签名检查；旧 mtime/last_updated 规则已删除 |
| fts_update.py | build_index, search_journals (preflight), event_detectors, search_index (write/edit write-through) | ✅ 活跃 | 只读签名检查 + 单次读取 + 唯一 file→row 插入路径；共享 index lock；pending 强制重读、不可解析文本按原始行索引；不可读文件计入 `unreadable`/`unreadable_paths` |
| llm_extract.py | 无 | 🗄️ 已退役 | backward-compat shim 已删除；隔离实现仅保留在 `tools/_optional/llm_extract.py`，不在核心工具默认路径导入 |
| journal_files.py | search_journals, entity, maintenance, backup, __main__, event_detectors, fts_update, metadata_cache | ✅ 活跃 | Journals/ 文件种类 SSOT + `is_live_fragment_path()` 准入谓词；枚举默认只返回 fragment |
| logger.py | ALL tools | ✅ 活跃 | |
| metadata_cache.py | search_journals, write_journal | ✅ 活跃 | |
| path_contract.py | write_journal, edit_journal | ✅ 活跃 | |
| paths.py | 多个 | ✅ 活跃 | |
| pending_writes.py | write_journal, edit_journal, search_journals, build_index | ✅ 活跃 | 写穿失败时的修复队列；generation 快照确认（`ack_pending`），同一 path 构建期间重新入队不丢事件；兼容旧列表格式 |
| related_candidates.py | write_journal | ✅ 活跃 | |
| revisions.py | edit_journal | ✅ 活跃 | |
| schema_validator.py | dev tools | ✅ 活跃 | |
| schema.py | frontmatter | ✅ 活跃 | |
| search_config.py | search_journals | ✅ 活跃 | |
| search_constants.py | search_journals | ✅ 活跃 | 包含 deprecated semantic flag defaults、FTS、confidence、fuzzy typo、structured metadata 常量 |
| search_diagnose.py | search_journals | ✅ 活跃 | Round 8 新增：按月 JSONL 指标聚合最近搜索诊断摘要 |
| search_index.py | build_index, search_journals, write_journal, edit_journal | ✅ 活跃 | `upsert_fts_row` 为 write/edit 提交后单行 FTS 写穿（单次读取、稳定才记签名、不碰 `last_updated`） |
| search_metrics.py | search_journals | ✅ 活跃 | Round 8 新增：按月 JSONL 追加搜索指标日志 |
| text_normalize.py | search, fts | ✅ 活跃 | |
| timing.py | write_journal | ✅ 活跃 | write_journal 使用 Timer 做性能计时；其他工具使用 trace.py |
| topics.py | write_journal | ✅ 活跃 | Charter 19 Phase 1 新增：deterministic VALID_TOPICS SSOT |
| trace.py | search_journals, build_index, write_journal | ✅ 活跃 | Round 7 观测层：step-based context manager |
| url_download.py | write_journal | ✅ 活跃 | |
| workflow_signals.py | write_journal, errors | ✅ 活跃 | Round 5 Task 1 新增 |
| yaml_utils.py | frontmatter | ✅ 活跃 | |

## DEPENDENCIES

**This lib depends on**: Python 3.11+, pyyaml, httpx, jieba, rapidfuzz, Pillow

**Tools depend on this lib**: write_journal, search_journals, edit_journal, generate_index, build_index, query_weather, backup, Web GUI service layer helpers
