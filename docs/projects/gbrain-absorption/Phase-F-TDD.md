# Phase F TDD Brief — Facts/trajectory + trajectory module (#6)

> **Phase**: F | **gbrain Candidate**: #6
> **Worktree**: `.claude/worktrees/gbrain-F/`
> **Branch**: `claude/gbrain-F`
> **Wave**: 1 (independent)
> **预估规模**: L (>3 天) — 6 phase 中最大
> **PRD**: `docs/projects/gbrain-absorption/PRD.md` §5 Phase F + §3.1 (trajectory 模块边界)

## 派发纪律 3 门（PRD §5 引用）

- **可证伪退出**: `trajectory --field={weight|sleep|mood|location|project} --range=...` 输出 typed observation JSON 含 `evidence_paths`；零 L1 schema 写断言通过；`test_trajectory_contract.py` 通过（每 field 至少 1 测）
- **真实消费者**: trajectory 模块本身（Step 3 真模块的 v1）
- **有界自主**:
  - 可写：`tools/trajectory/`（新建模块）, `tests/contract/test_trajectory_contract.py`, `tests/fixtures/trajectory/sample_journals/`（测试样本日记）
  - 可读：L2 `search` / `aggregate` / `analyze` 的 CLI 文档（不读源）
  - **不动**：L1 frontmatter / journal 写入逻辑、`~/Documents/Life-Index/` 真实数据

## Task 清单

1. **Scaffold**：`tools/trajectory/{__init__.py, __main__.py, core.py, extractors/{weight.py, sleep.py, mood.py, location.py, project.py}}`
2. **Fixture**：`tests/fixtures/trajectory/sample_journals/`，至少 10 篇 mock journals，每篇含部分 fields
3. **Test (RED)**：`tests/contract/test_trajectory_contract.py`：
   - 每 field 至少 1 测 happy path
   - 测输出 typed observation JSON schema：`{type, value, time, evidence_paths[]}`
   - 测**零 L1 schema 写**断言（运行前后 sample_journals/ 文件 hash 不变）
   - 测 evidence_paths 全可追溯到 sample_journals/ 文件
4. **Implement (GREEN)**：
   - 5 个 extractor（每 field 独立模块）
   - weight: 扫 frontmatter `weight_kg` + 正文 "体重: XX.X kg" 模式
   - sleep: 扫 frontmatter `sleep_hours` + 正文 "睡了 X 小时" / "凌晨 X 点睡" 模式
   - mood: 扫 frontmatter `mood` + 正文 emoji + 描述词
   - location: 扫 frontmatter `location` + 正文 "在 XX" 模式
   - project: 扫 frontmatter `project` + tag + 正文项目名
   - `core.py` 统一接口 + 时序聚合
   - `__main__.py` CLI 入口
5. **`LIFE_INDEX_DATA_DIR` 隔离**：实现必须支持 `LIFE_INDEX_DATA_DIR` env 切换数据目录（按 MEMORY: "Tests must not write to `~/Documents/Life-Index/`; use `tmp_path` or `LIFE_INDEX_DATA_DIR`"）
6. **CLI 注册**：`tools/__main__.py` 加 `trajectory` 子命令；schema_version 戳
7. **Docs**：`docs/API.md` 加 `trajectory` 命令；`CHANGELOG.md` 加条目；说明只读语义
8. **Self-check**
9. **PR**

## 红绿测试要求

- TDD 严格
- 必含"零 L1 schema 写"测试（fixture 文件 hash before/after 对比）
- 必含 evidence_paths 可追溯测试

## 验收标准

- `trajectory --field=weight --range=2025-01..2026-05` 工作
- 5 fields 全工作
- typed observation JSON schema 合规
- 零 L1 schema 写 PASS
- evidence_paths 全可追溯
- `test_trajectory_contract.py` PASS
- `test_layer_invariants.py` PASS（含 trajectory 不写 L1 schema 断言）
- 不污染 `~/Documents/Life-Index/`（用 `LIFE_INDEX_DATA_DIR` 或 `tmp_path`）
- `docs/API.md` 已更新
- `CHANGELOG.md` 已更新

## 自检 Checkbox

- [ ] 契约测试 PASS（5 fields × ≥ 1 case 各自）
- [ ] Layer invariant PASS
- [ ] **零 L1 schema 写测试 PASS**（fixture hash before == after）
- [ ] **evidence_paths 全可追溯**测试 PASS
- [ ] 测试不写真实数据目录（`LIFE_INDEX_DATA_DIR` 或 `tmp_path`）
- [ ] 输出 JSON schema 符合 `{type, value, time, evidence_paths[]}`
- [ ] 5 fields 各自 spot check（输出合理）
- [ ] 默认无 LLM
- [ ] `docs/API.md` 已更新
- [ ] `CHANGELOG.md` 已更新

## 下一 Task 指针

PR merged → 主控勾 Phase F → trajectory 模块作为 v1 可用，等 M4 集成。

## 执行总结（subagent 完成后填）

```
完成时间: <TBD>
实际 LOC: <TBD>
遇到的难点: <TBD>
验收证据:
  - test_trajectory_contract.py output: <snippet>
  - 5 fields 各自 sample output: <snippets>
  - zero-L1-write hash test: <before/after>
  - evidence_paths traceability test: <pass evidence>
```
