# ADR Index — Architecture Decision Records

> **最后更新**: 2026-05-24 (public/private documentation split; added ADR-027/028)
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
| ADR-024 | Entity Schema v0 | 📋 Decision | Pilot 实体标注 schema 冻结；文件存在 |
| ADR-026 | L1/L2 Future Compatibility Baseline | 📋 Decision | 终局高级模块的 L1/L2 地基兼容性基线；文件存在；CHARTER 修订待 RFC/cooldown |
| ADR-027 | Write Journal LLM Extract Migration | 📋 Decision | LLM extraction moved out of default write path；文件存在 |
| ADR-028 | L2 Retrieval Default = Pure Keyword | 🔒 Invariant | Recall-first truthfulness model；CHARTER §1.11；文件存在 |

> **注**：ADR-018/019/020 编号被预留但未使用；ADR-021/022/023/025 为 round-specific deviation / audit / baseline process records，已移至私有本地治理归档，不再属于公开 ADR surface。

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
| ADR-028 | L2 默认检索必须保持 keyword-first / recall-first；semantic/hybrid 为显式或 fallback 路径 | CHARTER §1.11 Recall-First Retrieval Truthfulness Model |

其余 Invariant 级原则已直接写入 CHARTER §4 反模式黑名单（如"不得在 retrieval 层硬切 top-K"、"不得在底层调用 LLM"等），不属于任何特定 ADR。

---

## 统计

- **总计**: 21 条公开 ADR (ADR-001 ~ ADR-017, ADR-024, ADR-026 ~ ADR-028；ADR-018/019/020 编号未使用；ADR-021/022/023/025 已私有归档)
- **文件存在**: 14 条
- **文件缺失**: 7 条（内容在 search_constants.py 注释中）
- **🔒 Invariant**: 2 条 (ADR-008, ADR-028)
- **📋 Decision**: 19 条
