# ADR-023: Round 17 Baseline 5 指标补全

> **状态**: 已接受
> **日期**: 2026-05-01
> **作者**: Kimi Code CLI（审计修补）

---

## 背景

Round 17 closure 文档（`phase-7-closure.md`）声称 IR baseline 已锁定，输出指标为：
- MRR@5 = 0.2716
- Recall@5 = 0.3836
- Precision@5 = 0.3565

Round 17 执行审计（`round-17-execution-audit.md`，归档于 `.strategy/cli/archive/round-17/`）发现：
1. `run_eval.py` 的 `_collect_metrics()` 函数**未计算 Recall@10**
2. `run_eval.py` 的 keyword judge 模式下**未计算 NDCG@5**
3. `tests/eval/baselines/round-17-baseline.json` 的 `metrics` 块中，`recall_at_10` 与 `ndcg_at_5` **字段完全缺失**（不是 `null`，是 key 不存在）
4. PRD Task 2 明确要求输出 **P@5 / Recall@10 / NDCG@5 / MRR** 四个指标，实际只达成 2/4

这意味着 Round 17 锁定的 baseline 是**不完整的**——它被标记为 PASS，但缺少 PRD 硬指标要求的两项。

## 决策

**重写 Round 17 已锁定的 baseline JSON**，补全 Recall@10 与 NDCG@5。

这不是"修改历史数字"，而是"补全原本就应该存在但未计算的指标"。Baseline 的底层数据（85 条 query 的搜索结果）没有变化，变化的只是 eval 脚本的指标计算逻辑。

## 修补内容

| 修补项 | 文件 | 说明 |
|---|---|---|
| Recall@10 计算 | `tools/eval/run_eval.py` | `_evaluate_queries()` 新增 `top_results_10` 与 `first_relevant_rank_at_10`；`_collect_metrics()` / `_collect_llm_metrics()` 新增 `recall_at_10` |
| NDCG@5 keyword 模式 | `tools/eval/run_eval.py` | keyword judge 分支新增 `keyword_relevance_scores`（binary 0/1），复用 `_compute_ndcg_at_5()` |
| TDD RED 测试 | `tests/eval/test_gold_set_integrity.py` | 新建，5 项测试（plan §3.1 强制要求，原始执行中被跳过） |
| Baseline 重写 | `tests/eval/baselines/round-17-baseline.json` | 重新生成，含完整 5 指标 |

## 修补后指标

```json
{
  "mrr_at_5": 0.2716,
  "recall_at_5": 0.3836,
  "recall_at_10": 0.3973,
  "precision_at_5": 0.3565,
  "ndcg_at_5": 0.2877
}
```

**关键发现**：Recall@10（0.3973）仅比 Recall@5（0.3836）高 1.37pp。这说明当前搜索系统的核心问题不是"相关结果排得太靠后"，而是"根本找不到相关结果"——直接指导 Round 18 的优化策略（见 Round 18 PRD §1.3）。

## 合规性说明

- **为何重写已锁定的 baseline？** Round 17 closure 声称 baseline 已锁定，但审计发现该 baseline 不满足 PRD Task 2 的硬指标要求（缺少 Recall@10/NDCG@5）。重写不是"改数字"，而是"补全原本就应该存在的计算"。
- **底层数据是否变化？** 否。85 条 query 的搜索结果与 Round 17 完全一致，变化的是 eval 脚本从结果中抽取指标的方式。
- **是否影响 Round 17 的 closure 有效性？** 是。Round 17 closure M3 的"IR baseline 已锁定"声明在审计后被修正为"IR baseline 已补齐"。closure 文档（`.strategy/cli/round-17-plan/phase-7-closure.md`，本地-only）已同步更新。

## 关联文档

- 审计报告：`.strategy/cli/archive/round-17/round-17-execution-audit.md` §3.2, §5.1
- Round 18 PRD：`.strategy/cli/round-18-prd.md` §1.1
- Commit: `f6c9cc7`

## 后果

- Round 17 baseline 现在是完整的 5 指标版本，可作为 Round 18 的起跳数据
- Round 18 不再需要为"缺少 Recall@10 测量能力"而额外投入工程时间
- 建立了先例：已锁定的 baseline 若被审计发现指标不完整，允许通过 ADR 补全而非静默修改
