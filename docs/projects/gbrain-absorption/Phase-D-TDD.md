# Phase D TDD Brief — Maintenance cycle (#4)

> **Phase**: D | **gbrain Candidate**: #4
> **Worktree**: `.claude/worktrees/gbrain-D/`
> **Branch**: `claude/gbrain-D`
> **Wave**: 2 (**blocked by Phase A + Phase C**)
> **PRD**: `docs/projects/gbrain-absorption/PRD.md` §5 Phase D

## 派发纪律 3 门（PRD §5 引用）

- **可证伪退出**: `maintenance --dry-run` 输出 6 类检查报告（index freshness / entity audit / orphan related_entries / search eval smoke / backup verification / candidate edges 数量）；零 production 写入断言通过；`test_maintenance_contract.py` 通过
- **真实消费者**: 用户 nightly / weekly 跑健康巡检 + CI cron（如启用）
- **有界自主**:
  - 可写：`tools/maintenance/`（新建模块）, `tests/contract/test_maintenance_contract.py`
  - 可读：`tools/eval/ablation/`（Phase A）, `tools/entity/`（Phase C）, `tools/build_index/`, `tools/backup/`, `tools/health/`
  - **不动**：被调用模块的源代码

## 依赖前置

- Phase A 必须 merged（`entity-graph-eval` 可调）
- Phase C 必须 merged（`entity --candidate-edges` 可调）
- subagent 派发时验证：两 phase merge commit 已在 main

## Task 清单

1. **Pull rebase**：`git pull --rebase origin main`
2. **Scaffold**：`tools/maintenance/{__init__.py, __main__.py, core.py, checks.py}`
3. **Test (RED)**：`tests/contract/test_maintenance_contract.py`：
   - 测 `maintenance --dry-run` 输出 6 类报告
   - 测每报告含 `pass | fail | needs-user-action` 状态
   - 测**零 production 写入**断言
   - 测 6 检查项均通过 subprocess 调既有 CLI（不直接 import 被调模块内部）
4. **Implement (GREEN)**：
   - `checks.py` 6 函数：
     - `check_index_freshness()` → subprocess `build-index --verify`
     - `check_entity_audit()` → subprocess `entity --audit`
     - `check_orphan_related_entries()` → 扫 frontmatter 找无对应实体的 related_entries
     - `check_search_eval_smoke()` → subprocess `entity-graph-eval` 小规模 (3 queries)
     - `check_backup_verification()` → subprocess `backup --verify`（如存在）
     - `check_candidate_edges_count()` → subprocess `entity --candidate-edges`，报告数量 & 高置信占比
   - `core.py` 聚合 6 检查结果，归类为 pass/fail/needs-action
   - `__main__.py` CLI 入口 + 输出格式（默认 text，`--output=json` 可选）
5. **CLI 注册**：`tools/__main__.py` 加 `maintenance` 子命令；schema_version 戳
6. **Docs**：`docs/API.md` 加 `maintenance` 命令文档；`CHANGELOG.md` 加条目
7. **Self-check**
8. **PR**

## 红绿测试要求

- TDD 严格
- 必含"零写入"测试（运行前后选定 production 文件 hash 不变）
- 必含"subprocess 模式"测试（不直接 import 被调模块）

## 验收标准

- `maintenance --dry-run` 输出 6 检查报告
- 每报告含 pass/fail/needs-user-action
- 零写入断言 PASS
- `test_maintenance_contract.py` PASS
- `test_layer_invariants.py` PASS（含 maintenance 不引入 LLM 断言）
- `docs/API.md` 已更新
- `CHANGELOG.md` 已更新
- `maintenance --output=json` 工作

## 自检 Checkbox

- [ ] 契约测试 PASS
- [ ] Layer invariant PASS
- [ ] 零写入测试 PASS（production 文件 hash 不变）
- [ ] 6 检查项每个独立测试覆盖
- [ ] subprocess 模式（不直接 import 被调模块）
- [ ] `maintenance --dry-run` 可跑
- [ ] `maintenance --output=json` 可跑
- [ ] 默认无 LLM
- [ ] `docs/API.md` 已更新
- [ ] `CHANGELOG.md` 已更新

## 下一 Task 指针

PR merged → 主控勾 Phase D → 等其他 phase 全完进 M4 集成验证。

## 执行总结（subagent 完成后填）

```
完成时间: <TBD>
实际 LOC: <TBD>
遇到的难点: <TBD>
验收证据:
  - test_maintenance_contract.py output: <snippet>
  - sample maintenance --dry-run output: <full report snippet>
  - zero-write hash test: <before/after hashes>
```
