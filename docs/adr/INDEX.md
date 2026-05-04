# ADR Index — Architecture Decision Records

> **最后更新**: 2026-05-04 (Round 19 Phase 1-D，新增 ADR-025)
> **分类标准**: 🔒 Invariant = 不变量级（不可违反，违反需走 CHARTER 修订流程）；📋 Decision = 决策级（可随参数调优而变化）

---

## 分类总表

| ADR # | 标题 | 分类 | 备注 |
|-------|------|------|------|
| ADR-001 | RRF k=60 Smoothing Constant | 📋 Decision | 内容在 `search_constants.py` 注释中；文件缺失 |
| ADR-002 | Semantic Threshold Floor (0.40) | 📋 Decision | 内容在 `search_constants.py` 注释中；文件缺失 |
| ADR-003 | FTS Min Relevance (25) | 📋 Decision | 内容在 `search_constants.py` 注释中；文件缺失 |
| ADR-004 | RRF Min Score (0.008) | 📋 Decision | A/B 实验选定；文件存在 |
| ADR-005 | Confidence Rules (D10) | 📋 Decision | 置信度分类规则；文件存在 |
| ADR-006 | Semantic Adaptive Threshold | 📋 Decision | 自适应阈值算法；文件存在 |
| ADR-007 | FTS Title Split (Raw + Segmented) | 📋 Decision | 标题列双存储；文件存在 |
| ADR-008 | Rejection Eval Gate | 🔒 Invariant | CI 硬阈值，不可绕过；文件存在 |
| ADR-009 | Chinese Stopword List | 📋 Decision | 分词停用词表；文件存在 |
| ADR-010 | RRF Semantic Weight Tuning (0.4→0.6) | 📋 Decision | 权重调优；文件存在 |
| ADR-011 | Title Hard Promotion (D12) | 📋 Decision | 标题加权乘数；文件存在 |
| ADR-012 | Entity Hint Ranking Bonus | 📋 Decision | 内容在 `search_constants.py` 注释中；文件缺失 |
| ADR-013 | High-Frequency Term Min Relevance | 📋 Decision | 内容在 `search_constants.py` 注释中；文件缺失 |
| ADR-014 | Score Dimension Normalization | 📋 Decision | 内容在 `search_constants.py` 注释中；文件缺失 |
| ADR-015 | Tukey IQR Fence for Dynamic Thresholds | 📋 Decision | 内容在 `search_constants.py` + `ranking.py` 注释中；文件缺失 |
| ADR-016 | Query Preprocessor | 📋 Decision | 确定性查询理解层；文件存在 |
| ADR-017 | Write-Through Pending Queue | 📋 Decision | 写入穿透缓存队列；文件存在 |
| ADR-021 | Round 17 Phase 6-A Param Slim Deviation | 📋 Decision | Round 17 deviation；文件存在；本表未及时回填 |
| ADR-022 | Round 17 Phase 5 Orchestrator MVP Deviation | 📋 Decision | Round 17 deviation；文件存在；本表未及时回填 |
| ADR-023 | Round 17 Baseline 5 Metrics Completion | 📋 Decision | Round 17 baseline；文件存在；本表未及时回填 |
| ADR-024 | Entity Schema v0 | 📋 Decision | Pilot 实体标注 schema 冻结；文件存在 |
| ADR-025 | Phase 1-D Baseline v3 → v4 Migration | 📋 Decision | Round 19 Phase 1-D baseline rebaseline；文件存在 |

> **注**：ADR-018/019/020 编号被预留但未使用；ADR-021~024 来自 Round 17/18，文件已落库但本 INDEX 表先前未及时回填，本次随 ADR-025 一并补登。

---

## 缺口状态

以下 ADR 文件缺失，但决策内容已记录在 `tools/lib/search_constants.py` 的常量注释中：

| ADR # | 缺失原因 | 内容位置 |
|-------|----------|----------|
| ADR-001 | 从未创建独立文件 | `search_constants.py` RRF_K 注释 |
| ADR-002 | 从未创建独立文件 | `search_constants.py` SEMANTIC_MIN_SIMILARITY 注释 |
| ADR-003 | 从未创建独立文件 | `search_constants.py` FTS_MIN_RELEVANCE 注释 |
| ADR-012 | 从未创建独立文件 | `search_constants.py` SCORE_ENTITY_BONUS 注释 |
| ADR-013 | 从未创建独立文件 | `search_constants.py` HIGH_FREQUENCY_MIN_RELEVANCE 注释 |
| ADR-014 | 从未创建独立文件 | `search_constants.py` 归一化注释 |
| ADR-015 | 从未创建独立文件 | `search_constants.py` + `ranking.py` Tukey 注释 |

**决策**：不补建缺失文件。`search_constants.py` 的注释已包含完整的 ADR rationale，补建文件属于形式主义，不增加实际信息量。

---

## Invariant 级条目与 CHARTER 对应

| ADR | Invariant 内容 | CHARTER 对应 |
|-----|---------------|-------------|
| ADR-008 | 搜索拒绝必须通过 eval gate 硬阈值 | CHARTER §4 "不得在没有 Gold Set 回归通过的情况下合入搜索相关 PR" |

其余 Invariant 级原则已直接写入 CHARTER §4 反模式黑名单（如"不得在 retrieval 层硬切 top-K"、"不得在底层调用 LLM"等），不属于任何特定 ADR。

---

## 统计

- **总计**: 22 条 ADR (ADR-001 ~ ADR-017, ADR-021 ~ ADR-025；ADR-018/019/020 编号未使用)
- **文件存在**: 15 条
- **文件缺失**: 7 条（内容在 search_constants.py 注释中）
- **🔒 Invariant**: 1 条 (ADR-008)
- **📋 Decision**: 21 条
