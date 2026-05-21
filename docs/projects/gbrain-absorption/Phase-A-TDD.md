# Phase A TDD Brief — Graph ablation eval (#1)

> **Phase**: A | **gbrain Candidate**: #1
> **Worktree**: `.claude/worktrees/gbrain-A/`
> **Branch**: `claude/gbrain-A`
> **Wave**: 1 (independent)
> **PRD**: `docs/projects/gbrain-absorption/PRD.md` §5 Phase A

## 派发纪律 3 门（PRD §5 引用）

- **可证伪退出**: `python -m tools.eval.ablation --queries=tests/fixtures/eval/ablation_queries.json --output=stdout` 输出 JSON，含 `entity_graph={true,false}` × `semantic={true,false}` × `hybrid={true,false}` 8 种组合的 P@5/R@5/MRR@5；契约测试通过
- **真实消费者**: Phase B (#2 source-tier 验证) + Phase D (#4 maintenance smoke 调用)
- **有界自主**:
  - 可写：`tools/eval/ablation/`, `tests/contract/test_ablation_eval_contract.py`, `tests/fixtures/eval/ablation_queries.json`
  - 可读：`tools/search_journals/`, `tools/entity/`, `tools/lib/`
  - **不动**：L2 search / smart-search 源码、Entity Graph 写入逻辑

## Task 清单（顺序执行）

1. **Scaffold**：
   - `tools/eval/ablation/__init__.py`
   - `tools/eval/ablation/__main__.py`（CLI 入口）
   - `tools/eval/ablation/core.py`（runner）
   - `tools/eval/ablation/metrics.py`（P@5 / R@5 / MRR@5 计算）
2. **Fixture**：
   - `tests/fixtures/eval/ablation_queries.json` 至少 20 query，每条带 expected relevant doc ids (从既有 gold set 选)
3. **Test (RED)**：
   - `tests/contract/test_ablation_eval_contract.py` 先写测试让其 fail：
     - 测 CLI 入口能跑
     - 测输出 JSON 含 8 组合 entries
     - 测每 entry 含 `entity_graph`/`semantic`/`hybrid` 标志位 + P@5/R@5/MRR@5
4. **Implement (GREEN)**：
   - core.py 实现 8 组合 runner（通过 subprocess 调 `search` / `smart-search` with 不同 flag）
   - metrics.py 实现指标计算
   - __main__.py 串起来 + 输出 JSON
5. **CLI 注册**：`tools/__main__.py` 加 `entity-graph-eval` 子命令（如果走 top-level）；或直接 `python -m tools.eval.ablation` 入口
6. **Layer invariant 扩展**（本 phase 是 wave 1 第一波，可负责扩展）：
   - `tests/contract/test_layer_invariants.py` 加断言：`tools/eval/ablation/` 默认路径无 `anthropic`/`openai`/`llm_client` import
7. **Docs**：
   - `docs/API.md` 加 `entity-graph-eval` 命令文档 + schema_version
   - `CHANGELOG.md` `[Unreleased]` 加 user-facing 条目
8. **Self-check**：跑下面 self-check checklist 全过
9. **PR**：开 PR 回 main，描述含完成定义验证证据 + 自检 checkbox 状态

## 红绿测试要求

- TDD 严格：Step 3 先写测试，跑后必须看到 FAIL（RED）。Step 4 实现后跑必须 GREEN
- 不允许 implement-first 跳过 red phase
- PR description 必须含 red→green 证据（两次 pytest 输出 snippet）

## 验收标准

- `python -m tools.eval.ablation --queries=tests/fixtures/eval/ablation_queries.json` 输出 JSON
- JSON 含 8 个组合 entries，每个有完整 P@5 / R@5 / MRR@5 数值
- `test_ablation_eval_contract.py` 全过
- `test_layer_invariants.py` 全过（含扩展断言）
- Gold Set 回归测试 ≥ 基线
- `docs/API.md` 已更新
- `CHANGELOG.md` `[Unreleased]` 已更新

## 自检 Checkbox（subagent 自检，PR 前必须全勾）

- [ ] 契约测试 `test_ablation_eval_contract.py` PASS
- [ ] Layer invariant `test_layer_invariants.py` PASS（含扩展断言）
- [ ] Gold Set 回归 PASS
- [ ] `entity-graph-eval --help` 工作
- [ ] 输出 JSON 含 8 组合 × P@5/R@5/MRR@5
- [ ] 默认路径无 LLM import（grep 验证）
- [ ] `docs/API.md` 含本 phase surface
- [ ] `CHANGELOG.md` `[Unreleased]` 含本 phase 条目
- [ ] PR 描述含 red→green 测试输出证据
- [ ] worktree 干净（无未提交改动外的 staged）

## 下一 Task 指针

PR merged → 主控 Agent 在 `Phase-Sequence.md` 勾 Phase A checkbox → 解锁 Phase B dispatch。

## 执行总结（subagent 完成后填）

```
完成时间: <TBD>
实际 LOC: <TBD>
遇到的难点: <TBD>
验收证据:
  - test_ablation_eval_contract.py output: <snippet>
  - sample ablation JSON output: <snippet>
  - Gold Set regression: <baseline vs current>
```
