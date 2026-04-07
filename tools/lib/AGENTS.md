# AGENTS.md - tools/lib/

> **最后更新**: 2026-03-29 | **版本**: v1.2 | **状态**: 活跃维护

## OVERVIEW
Shared infrastructure library for all Life Index atomic tools.

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add new error code | `errors.py` | Follow E{module}{type} format, add recovery strategy |
| Modify attachment handling | `attachment.py` | Normalize write-input and stored-metadata attachment entries |
| Modify frontmatter format | `frontmatter.py` | SSOT: update FIELD_ORDER and type mappings (re-exports attachment + schema) |
| Change data directory paths | `config.py` | Update USER_DATA_DIR, all other paths derive from it |
| Debug concurrent write issues | `file_lock.py` | Cross-platform advisory locks for serialization |
| Debug L2 search performance | `metadata_cache.py` | Check SQLite WAL mode, mtime/size detection |
| Fix FTS5 search issues | `search_index.py` | Supports auto-rebuild on corruption |
| Debug FTS search queries | `fts_search.py` | BM25 ranking, snippet extraction, JSON field parsing |
| Debug FTS index updates | `fts_update.py` | Incremental/full rebuild, file hashing, journal parsing |
| Add semantic search feature | `semantic_search.py` | Uses shared sentence-transformers backend for multilingual embeddings |
| Debug path normalization | `path_contract.py` | Canonical path normalization and route-safe path shaping |
| Modify schema validation | `schema.py` | SCHEMA_VERSION, validate/migrate metadata, required/recommended fields |
| Debug URL download pipeline | `url_download.py` | Shared remote-file download helper used by write/web flows |
| Vector index corruption | `vector_index_simple.py` | Pickle-based fallback when sqlite-vec unavailable |

## MODULES

- **attachment.py**: Attachment normalization for write-input and stored-metadata modes. Extracted from frontmatter.py.
- **config.py**: Centralized configuration, paths, templates. All paths use `pathlib.Path` for cross-platform compatibility.
- **errors.py**: Structured error codes (E{module}{type}) with recovery strategies for Agent decision-making.
- **file_lock.py**: Cross-platform file locking for concurrent access control. Uses fcntl (Unix) and msvcrt (Windows).
- **frontmatter.py**: SSOT for YAML frontmatter parsing/formatting. Re-exports attachment.py and schema.py for backward compat.
- **fts_search.py**: FTS5 full-text search with BM25 ranking. Extracted from search_index.py.
- **fts_update.py**: FTS5 index building/updating (incremental and full rebuild). Extracted from search_index.py.
- **metadata_cache.py**: SQLite-based L2 search cache. 50-100x performance improvement over file scanning.
- **path_contract.py**: Shared path normalization helpers for route-safe, user-safe journal paths.
- **schema.py**: Schema version management, metadata validation and migration. Extracted from frontmatter.py.
- **search_index.py**: FTS5 index management (init, stats) + backward-compat wrappers for fts_search.py and fts_update.py.
- **semantic_search.py**: Vector embedding search using BAAI/bge-m3 via shared sentence-transformers backend.
- **timing.py**: Performance timing utility for metrics collection. Used in tool outputs for monitoring.
- **url_download.py**: Shared URL download helper for attachment ingestion and related flows.
- **vector_index_simple.py**: Pure Python fallback vector index using numpy/pickle.

## CONVENTIONS

**SSOT Pattern**: `frontmatter.py` is the single source of truth for YAML frontmatter. Any format change must happen here first, then propagate to tools.

**Error Recovery**: All errors include a `recovery_strategy` field (`skip_optional`, `ask_user`, `continue_empty`, `fail`, `retry`). Agent uses this to decide next action.

**File Locking**: All write operations (journal, edit, index) use `FileLock` to prevent concurrent conflicts. Lock timeout defaults to 30s for journals, 60s for index operations.

