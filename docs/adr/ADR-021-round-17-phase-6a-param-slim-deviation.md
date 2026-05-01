# ADR-021: Round 17 Phase 6-A 参数瘦身目标偏离

> **状态**: 已接受
> **日期**: 2026-05-01
> **作者**: Sisyphus (GLM-5.1) / 审计补录: Kimi Code CLI

---

## 背景

PRD Task 7b 要求将 `search_constants.py` 对外暴露的"有语义"配置项从 34+ 降至 **≤15**。

Phase 6-A 执行后，实际状态为：
- `__all__` 导出 **43** 项（含 1 deprecated alias）
- 去重后有语义的独立配置：**42** 项
- 仅完成 **1** 个 exact-duplicate 合并（`SEMANTIC_ABSOLUTE_FLOOR` → alias for `SEMANTIC_MIN_SIMILARITY`）

## 偏离原因

1. **Gold Set A/B 数据不足**：参数合并的 plan 硬性要求"每个合并经 A/B 测试验证，metrics drift ≤ 2%"。Round 17 执行 Phase 6-A 时 Gold Set 仅 24 条（Phase 1-B 尚未完成），不足以支撑 A/B 的统计置信度。
2. **常量各司其职**：42 个常量中，大部分对应不同层级的不同语义（如 `FTS_MIN_RELEVANCE` vs `HIGH_FREQUENCY_MIN_RELEVANCE` 虽概念相近但阈值不同，服务于不同场景）。强行合并会降低可维护性。
3. **时间 box 约束**：Phase 6-A 预计 3-5 天，实际投入 <1 天（lint + 1 merge），剩余时间被 Phase 5 Orchestrator 和 Phase 6-B SLO 占用。

## 决策

接受偏离，目标延期至 **Round 18**。

Round 18 重新评估条件：
- Gold Set ≥ 150 条（提供足够 A/B 统计量）
- 语义管道 baseline 已测量（keyword-only baseline 无法区分"参数调整带来的改善"与"语义管道带来的改善"）
- 每次合并必须有 ≥100 条 query 的 A/B drift 报告

## 后果

- `search_constants.py` 继续以 42 项独立配置运行，维护成本略高于理想状态，但功能正确
- lint 脚本 `search_constants_lint.py` 已部署，防止新增裸阈值
- `test_total_exports_count` 断言 `len(__all__) <= 45`，作为上限护栏

## 替代方案（已排除）

- **强行合并至 ≤15**：风险过高，可能在无 A/B 数据的情况下破坏现有搜索行为
- **删除不常用常量**：会破坏 backward compatibility，且 plan 要求"合并后的旧名保留为 alias"
