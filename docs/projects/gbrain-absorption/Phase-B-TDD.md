# Phase B TDD Brief — Source-tier boost (#2)

> **Phase**: B | **gbrain Candidate**: #2
> **Worktree**: `.claude/worktrees/gbrain-B/`
> **Branch**: `claude/gbrain-B`
> **Wave**: 2 (**blocked by Phase A**)
> **PRD**: `docs/projects/gbrain-absorption/PRD.md` §5 Phase B

## 派发纪律 3 门（PRD §5 引用）

- **可证伪退出**: `search` 启用 tier weights（参数在 `search_constants.py`）；`test_source_tier_contract.py` 通过；Phase A eval 跑后 `tier=on` vs `tier=off` 的 P@5 delta 写入 `.strategy/cli/2026-05-2X-source-tier-eval-result.md`（数值不强制为正，但必须 documented）
- **真实消费者**: Phase A eval（即时验证）+ future modules（memoir / evidence pack 等）
- **有界自主**:
  - 可写：`tools/search_journals/ranking.py`, `tools/search_journals/search_constants.py`, `tests/contract/test_source_tier_contract.py`, `.strategy/cli/2026-05-2X-source-tier-eval-result.md`
  - 可读：`tools/eval/ablation/`（Phase A 产物）, `tools/search_journals/` 其余文件
  - **不动**：smart-search planner, entity 命令, L1 数据格式

## 依赖前置

- Phase A 必须先 merged 到 main（提供 `entity-graph-eval` 可调）
- subagent 派发时验证：`git log origin/main --grep="Phase A"` 应见 merge commit；`python -m tools.eval.ablation --help` 应可跑

## Task 清单

1. **Pull rebase**：`git pull --rebase origin main` 确保拿到 Phase A 产物
2. **Source tier 定义**：在 `search_constants.py` 加 `SOURCE_TIER_WEIGHTS = {...}` (frontmatter/title hit, monthly index, generated report, attachment OCR 等分层)
3. **Test (RED)**：`tests/contract/test_source_tier_contract.py`：
   - 测 `search` 命令默认行为（tier disabled）不变
   - 测 `search --enable-source-tier` 启用 tier weights
   - 测特定 query 在 tier 启用下 expected doc 排序提升
4. **Implement (GREEN)**：
   - `ranking.py` 加 tier-aware re-ranking function
   - `search_journals/__main__.py` 加 `--enable-source-tier` flag（默认 false 保兼容）
5. **Eval (Phase A 集成)**：跑 `python -m tools.eval.ablation --queries=tests/fixtures/eval/ablation_queries.json --tier-toggle` 产出 tier on/off 对比
6. **Eval 结果归档**：写 `.strategy/cli/2026-05-2X-source-tier-eval-result.md`，含：
   - tier off baseline P@5/R@5/MRR@5
   - tier on P@5/R@5/MRR@5
   - delta 分析
   - 结论：是否推荐 default enable（视 delta 决定）
7. **Docs**：`docs/API.md` 加 `--enable-source-tier` flag 说明；`CHANGELOG.md` `[Unreleased]` 加条目
8. **Self-check**：跑全 checklist
9. **PR**

## 红绿测试要求

- TDD 严格：Step 3 RED → Step 4 GREEN
- PR 含 red→green 证据

## 验收标准

- `test_source_tier_contract.py` PASS
- `test_layer_invariants.py` PASS（应已被 Phase A 扩展含 tier-aware ranking 不引入 LLM）
- Gold Set 回归 ≥ 基线（即使 tier disabled 也不应回归）
- `.strategy/cli/2026-05-2X-source-tier-eval-result.md` 含数值 + delta
- Phase A `entity-graph-eval` 跑后 tier=on/off 对比可见
- `docs/API.md` 已更新
- `CHANGELOG.md` 已更新

## 自检 Checkbox

- [ ] 契约测试 PASS
- [ ] Layer invariant PASS
- [ ] Gold Set 回归 PASS（tier disabled 默认行为不变）
- [ ] `search --enable-source-tier` 工作
- [ ] tier on/off P@5 delta 数值已 documented in `.strategy/cli/...md`
- [ ] 默认路径（不带 `--enable-source-tier`）行为完全不变 — bit-exact regression test
- [ ] `docs/API.md` 已更新
- [ ] `CHANGELOG.md` 已更新
- [ ] PR 描述含 red→green + eval delta 数值

## 下一 Task 指针

PR merged → 主控勾 Phase B → Phase D 解锁（若 Phase C 也已 merged）。

## 执行总结（subagent 完成后填）

```
完成时间: <TBD>
实际 LOC: <TBD>
遇到的难点: <TBD>
验收证据:
  - test_source_tier_contract.py output: <snippet>
  - tier on/off P@5 delta: <numbers>
  - Gold Set: <baseline vs current>
  - eval result file: .strategy/cli/2026-05-2X-source-tier-eval-result.md
```
