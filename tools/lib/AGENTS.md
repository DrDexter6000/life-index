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
| Add semantic search feature | `semantic_search.py` | Uses fastembed (ONNX Runtime), multilingual embeddings |
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
- **metadata_cache.py**: SQLite-based L2 search cache. 50-100x performance improvement over file scanning.
- **path_contract.py**: Shared path normalization helpers for route-safe, user-safe journal paths.
- **schema.py**: Schema version management, metadata validation and migration. Extracted from frontmatter.py.
- **search_index.py**: FTS5 full-text search with BM25 ranking, incremental updates.
- **semantic_search.py**: Vector embedding search using paraphrase-multilingual-MiniLM-L12-v2, core dependency.
- **timing.py**: Performance timing utility for metrics collection. Used in tool outputs for monitoring.
- **url_download.py**: Shared URL download helper for attachment ingestion and related flows.
- **vector_index_simple.py**: Pure Python fallback vector index using numpy/pickle.

## CONVENTIONS

**SSOT Pattern**: `frontmatter.py` is the single source of truth for YAML frontmatter. Any format change must happen here first, then propagate to tools.

**Error Recovery**: All errors include a `recovery_strategy` field (`skip_optional`, `ask_user`, `continue_empty`, `fail`, `retry`). Agent uses this to decide next action.

**File Locking**: All write operations (journal, edit, index) use `FileLock` to prevent concurrent conflicts. Lock timeout defaults to 30s for journals, 60s for index operations.

**Semantic Search**: Uses fastembed with ONNX Runtime for multilingual embeddings (50+ languages). Core feature, always available.

## ANTI-PATTERNS

- **Never** duplicate frontmatter parsing logic in tools. Always import from `lib.frontmatter`.
- **Never** hardcode paths. Use `config.USER_DATA_DIR` and derived constants.
- **Never** duplicate `USER_DATA_DIR` resolution outside `tools/lib/config.py` (e.g., in `web/runtime.py`). Web/runtime code must import `config.USER_DATA_DIR` / `config.JOURNALS_DIR` directly, not recompute via `Path.home()`.
- **Never** raise bare exceptions. Use `LifeIndexError` with structured codes.
- **Never** skip error handling for vector index operations. Always use try/except with logging.
- **Never** write journals/indexes without acquiring the appropriate lock first.

## DEPENDENCIES

**This lib depends on**: Python 3.11+, pyyaml, fastembed>=0.5.1,<1.0, numpy>=1.24.0

**Tools depend on this lib**: write_journal, search_journals, edit_journal, generate_abstract, build_index, query_weather, backup, dev/validate_data, dev/rebuild_indices, dev/run_with_temp_data_dir, Web GUI service layer helpers
