# WP-CLI-SEM-RM: Drop In-Tool Vector/Semantic Search

## 1. Verdict

Status at report write time: LOCAL PASS, PR/remote CI pending.

This work package removes active in-tool vector/semantic retrieval from Life Index CLI search, smart-search, index, eval, and health paths. Retrieval is now deterministic keyword search plus Entity Graph support. Legacy `--semantic*` flags are still accepted for caller compatibility and are explicit deprecated no-ops.

Legacy semantic/vector modules remain in the tree where unrelated tests or compatibility code still reference them, but the active CLI paths no longer import, build, require, or dispatch them.

## 2. Starting State And Branch

Source branch:

```text
COMMAND: git fetch origin main
OUTPUT:
From https://github.com/DrDexter6000/life-index
 * branch            main       -> FETCH_HEAD
   8e63f7c..a7dc028  main       -> origin/main
```

Work branch:

```text
COMMAND: git worktree add -b refactor/drop-in-tool-semantic <isolated-worktree> origin/main
OUTPUT:
branch 'refactor/drop-in-tool-semantic' set up to track 'origin/main'.
HEAD is now at a7dc028 feat(index-tree): refresh canonical navigation indexes
```

Initial shared checkout status was captured before branching. The full raw porcelain output is intentionally not committed because it contained private local path names that the public-private-name gate forbids in PR-added lines. Public-safe summary: the shared checkout already had unrelated dirty tracked docs/eval files and private untracked local artifacts. It was not edited.

Initial isolated worktree status:

```text
COMMAND: git status --porcelain
OUTPUT:
<empty>
```

```text
COMMAND: git status -sb
OUTPUT:
## refactor/drop-in-tool-semantic...origin/main
```

## 3. Implementation Summary

Code changes:

- `tools/search_journals/core.py` now runs deterministic keyword search only. `semantic_results` stays empty, `semantic_available` is false, requested semantic policy is reported as `deprecated_noop`, and a deprecation warning is emitted when semantic flags are present.
- `tools/search_journals/orchestrator.py` and `tools/smart_search/__main__.py` no longer use semantic fallback strategy. Query plans report keyword-only deterministic behavior.
- `tools/build_index/__init__.py` and `tools/build_index/__main__.py` build FTS only. `--vec-only` and `--with-semantic` are accepted as deprecated no-ops. Manifest vector fields are legacy zero/empty values.
- `tools/eval/run_eval.py` and `tools/eval/__main__.py` keep `--semantic` and `--semantic-report` safe as no-ops. Default eval still runs.
- `tools/__main__.py` health reports semantic/vector search as disabled, not failed.
- `tools/verify/core.py`, `tools/lib/index_freshness.py`, `tools/build_index/diagnostics.py`, and `tools/write_journal/index_updater.py` no longer require vector index freshness or vector writes.
- `pyproject.toml` removes `sentence-transformers` and the `[semantic]` extra.

Docs changed: `CHARTER.md`, `README.md`, `SKILL.md`, `docs/API.md`, and `docs/ARCHITECTURE.md`.

Tests changed: semantic behavior tests now assert compatibility no-op semantics, index/vector tests assert FTS-only behavior, eval tests assert no-op semantic reporting, and a focused `tests/unit/test_semantic_flags_noop.py` was added.

## 4. Compatibility Contract

Preserved CLI flags:

- `life-index search --semantic`
- `life-index search --no-semantic`
- `life-index search --semantic-policy fallback`
- `life-index search --semantic-weight <float>`
- `life-index eval --semantic`
- `life-index eval --semantic-report`
- `life-index index --vec-only`
- `life-index index --with-semantic`

Observed behavior:

```text
search --semantic --semantic-policy fallback:
semantic_results: []
semantic_available: false
semantic_fallback_used: false
semantic_effective_policy: deprecated_noop
warnings: deprecated_noop: --semantic* flags are accepted for compatibility but ignored; search now uses keyword + Entity Graph only.
```

Health behavior:

```text
search_index.semantic_status: disabled
search_index.semantic.status: disabled
search_index.semantic.reason: in-tool semantic/vector search has been removed
```

## 5. Local Gate Evidence

Blocker matrix local representative gate:

```text
COMMAND: python -m pytest -m blocker -q --timeout=120
OUTPUT:
........................................................................ [  2%]
...
............                                                             [100%]
EXIT_CODE: 0
```

Contract gate:

```text
COMMAND: python -m pytest -m contract -q --timeout=120
OUTPUT:
.sssss.................................................................. [ 10%]
...
...............................................................          [100%]
EXIT_CODE: 0
```

Search Eval Quality Gate test set:

```text
COMMAND: python -m pytest tests/unit/test_eval_gate.py tests/unit/test_eval_runner.py tests/unit/test_eval_llm.py tests/eval/test_broad_eval_soft_gate.py tests/eval/test_semantic_report.py tests/eval/test_eval_compare.py tests/eval/test_eval_run.py tests/eval/test_eval_qrels.py tests/eval/test_eval_export.py tests/eval/test_eval_serialization.py -q --timeout=120
OUTPUT:
sssssssssssssssssssssssssssssssssssssssssss............................. [ 28%]
...
.....ssssssssss....................                                      [100%]
EXIT_CODE: 0
```

Doc sync and public gates:

```text
COMMAND: python .github/scripts/check_doc_sync.py
OUTPUT:
所有检查通过！
EXIT_CODE: 0

COMMAND: python .github/scripts/check_public_diff_names.py
OUTPUT:
Public diff private-name check passed.
EXIT_CODE: 0

COMMAND: python .github/scripts/check_public_surface_allowlist.py
OUTPUT:
Public surface allowlist check passed.
EXIT_CODE: 0

COMMAND: python .github/scripts/check_l2_no_llm.py
OUTPUT:
L2 no-LLM check passed.
EXIT_CODE: 0
```

Lint, security, and type checks:

```text
COMMAND: flake8 tools/ --count --max-complexity=40 --max-line-length=100 --show-source --statistics
OUTPUT:
0
EXIT_CODE: 0

COMMAND: python -m black --check tools
OUTPUT:
EXIT_CODE: 0

COMMAND: python -m bandit -r tools/ -ll -c pyproject.toml
OUTPUT:
No issues identified.
EXIT_CODE: 0

COMMAND: mypy tools/ --ignore-missing-imports
OUTPUT:
Success: no issues found in 203 source files
EXIT_CODE: 0
```

Full pytest:

```text
COMMAND: python -m pytest -q
OUTPUT:
.............................sssss...................................... [  1%]
...
EXIT_CODE: 0
```

Clean install smoke:

```text
COMMAND: powershell -NoProfile -ExecutionPolicy Bypass -Command <clean install smoke script>
OUTPUT:
sentence-transformers not installed (expected)
RUN: index --json
"semantic_status": "disabled"
RUN: search --query keyword
"total_found": 1
RUN: search --query keyword --semantic --semantic-policy fallback
"semantic_effective_policy": "deprecated_noop"
RUN: smart-search --query keyword smoke
"filtered_results": [
RUN: health --json
"semantic_status": "disabled"
"reason": "in-tool semantic/vector search has been removed"
EXIT_CODE: 0
```

## 6. Eval Evidence

Default eval:

```text
COMMAND: python -m tools eval
OUTPUT:
Queries: 108
MRR@5: 0.6259
Recall@5: 0.9231
Precision@5: 0.5351
nDCG@5: 0.6602
Failures: 5
FAIL GQ25 "我的女儿" - Expected >= 3 results, got 2
FAIL GQ34 "CEO任务" - Expected >= 1 results, got 0
FAIL GQ51 "今年一月份发生了什么" - Expected >= 1 results, got 0
FAIL GQ57 "四月初的国际新闻" - Expected >= 2 results, got 0
FAIL GQ65 "中东局势的深度分析" - Expected >= 2 results, got 0

Broad Eval (15 queries):
  Strict pass: 15/15 (100%)
  Soft pass:   15/15 (100%)
  Fail:        0/15

Aggregate Eval (7 queries):
  total_queries: 7
  passed_queries: 7
  failed_queries: 0
EXIT_CODE: 0
```

The metrics match the stated baseline exactly and retain the same five failing query IDs.

## 7. Acceptance Checklist

- [x] Semantic/vector pipeline removed from active search and smart-search paths; `sentence-transformers` and `[semantic]` extra removed from `pyproject.toml`.
- [x] Index no longer builds vector indexes.
- [x] `--semantic*` flags are retained as accepted deprecated no-ops; `search --semantic --semantic-policy fallback` does not error.
- [x] Eval runs; metrics are at baseline; failures remain 5 with no new IDs.
- [x] Health reports semantic/vector as disabled rather than failed.
- [x] Docs updated, including the README explanation for no in-tool vector RAG.
- [x] `python -m pytest -q` passes locally.
- [ ] Remote required CI green. Pending until PR is opened.
- [x] Eight-section report written before completion claim.
- [x] Stop point is PR review; no merge performed.

## 8. PR And Residual Risk

PR state at report write time: not opened yet. This report is written before PR creation as required.

Residual risk:

- Legacy semantic/vector modules are retained but disconnected from active CLI paths. Removing those files outright would be a larger compatibility/test cleanup and is outside this deterministic subtraction scope.
- Clean-install health in a one-entry sandbox can be degraded for missing Entity Graph/index-tree artifacts; the semantic check itself is disabled and non-failing, which is the acceptance target.
- Remote CI must still confirm the required matrix and public checks after push.