**Semantic Search**: Uses sentence-transformers with BAAI/bge-m3 for multilingual embeddings. Core feature, always available.

## ANTI-PATTERNS

- **Never** duplicate frontmatter parsing logic in tools. Always import from `lib.frontmatter`.
- **Never** hardcode paths. Use `config.USER_DATA_DIR` and derived constants.
- **Never** duplicate `USER_DATA_DIR` resolution outside `tools/lib/config.py` (e.g., in `web/runtime.py`). Web/runtime code must import `config.USER_DATA_DIR` / `config.JOURNALS_DIR` directly, not recompute via `Path.home()`.
- **Never** raise bare exceptions. Use `LifeIndexError` with structured codes.
- **Never** skip error handling for vector index operations. Always use try/except with logging.
- **Never** write journals/indexes without acquiring the appropriate lock first.

## MODULE REGISTRY

> 本表记录每个 lib 模块的集成状态。任何新增模块必须登记；任何激活/弃用变更必须更新。

| 模块 | 消费者 | 集成状态 | 备注 |
|------|--------|---------|------|
| attachment.py | write_journal, frontmatter | ✅ 活跃 | |
| config.py | ALL tools | ✅ 活跃 | 路径 SSOT |
| content_analysis.py | write_journal | ✅ 活跃 | |
| embedding_backends.py | semantic_search | ✅ 活跃 | |
| entity_cache.py | write_journal | ⚠️ 待审视 | Round 4 Direction 4 候选 |
| entity_graph.py | write_journal, entity tool | ⚠️ 待审视 | Round 4 Direction 4 候选 |
| entity_schema.py | write_journal, entity_graph | ⚠️ 待审视 | Round 4 Direction 4 候选 |
| errors.py | write_journal(core), edit_journal, build_index | ⚠️ 部分集成 | Round 5 Task 3 将全面激活 |
| file_lock.py | write_journal, edit_journal, build_index | ✅ 活跃 | |
| frontmatter.py | write_journal, edit_journal, search | ✅ 活跃 | SSOT |
| fts_search.py | search_journals | ✅ 活跃 | |
| fts_update.py | build_index | ✅ 活跃 | |
| llm_extract.py | write_journal(prepare), content_analysis | ✅ 活跃 | |
| logger.py | ALL tools | ✅ 活跃 | |
| metadata_cache.py | search_journals, write_journal | ✅ 活跃 | |
| path_contract.py | write_journal, edit_journal | ✅ 活跃 | |
| paths.py | 多个 | ✅ 活跃 | |
| related_candidates.py | write_journal | ✅ 活跃 | |
| revisions.py | edit_journal | ✅ 活跃 | |
| schema_validator.py | dev tools | ✅ 活跃 | |
| schema.py | frontmatter | ✅ 活跃 | |
| search_config.py | search_journals | ✅ 活跃 | |
| search_constants.py | search_journals | ✅ 活跃 | |
| search_index.py | build_index, search_journals | ✅ 活跃 | |
| semantic_search.py | search_journals | ✅ 活跃 | |
| text_normalize.py | search, fts | ✅ 活跃 | |
| timing.py | ALL tools | ✅ 活跃 | Round 4 Direction 4 候选 |
| url_download.py | write_journal | ✅ 活跃 | |
| vector_index_simple.py | build_index | ✅ 活跃 | |
| workflow_signals.py | write_journal, errors | ✅ 活跃 | Round 5 Task 1 新增 |
| yaml_utils.py | frontmatter | ✅ 活跃 | |

## DEPENDENCIES

**This lib depends on**: Python 3.11+, pyyaml, numpy>=1.24.0, sentence-transformers>=2.6.0

**Tools depend on this lib**: write_journal, search_journals, edit_journal, generate_index, build_index, query_weather, backup, dev/validate_data, dev/rebuild_indices, dev/run_with_temp_data_dir, Web GUI service layer helpers
