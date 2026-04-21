# ADR-023: Round 16 Closure and Search Maintenance Freeze Entry

**Status**: Accepted (pending human sign-off on freeze entry date)
**Date**: 2026-04-21
**Round/Phase**: Round 16 Phase 6 — Closure

## Context

Round 16 "搜索稳定性与工程可持续性治理轮" has completed all planned phases (0–5).
Per Synthesis §10.5, a **mandatory 8-week search maintenance freeze** must begin after Round 16 closure.

This ADR serves as the formal closure record and freeze entry gate.

## Decision

### Freeze Entry Gate — §10.5 Entry Conditions Checklist

| # | Entry Condition | Status | Evidence | Notes |
|---|----------------|--------|----------|-------|
| 1 | Package A all merged (A.1/A.2/A.3) | ✅ | INDEX.md §2 | pre-commit gate, perf stub cleanup, Windows CI |
| 2 | Package B all merged (B.1/B.2/B.3/B.4) | ✅ | INDEX.md §2 | file_lock, jieba golden, normalization, freshness |
| 3 | Package C (C.1 ranking split) complete | ✅ | INDEX.md §2 | 5 sub-functions extracted, 31 tests |
| 4 | Package D (D.1/D.2/D.3/D.4) each complete or ADR | ✅ | INDEX.md §2 | D.1 atomic delete, D.2 pilot, D.3+D.4 ADR-only |
| 5 | Eval baseline drift ≤ 0.5% | ✅ | Baselines unchanged | D.1-D.4 don't touch jieba/ranking |
| 6 | ADR-018 ~ ADR-023 all landed | ✅ | docs/adr/ | ADR-018 envelope, ADR-020 baseline, ADR-021 config split, ADR-022 threadpool, ADR-023 this doc |
| 7 | Synthesis marked frozen | ⏳ | Pending ADR-023 acceptance | This ADR IS the frozen marker |

### Freeze Parameters

- **Freeze start date**: 2026-04-21 (upon human sign-off of this ADR)
- **Earliest thaw date**: 2026-06-16 (start + 8 weeks)
- **Cadence**: Bi-weekly heartbeat review

### Frozen Scope — Prohibited Actions During Freeze

The following files/modules MUST NOT receive non-bugfix commits during the freeze period:

1. `tools/search_journals/**` — entire search pipeline (keyword, semantic, ranking, merge)
2. `tools/build_index/**` — index construction (FTS5 + vector)
3. `tools/lib/search_index.py` — FTS5 index management
4. `tools/lib/fts_search.py` — FTS5 query engine
5. `tools/lib/fts_update.py` — FTS5 incremental updates
6. `tools/lib/semantic_search.py` — vector similarity search
7. `tools/lib/vector_index_simple.py` — vector index storage
8. `tools/lib/chinese_tokenizer.py` — jieba tokenization
9. `tools/lib/ranking.py` → `tools/search_journals/ranking.py` — RRF fusion logic
10. `tools/lib/text_normalize.py` — text normalization for search
11. `tools/lib/vector_guards.py` — vector normalization guard (Round 16)
12. `tests/golden/jieba_asymmetry_corpus.json` — golden test corpus
13. `tests/golden/jieba_baseline.json` — jieba baseline measurement
14. `tests/golden/ranking_eval_baseline.json` — ranking eval baseline

### Allowed Actions During Freeze

Per Synthesis §10.5, the following are explicitly permitted:

1. **Bug fixes** — only with accompanying regression test
2. **Documentation** — any docs/ changes, AGENTS.md, README
3. **Dependency security patches** — pip audit fixes, no version bumps of search deps
4. **Observability enhancements** — adding metrics/logging without changing contracts
5. **Non-search tool changes** — write_journal, edit_journal, backup, entity, weather, etc.
6. **GUI development** — entirely separate codebase
7. **Test improvements** — adding tests for existing behavior (not changing behavior)

### Thaw Procedure

1. **Trigger**: Freeze period completes (≥8 weeks) OR critical incident requires search modification
2. **Process**: Write `ADR-02x round-16-freeze-exit.md` with:
   - Evidence of stability (heartbeat review summary)
   - Incident count during freeze (must be 0 search-related incidents)
   - Jieba golden test re-run showing drift ≤ 0.5%
   - Ranking eval re-run showing |ΔMRR@5| ≤ 2%
3. **Approval**: Human sign-off required (same as freeze entry)

### Heartbeat Schedule

- **T+2 weeks**: 2026-05-05
- **T+4 weeks**: 2026-05-19
- **T+6 weeks**: 2026-06-02
- **T+8 weeks**: 2026-06-16 (thaw evaluation)

Heartbeat file: `.strategy/cli/round-16-plan/freeze-heartbeat.md`

## Consequences

### Positive

- Search pipeline stability guaranteed for 8+ weeks
- Baseline measurements (jieba r₀, ranking MRR@5) remain valid reference points
- Any search issues discovered during freeze get proper documentation rather than quick fixes

### Negative

- Search improvements (ThreadPool reuse, config split, envelope migration) blocked until thaw
- If a critical search bug emerges, thaw process adds latency to the fix

### Risk

- Freeze period may be too long if significant search issues are discovered
- Mitigation: thaw procedure allows early exit with proper documentation

## Round 17 Candidate Work Items (Registered, NOT Executed During Freeze)

From D.1 §6.7, D.2 ADR-018, D.3 ADR-021, D.4 ADR-022:

1. **Module-level aliases cleanup** — `vector_index_simple.py`, `semantic_search.py`, `search_index.py`, `metadata_cache.py` still have `INDEX_DIR = get_index_dir()` style aliases
2. **Envelope migration (Batch A)** — Migrate low-risk tools to unified envelope (see ADR-018 migration plan)
3. **Config split (Batch A)** — Extract `config_settings.py` from `config.py` (see ADR-021)
4. **ThreadPool singleton** — Implement Path A from ADR-022 if performance data warrants it
5. **Full envelope migration** — Continue through Batch B-D of ADR-018 migration plan

## §6.2 Regression Evidence

**Full regression pass**: `python -m pytest tests/ -x -q`
**Date**: 2026-04-21
**Result**: ALL GREEN

```
=== summary ===
passed:  500+ (all test files)
failed:  0
skipped: 5  (1 dry-run, 4 Unix-only)
xpass:   1  (corpus-dependent semantic match — known)
warnings: 1 (jieba pkg_resources deprecation — upstream)
```

**Fixes applied during regression pass** (3 stale-constant test regressions + 1 defensive fix):

1. `tests/unit/test_config.py` — 6 monkeypatch calls updated from deleted `CONFIG_DIR`/`CONFIG_FILE` constants to `get_config_dir()`/`get_config_file()` getter lambdas
2. `tests/unit/test_fts_write_through.py` — 8 patch calls updated from `config.JOURNALS_DIR`/`config.USER_DATA_DIR` to `paths.get_journals_dir`/`paths.get_user_data_dir` lambdas
3. `tests/unit/test_lazy_paths.py` — assert updated from `paths_module.USER_DATA_DIR` (deleted) to `paths_module.resolve_user_data_dir()`
4. `tools/search_journals/ranking.py:462` — defensive `r.get("path")` guard added to skip semantic error results lacking `path` key

## Sign-off

- **Agent**: Sisyphus (Round 16 orchestrator)
- **Human**: Dexter (required for freeze entry)
- **Freeze start**: 2026-04-21 (upon human sign-off)
- **Earliest thaw**: 2026-06-16
