# CI Hard Checks — SSOT

**版本**: v0.1 (2026-05-23)
**目的**: 实现 `docs/PROJECT_WORKFLOW.md` v1.2 §M3 (d) push 前置门 L4 within-version revision 的 operational SSOT
**维护协议**: 任何 CI hard check 的新增/删除/变更 **必须**在同一 commit 同步更新本文件 + `scripts/pre-push-gate.sh`，commit message 含 "ci-hard-check inventory updated"

---

## 为什么这份文件存在

`PROJECT_WORKFLOW.md` v1.2 §M3 (d) 的 L4 within-version 补全说："本地 gate 必须 1:1 覆盖 CI 跑的全部 hard check，CI 有但本地无 = §(d) 失效"。

但 "1:1 覆盖" 不能靠每次主审记忆，必须有 SSOT。本文件就是该 SSOT。

历史实证：v1.1.1 release 主审凭记忆跑了 contract / blocker / compileall / diff_check，但漏 `jieba title test` (在 unit/ 不在 blocker mark) + `black --check`，push 后 CI 红 2 次，产生 2 个 post-tag commit (`52f5184` / `2b0696d`) 违反 §(d)。

---

## CI workflows in scope

| Workflow file | Trigger | In scope? | 说明 |
|---|---|---|---|
| `.github/workflows/tests.yml` | push main/develop + pull_request main | ✓ | blocker / contract / search-eval / quarantine / coverage |
| `.github/workflows/quality.yml` | push main/develop + pull_request main | ✓ | doc-sync / lint flake8 / black format / bandit / mypy |
| `.github/workflows/release.yml` | `workflow_dispatch` only | ✗ | 手动 publish，跟 push 不冲突 |
| `.github/workflows/benchmark.yml` | (查看具体 trigger) | ✗ | perf 测量，不是 hard check |
| `.github/workflows/nightly.yml` | nightly schedule | ✗ | nightly only，不阻塞 push |

---

## Hard Checks 清单

| # | Check | 命令 (Scope) | Source workflow | Hard? | 本地命令 |
|---|---|---|---|---|---|
| 1 | blocker gate | `pytest -m blocker --timeout=120` (matrix: ubuntu+windows × py3.11+py3.12) | tests.yml | ✓ YES | `pytest -m blocker -q --timeout=120` |
| 2 | contract gate | `pytest -m contract --timeout=120` (ubuntu py3.12) | tests.yml | ✓ YES | `pytest -m contract -q --timeout=120` |
| 3 | search-eval-gate | 10 个具体 eval test 文件 (见 tests.yml `search-eval-gate` job) | tests.yml | ✓ YES | 同 CI（脚本封装） |
| 4 | doc-sync | `python .github/scripts/check_doc_sync.py` | quality.yml | ✓ YES | 同 CI |
| 5 | lint flake8 | `flake8 tools/ --count --max-complexity=40 --max-line-length=100 --show-source --statistics` | quality.yml | ✓ YES | 同 CI |
| 6 | format black | `black --check --diff tools/` | quality.yml | ✓ YES | `python -m black --check tools/` |
| 7 | security bandit | `bandit -r tools/ -ll -c pyproject.toml` | quality.yml | ✓ YES | 同 CI |
| 8 | typecheck mypy | `mypy tools/ --ignore-missing-imports` | quality.yml | ✓ YES | 同 CI |
| Q | quarantine | `pytest -m quarantine --timeout=300` | tests.yml | ✗ continue-on-error | （不在 pre-push gate） |
| C | coverage | `pytest -m "blocker or contract" --cov` | tests.yml | ✗ continue-on-error | （不在 pre-push gate） |

### 重要 scope 边界

- **black/flake8/bandit/mypy 只检查 `tools/`，不检查 `tests/`**：CI 这样设计；本地 1:1 跟随，不扩展 scope。否则会因 `tests/` 109 文件未 format 而产生大量"假 fail"。
- **blocker test scope**: `pytest -m blocker` 收集 mark 为 `blocker` 的 test，跨 `tools/` 和 `tests/`。
- **不要在 pre-push gate 加 quarantine/coverage**：CI 这些 jobs 是 `continue-on-error: true`，本地强制只会增加噪音。

---

## 本地 pre-push gate 入口

```bash
bash scripts/pre-push-gate.sh
```

行为：
- 顺序跑所有 hard check（fail-fast OFF，全部跑完汇总）
- 全部 PASS → exit 0，打印 "ALL CHECKS PASS — safe to push"
- 任一 FAIL → exit 1，打印 FAILED CHECKS 清单
- 输出落盘到 `.agent-reports/pre-push-gate/run_<timestamp>.log`
- 总 wall-clock 预期 < 15 分钟

---

## 维护协议（强制）

CI hard check 的任何变更必须满足：

1. **同 commit 双更新**：`.github/workflows/{tests,quality}.yml` + 本文件 + `scripts/pre-push-gate.sh`
2. **commit message tag**: 包含 `ci-hard-check inventory updated`
3. **PRD/RFC anchored**：如果新增/删除 hard check 涉及质量门变更，必须有上游 PRD 或 RFC 引用本文件
4. **回归 audit**：变更后第一次 push 前必须 `bash scripts/pre-push-gate.sh` 全绿（不可豁免）

违反协议 = §(d) push 前置门失效；下次 CI 红时 retrospective 必须列出本协议违反点。

---

## 版本历史

- **v0.1 (2026-05-23)**：初版。基于 v1.1.1 release retrospective + V1.5/v1.2 L4 within-version revision 落地。8 个 hard check + 2 个 non-hard check 清单。
