# ADR-021: config.py God Module Split Scheme

**Status**: Proposed
**Date**: 2026-04-21
**Round/Phase**: Round 16 Package D

## Context

`tools/lib/config.py` currently re-exports approximately 46 symbols (constants + getters + third-party re-exports). It is the accumulation of "minimal incision" changes across Rounds 5 through 15. The file header itself acknowledges this:

```
Note: Path definitions moved to paths.py, search config moved to search_config.py
This module re-exports them for backward compatibility.
```

Despite that note, `config.py` has continued to grow. A full inventory of `__all__` exports reveals the following taxonomy.

### Export Inventory (46 symbols)

**Category 1 — Config loading (5 symbols):**

- `load_user_config`, `reload_user_config`, `USER_CONFIG`, `load_yaml_config`, `deep_merge`
- plus backward-compat aliases `_load_yaml_config`, `_deep_merge`

**Category 2 — Default values (2 symbols):**

- `get_default_location`, `DEFAULT_LOCATION`

**Category 3 — Weather API (5 symbols):**

- `get_weather_config`, `WEATHER_API_URL`, `WEATHER_ARCHIVE_URL`

**Category 4 — LLM configuration (4 symbols):**

- `get_llm_config`, `save_llm_config`, `save_default_location`

**Category 5 — Paths re-export (24 symbols):**

- `USER_DATA_DIR`, `PROJECT_ROOT`, `JOURNALS_DIR`, `BY_TOPIC_DIR`, `ATTACHMENTS_DIR`, `ABSTRACTS_DIR`, `CONFIG_DIR`, `CONFIG_FILE`, `ensure_dirs`, `JOURNAL_FILENAME_PATTERN`, `DATE_FORMAT`, `DATETIME_FORMAT`, `JOURNAL_TEMPLATE`, `get_journal_dir`, `get_next_sequence`, `sanitize_filename`, `get_path_mappings`, `PATH_MAPPINGS`, `normalize_path`, `get_safe_path`, `get_index_prefixes`, `INDEX_PREFIXES`, `resolve_user_data_dir`, `resolve_journals_dir`

**Category 6 — Lazy path getters re-export (13 symbols):**

- `reset_path_cache`, `get_user_data_dir`, `get_journals_dir`, `get_index_dir`, `get_fts_db_path`, `get_vec_index_path`, `get_vec_meta_path`, `get_cache_dir`, `get_metadata_db_path`, `get_by_topic_dir`, `get_attachments_dir`, `get_config_dir`, `get_config_file`

**Category 7 — Search config re-export (9 symbols):**

- `get_search_config`, `get_search_weights`, `save_search_weights`, `get_search_mode`, `save_search_mode`, `FILE_LOCK_TIMEOUT_DEFAULT`, `FILE_LOCK_TIMEOUT_REBUILD`, `FILE_LOCK_TIMEOUT_SEARCH`, `EMBEDDING_MODEL`, `get_model_cache_dir`

### Problems with Current Structure

1. **Import coupling**: Every tool that needs a single constant (e.g., `DATE_FORMAT`) imports the entire `config` module, dragging in YAML loading, weather API config, and LLM config
2. **Hidden third-party re-exports**: `load_yaml_config` and `deep_merge` are re-exported from `yaml_utils`; `EMBEDDING_MODEL` and `get_model_cache_dir` are re-exported from `search_config`; these are not obvious without reading the source
3. **Testability**: Cannot unit-test individual categories in isolation; config loading pulls in file system state
4. **Onion violation**: `config.py` is the "core" lib module but it depends on `paths.py`, `search_config.py`, and `yaml_utils` — lower-level modules depend on higher-level ones transitively
5. **Circular dependency risk**: As more tools import from `config.py`, any change to `paths.py` or `search_config.py` potentially breaks tool imports transitively

## Decision

### Target Module Structure

Split `config.py` into four focused modules:

**`tools/lib/config_settings.py`** — Application-level settings only

