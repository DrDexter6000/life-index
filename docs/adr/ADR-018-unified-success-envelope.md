# ADR-018: Unified Success Response Envelope

**Status**: Accepted
**Date**: 2026-04-21
**Round/Phase**: Round 16 Package D (Task D.2)

## Context

### Why a Unified Envelope Is Necessary

The error envelope is fully standardized. `tools/lib/errors.py` defines `LifeIndexError.to_json()` which produces a consistent structure with `success`, `error.code`, `error.message`, `error.recovery_strategy`, etc.

Success responses, however, are **structurally inconsistent**. A survey of current tool outputs reveals:

| Tool | Top-level shape | Notes |
|------|----------------|-------|
| `query_weather` | `success, date, location, weather, error` | flat top-level |
| `backup` | `success, backup_path, files_backed_up, error` | flat top-level |
| `write_journal` | `success, write_outcome, journal_path, ...` | `write_outcome` as primary signal |
| `search_journals` | `success, merged_results, entity_hints, ...` | `merged_results` not `data` |
| `build_index` | `success, fts, vector, duration_seconds` | fts/vector not wrapped |
| `generate_index` | `success, type, year, month, output_path, message` | flat top-level |
| `health` | `success, data, events` | already uses `data` wrapper |
| `entity --stats` | `success, data, error` | already uses `data` wrapper |

This inconsistency forces Agent consumers to write **tool-specific response parsing logic** for each tool. The problem is not aesthetic — it is **engineering overhead per tool** with compounding maintenance cost.

### What This ADR Does

Defines a canonical success envelope schema, creates a shared helper module (`tools/lib/envelope.py`), and pilots exactly one tool (`entity --stats`) in Round 16. Full migration is deferred to Round 17+.

### What This ADR Does NOT Do

- Does NOT change the error envelope (already defined in `errors.py`)
- Does NOT migrate any core search tools in this round
- Does NOT break backward compatibility for any tool consumer

## Decision

### Canonical Success Envelope Schema

```json
{
  "ok": true,
  "data": { ... },
  "_trace": { ... },
  "events": [ ... ]
}
```

**Field semantics:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ok` | `bool` | Always | `true` for success; mirrors `success: false` in error envelope |
| `data` | `dict` | Always | Tool-specific result payload. Never `None`; empty dict `{}` for no-data responses |
| `_trace` | `dict` | Always (may be empty) | Observability fields: `trace_id`, `command`, `total_ms`, `steps`. Underscore prefix marks it as internal. Defaults to `{}` |
| `events` | `list` | Always (may be empty) | Piggyback event notifications (streak alerts, review reminders, etc.). Defaults to `[]` |

**Why `ok` instead of `success`:**

The error envelope uses `success: false`. The new success envelope uses `ok: true`. This **intentional asymmetry** provides a migration path:
- Tools that have been migrated: check `result["ok"]`
- Tools not yet migrated: check `result["success"]`
- Agent consumers can safely check both: `result.get("ok", result.get("success", False))`

After full migration (Round 18+), the legacy `success` field can be deprecated and removed.

**What goes in `_trace`:**

| Sub-field | Type | Description |
|-----------|------|-------------|
| `trace_id` | `str` | 8-character hex string for request correlation |
| `command` | `str` | Tool name (e.g., `"stats"`, `"search"`) |
| `total_ms` | `float` | Total wall-clock time in milliseconds |
| `steps` | `list` | Optional breakdown of sub-operations with timing |

**What goes in `events`:**

Event types already defined in `docs/API.md` §"Response: events 字段":

| Event type | Trigger condition |
|-----------|-------------------|
| `no_journal_streak` | 7+ days without a journal entry |
| `monthly_review_due` | Last month's report file missing |
| `entity_audit_due` | entity_graph.yaml not modified in 30+ days |
| `schema_migration_available` | Old schema version journals exist |
| `index_stale` | Journals newer than index |

### Helper Module: `tools/lib/envelope.py`

```python
def success(data: dict, *, trace: dict | None = None, events: list | None = None) -> dict:
    """Wrap tool output in unified success envelope."""
    return {
        "ok": True,
        "data": data,
        "_trace": trace or {},
        "events": events or [],
    }
```

Usage in a tool:

```python
from tools.lib.envelope import success

def my_tool():
    result = do_work()
    return success(
        {"entries": result, "count": len(result)},
        trace={"trace_id": "abc12345", "total_ms": 42.0},
    )
