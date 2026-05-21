# Phase Sequence — gbrain absorption

> **PRD**: `docs/projects/gbrain-absorption/PRD.md`
> **M1 ack #1**: 2026-05-21（commit `03eaf12`）
> **M2 created**: 2026-05-21
> **状态**: M3 准备中（等主控 Agent dispatch subagent）

## 依赖图

```
Wave 1（4 并行）          Wave 2（依赖 Wave 1）
─────────────────         ─────────────────
gbrain-A (#1 eval)  ──┐
                       ├──> gbrain-B (#2 source-tier, after A)
gbrain-C (#3 edges)──┤
                       ├──> gbrain-D (#4 maintenance, after A+C)
gbrain-E (#5 + recall) ──── 独立
gbrain-F (#6 + trajectory) 独立
```

## Phase 状态总览

| Phase | gbrain # | Worktree | Branch | TDD Brief | Wave | Status | Subagent | PR |
|---|---|---|---|---|---|---|---|---|
| A | #1 Graph ablation eval | `.claude/worktrees/gbrain-A` | `claude/gbrain-A` | `Phase-A-TDD.md` | 1 | [ ] not started | TBD | TBD |
| B | #2 Source-tier boost | `.claude/worktrees/gbrain-B` | `claude/gbrain-B` | `Phase-B-TDD.md` | 2 (after A) | [ ] blocked by A | TBD | TBD |
| C | #3 Candidate edges 报告 | `.claude/worktrees/gbrain-C` | `claude/gbrain-C` | `Phase-C-TDD.md` | 1 | [x] accepted | `码农C_DeepSeek` | local commit `366cac4` |
| D | #4 Maintenance cycle | `.claude/worktrees/gbrain-D` | `claude/gbrain-D` | `Phase-D-TDD.md` | 2 (after A+C) | [ ] blocked by A+C | TBD | TBD |
| E | #5 Search modes + recall | `.claude/worktrees/gbrain-E` | `claude/gbrain-E` | `Phase-E-TDD.md` | 1 | [ ] not started | TBD | TBD |
| F | #6 Facts/trajectory + trajectory module | `.claude/worktrees/gbrain-F` | `claude/gbrain-F` | `Phase-F-TDD.md` | 1 | [ ] not started | TBD | TBD |

## 主控 Agent 动作（M3 并行线 1）

1. **Wave 1 dispatch**：A / C / E / F 同时派给 4 个 subagent，各自在自己 worktree 工作
2. **Wave 1 验收**：subagent PR 完成 → 主控 review (code review + 跑 contract test + 跑 layer invariant) → reject 或 merge → 勾本表 checkbox
3. **Wave 2 dispatch**：A merged → 派 B；A+C merged → 派 D
4. **Wave 2 验收**：同 Wave 1
5. **全部 ✅ → 进 M4**：跨 Phase 接口对齐 + 合并冲突 + 集成测试 + 主理人 ack #2

## 主理人介入点

- M1 ack #1：✅ 已完成（2026-05-21）
- M2 / M3：**不介入**（按 PROJECT_WORKFLOW）
- M3 escalate：若 subagent 发现 PRD 漏写 / scope 扩张 / worktree 边界不够 → 回 M1 重 ack #1
- M4 ack #2：6 phase 全 ✅ + 集成测试通过后

## Merge 顺序规则

- Wave 1 之间无强制顺序，但 **A 应优先 merge**（B/D 依赖 A）
- 多 phase 同时改 `docs/API.md` / `CHANGELOG.md` `[Unreleased]` / `tests/contract/test_layer_invariants.py` → 后 merge 的 phase 必须 rebase
- 单 PR 自包含（不跨 phase 提交）

## 工作树文件域（防 merge 冲突）

| Phase | 主写域 | 共享文件（rebase 解决）|
|---|---|---|
| A | `tools/eval/ablation/` + `tests/contract/test_ablation_eval_contract.py` + `tests/fixtures/eval/ablation_queries.json` | `docs/API.md`, `CHANGELOG.md` |
| B | `tools/search_journals/ranking.py` + `tools/search_journals/search_constants.py` + `tests/contract/test_source_tier_contract.py` | `docs/API.md`, `CHANGELOG.md`, `.strategy/cli/2026-05-2X-source-tier-eval-result.md`（新建）|
| C | `tools/entity/__main__.py`（加 flag）+ `tools/entity/candidate_edges.py` + `tests/contract/test_candidate_edges_contract.py` | `docs/API.md`, `CHANGELOG.md` |
| D | `tools/maintenance/` + `tests/contract/test_maintenance_contract.py` | `docs/API.md`, `CHANGELOG.md`, `tools/__main__.py`（加 maintenance 注册）|
| E | `tools/recall/` + `tests/contract/test_recall_contract.py` | `docs/API.md`, `CHANGELOG.md`, `tools/__main__.py`（加 recall 注册）|
| F | `tools/trajectory/` + `tests/contract/test_trajectory_contract.py` | `docs/API.md`, `CHANGELOG.md`, `tools/__main__.py`（加 trajectory 注册）|

## 跨 Phase 共享 invariant 测试扩展

`tests/contract/test_layer_invariants.py` 需扩展以验：

- 6 个新 surface（entity-graph-eval, search 加 tier, entity --candidate-edges, maintenance, recall, trajectory）的 default 路径**无 LLM import**
- recall `--mode=deep` 不带 `--use-llm` 时降级到 recall（无 LLM 调用）
- trajectory 不写 L1 schema（断言）

由**第一个 merge 的 phase** 完成扩展（推荐 A）；后续 phase rebase 时复用。