```
Constants: DEFAULT_LOCATION, WEATHER_API_URL, WEATHER_ARCHIVE_URL
Getters: get_default_location(), get_weather_config(), get_llm_config()
Savers: save_llm_config(), save_default_location()
Config loading: load_user_config(), reload_user_config(), USER_CONFIG
YAML helpers: load_yaml_config(), deep_merge() (re-exported from yaml_utils)
```

**`tools/lib/paths.py`** (already exists) — Path constants and lazy getters. No change.

**`tools/lib/search_config.py`** (already exists) — Search-specific configuration. No change.

**`tools/lib/config.py`** — Thin facade that re-exports everything for backward compatibility.

```
Re-exports all symbols from config_settings + paths + search_config.
__all__ unchanged (46 symbols).
Deprecation warning on first import: "config.py re-exports are deprecated; import from sub-modules directly."
```

### Migration Batch Plan

Ordered by risk (lowest import-surface impact first):

**Batch A — No consumer changes required (Round 17 Phase 1)**

- Extract `config_settings.py` from `config.py`
- Keep `config.py` as a facade that re-exports everything
- No tool or caller needs to change import statements during this phase
- Verify: `python -c "from tools.lib.config import DEFAULT_LOCATION; print(DEFAULT_LOCATION)"`

**Batch B — Update internal lib imports (Round 17 Phase 2)**

- Update `tools/lib/*.py` that import from `config` to use specific sub-module imports where easy
- No change to any tool's external API
- Verify: all pytest unit tests pass

**Batch C — Update tool imports (Round 18 Phase 1)**

- Update tool `__main__.py` or `cli.py` entry points to import from specific modules
- Begin emitting deprecation warnings from `config.py` facade
- Verify: `life-index health --json` returns valid response

**Batch D — Full deprecation (Round 18 Phase 2)**

- `config.py` facade still exists but warns on every import
- Update all SKILL.md / AGENTS.md references to use specific module imports
- Remove facade in Round 19 (if ever)

### Batch Acceptance Criteria

| Batch | Criteria |
|-------|----------|
| A | Import from `config.py` still works; `config_settings.py` standalone import works; no test file changed |
| B | All `tests/unit/lib/` pass; no tool entry point changed |
| C | `life-index health --json` works; deprecation warnings visible in logs; all pytest tests pass |
| D | Zero imports from bare `config` module in tool entry points; deprecation warning fires on `config` facade import |

### Compatibility Shim Strategy

**Facade vs atomic switch**: Use the facade approach (Batch A through C) because:

- Zero breaking changes for Agent consumers during migration window
- No caller needs to change import statements until Batch D
- Deprecation warnings give callers a runway to migrate voluntarily

**Atomic switch** (direct module swap without facade) is rejected because the import surface across all tools is large enough that a facade window is necessary for safe rollout.

**Import tracking**: Before Batch A, run a grep to establish baseline consumer list:

```bash
grep -r "from tools.lib.config import" tools/ --include="*.py"
grep -r "from tools.lib import config" tools/ --include="*.py"
```

Update this list at each batch boundary to track migration progress.

## Consequences

### Positive

- Focused modules are independently testable
- Tools that only need `DATE_FORMAT` no longer transitively load YAML / weather / LLM config
- Circular dependency risk reduced
- Sub-modules have clear boundaries matching the project's actual layering (`paths` is infrastructure, `search_config` is domain, `config_settings` is application)

### Negative

- `config.py` facade adds a temporary indirection layer (2-3 rounds)
- Import tracking across tools requires manual grep work at each batch boundary
- Some tools may import the entire `config` namespace as `from tools.lib.config import *` — these need explicit fixing

### Risk

- Any tool that does `from tools.lib.config import *` will break when the facade is removed; must be found and fixed in Batch C
- Circular import risk during refactoring: if `config_settings.py` is extracted and later tools need both `config_settings` and `paths`, the import order matters; mitigation is to ensure `config_settings.py` never imports from `paths.py` directly