```

### Round 16 Pilot: `entity --stats`

**Pilot tool**: `tools/entity/stats.py` (`compute_stats`)

**Why this tool:**
1. Read-only — no mutation risk
2. Already has a `data` wrapper in its return value — minimal shape change
3. Well-tested (`tests/unit/test_entity_stats_check.py` with 6 existing tests)
4. Low call frequency — rarely invoked, low blast radius
5. No Agent consumer depends on its exact return shape for critical workflows

**Change**: Replace the current `{"success": True, "data": {...}, "error": None}` return with `envelope.success({...})` producing `{"ok": True, "data": {...}, "_trace": {}, "events": []}`.

### Hard Constraint: Core Search Tools Freeze

**The following tools MUST NOT be migrated until the Round 16 feature freeze ends:**

- `tools/search_journals/` — core retrieval path, too many callers depend on current shape
- `tools/build_index/` — core indexing path, tightly coupled with search
- Any tool using `--rebuild` flag

These tools are listed in Group C (High Risk) below. They may only be migrated in Round 17 Phase 2 or later, after the freeze ends and after the pilot has been validated in production.

### Migration Plan: Tool Groups by Risk

#### Group A — Low Risk (Round 16 pilot, this task)

| Tool | Reason | Status |
|------|--------|--------|
| `entity --stats` | Read-only, already has `data` wrapper, well-tested | ✅ Pilot |

#### Group B — Low-Medium Risk (Round 17 Phase 1)

| Tool | Reason | Notes |
|------|--------|-------|
| `entity --check` | Read-only, similar shape to stats | Same module as pilot |
| `entity --audit` | Read-only diagnostic | Same module as pilot |
| `entity --review` (queue only) | Read-only queue display | |
| `query_weather` | Flat response, simple wrap | Already close to canonical |
| `backup` | Simple file operation, clean data wrap | Low call frequency |
| `generate_index` | Flat response, simple wrap | |
| `health` | Already has `data` wrapper, just needs `ok` + `_trace` | Easiest migration |

#### Group C — High Risk (Round 17 Phase 2, after freeze)

| Tool | Reason | Notes |
|------|--------|-------|
| `write_journal` | Largest payload, many callers depend on flat fields | `write_outcome` + confirmation flow |
| `search_journals` | `merged_results` rename, entity hints, search plan | Most complex response shape |
| `edit_journal` | Similar to write_journal, confirmation flow | |
| `build_index` | Core indexing, coupled with search | `--rebuild` flag |
| `entity --merge` / `--delete` | Mutation operations, review queue coupling | |
| `migrate` | Schema migration tool, low call frequency but complex output | |

#### Group D — Dev/Internal (Round 18 or later)

| Tool | Reason |
|------|--------|
| `tools/dev/*` | Developer tools, not Agent-facing |
| `tools/verify/*` | Verification tools |
| `tools/timeline/*` | Timeline tools |
| `tools/eval/*` | Evaluation tools |

### Compatibility Strategy

**No breaking changes during migration window.**

1. Migrated tools use the new envelope (`ok/data/_trace/events`)
2. Unmigrated tools retain their current shape (`success/.../error`)
3. Agent consumers should check both: `result.get("ok", result.get("success", False))`
4. After Round 18, when all tools are migrated, the `success` field can be deprecated

**The `data` wrapper is never optional once introduced.** If a tool returns a scalar or null, wrap it: `{"data": null}` or `{"data": {"value": 42}}`.

### Error Envelope Unchanged

The error envelope defined in `tools/lib/errors.py` (`LifeIndexError.to_json()`) is canonical and does not change. The `success: false` branch is unaffected by this ADR.

## Consequences

### Positive

- Agent consumers can parse migrated tool responses through a single schema pattern
- `_trace` block enables zero-code-change observability across all tools
- `events` block already exists in some tools; making it universal enables consistent event consumption
- Pilot validates the schema with minimal risk before wider rollout

### Negative

- Dual format during migration window (some tools `ok`, some `success`)
- Existing tests for the pilot tool need updating
- Agent consumers need a transition-period compatibility check

### Risk

- If Agent consumers hard-code `result["success"]` checks, they will break when tools switch to `ok`
- Mitigation: announce in SKILL.md and API.md simultaneously; provide the `result.get("ok", result.get("success"))` pattern
- Pilot tool (`entity --stats`) has very low consumer surface, minimizing impact

## Files

- Envelope helper: `tools/lib/envelope.py`
- Error envelope SSOT: `tools/lib/errors.py`
- Pilot tool: `tools/entity/stats.py`
- Pilot tests: `tests/unit/test_entity_stats_check.py` (existing), `tests/unit/test_envelope_stats_pilot.py` (new)
- API reference: `docs/API.md`
