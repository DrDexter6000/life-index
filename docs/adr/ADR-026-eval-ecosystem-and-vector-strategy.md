# ADR-026: Eval 生态集成、向量检索策略与 RAG/LLM 架构边界

> **状态**: 已决（Decided）
> **决策日期**: 2026-05-04
> **来源**: Round 19 Phase 1-D 中途架构审视——用户要求从更高维度审视"是否在重复造轮子"
> **决策者**: Sisyphus（deepseek-v4-pro）提案，用户 ack
> **影响范围**: eval 工具链、向量检索未来演进、L2/L3 架构边界重申
> **触发条件**: 用户要求全局审视搜索/索引体系的工程合理性

---

## 1. 决策上下文

### 1.1 起源

Round 19 Phase 1-D 推进中，用户跳出任务层面，从架构高度重新审视：

> 「我们在搜索/索引上花了大量功夫，是否本质上在做别人已经做过的事？市面上已有满足 Life Index CLI 特殊需求的成熟解决方案？」

由此触发了一场跨四维度的全景评估：

1. **内部架构测绘**：梳理 Life Index 搜索/索引管线（FTS5 + bge-m3 向量 + RRF 融合 + 噪声闸 + 查询预处理 + eval 体系）
2. **竞品对比**：扫描 ~25 个本地搜索方案（Whoosh/Xapian/Tantivy/ChromaDB/LanceDB/Qdrant/Meilisearch/litesearch 等）
3. **PKM 对标**：分析 Obsidian/Logseq/SiYuan/Joplin 等工具的搜索架构
4. **Eval 专业化**：评估 `ranx` 替代自研 eval 代码的可行性
5. **向量检索远期**：评估 HNSW/ANN 在当前和 50 年视角下的必要性

### 1.2 全景评估核心发现

**总体判定**：Life Index 的搜索体系**不是重复造轮子**。核心技术 (SQLite FTS5、jieba 分词、bge-m3 嵌入、RRF 融合) 均为成熟组件；自研的调度系统 (Query Preprocessor、Noise Gate、Entity Expansion、Eval Framework) 处理的是**与具体数据耦合的定制问题**，无通用库可替代。

**唯一发现的"可外包"组件**：eval 指标计算 (MRR/Recall/Precision/nDCG) → `ranx` 库可替代 ~800 行自研代码，同时提供统计检验、多 run 对比、融合优化等新能力。

**关于 HNSW**：当前 N < 500，暴力搜索 (< 40ms) 完全够用。N 增长到 2,000-5,000 大约需要 3-5 年，在此之前不需要 ANN 索引。

**关于 RAG/LLM**：当前 L2 (确定性) + L3 (LLM 编排) 的架构分界符合 CHARTER §1.5，不需要因规模增长而改变。

---

## 2. 决策 1: ranx 采纳（✅ 采纳，Phase 1-D 关闭后执行）

### 2.1 决策内容

用 `ranx` 库替代 `tools/eval/run_eval.py` 中的自研 metric 计算代码 (~800 行)，保留 Life Index 独有的 golden query 解析、LLM judge、phase skip、regression 检测逻辑。

### 2.2 时机与执行顺序

**不在 Phase 1-D 内执行。** Phase 1-D 的 v4 baseline (MRR@5=0.5559, Recall@5=0.7957) 是用自研 eval 生成的，中途换测量工具会破坏可比性。ranx 整合为 Phase 1-D 关闭后的独立 task。

执行顺序：
1. Phase 1-D close（governance push）
2. 独立 task: ranx 整合
   - a) `pip install ranx`
   - b) 写 `yaml_to_ranx_qrels()` 和 `search_results_to_ranx_run()` 桥接函数
   - c) 对 v4 baseline 双跑对照（自研 vs ranx），确认数字差异在 ±0.003 以内
   - d) 替换 `_collect_metrics()` 为 `ranx.evaluate()`
   - e) 冻结新 baseline (v5, 标注 "ranx-calibrated")
   - f) 可选：用 `ranx.compare()` + Tukey HSD 替换当前自研 regression 检测
3. Round 20 启动时，eval 已迁移到 ranx

### 2.3 约束

- **数字对照验证必须在切换前完成。** 如果自研 vs ranx 的 MRR 差异 > 0.005，必须先追因（大概率是 nDCG 公式微差）。
- **保留自研 eval 代码直到对照验证通过。** 不删除旧代码来通过测试。
- **ranx 的 numba 依赖 (~200MB) 是接受的风险。** 作为 dev/CI 依赖，不影响用户运行时。

### 2.4 理性

- ranx 通过了 TREC Eval 对标验证，比自研公式更可信
- 提供统计检验（Student's t、Fisher、Tukey HSD）→ 搜索改进是否显著的判断从"感觉"变成"科学"
- 提供多 run 对比（`compare()`）→ A/B 实验不再靠目测
- 提供 RRF 融合优化（`optimize_fusion()`）→ 未来数据量增长后可自动重新标定 k 值
- MIT 许可证，兼容 Apache 2.0
- 依赖重量在可接受范围（numba ~200MB, pip install ranx）

---

## 3. 决策 2: HNSW 推迟（⏸️ 推迟，N > 2,000 时评估）

### 3.1 决策内容

当前（N ~100-500）保持 sqlite-vec 暴力搜索（O(N), < 40ms），不引入 ANN 索引。当 N 接近 2,000 时，评估以下路径：

- **路径 A**（优先）：若 sqlite-vec 已发布 ANN 稳定版（IVF/DiskANN），直接在 vec0 表加 `INDEXED BY` 子句，零新依赖
- **路径 B**（备选）：若 sqlite-vec 仍未发布，引入 `usearch` (<1MB，Apache 2.0，3 行代码集成)，作为旁路索引与 sqlite-vec 暴力搜索并存

### 3.2 缓冲期分析

| N | 暴力搜索延迟 | 感受 | 时间线（假设 1 篇/天） |
|:---:|:---:|:---|:---|
| 100（现在）| 3-8 ms | 无感 | — |
| 500 | 15-40 ms | 基本无感 | ~1 年 |
| 2,000 | 60-160 ms | 能感觉到 | ~5 年 |
| 5,000 | 150-400 ms | 明显等待 | ~13 年 |
| 10,000 | 300-800 ms | 不可接受 | ~27 年 |

拐点大约在 2,000-5,000 篇，缓冲期充裕（3-5+ 年）。过早引入 ANN 会增加代码复杂度而当下零收益。

### 3.3 CHARTER §1.8 长期主义分析

- **当下做 ANN**：~2-4 小时开发 + 引入新依赖 + 持续维护
- **半年后反转**：usearch 索引可随时丢弃重建，反转成本低
- **当下不做 ANN**：零成本，缓冲期 3-5+ 年
- **结论**：当下不做是长期主义正解。付出代价的时机是"刚好在需要之前"，不是"越早越好"。

### 3.4 触发条件

在 `semantic_search.py` 或 `index_manifest.py` 中记录以下提醒（非报警，仅注释）：

```
# ANN checkpoint: when N > 2000, evaluate sqlite-vec ANN maturity.
#   Path A: if sqlite-vec ANN (IVF/DiskANN) stable → add INDEXED BY
#   Path B: if not ready → pip install usearch, ~50 lines integration
# See ADR-026.
```

---

## 4. 决策 3: RAG/LLM 架构边界（✅ 维持现状，由 CHARTER §1.5 锁定）

### 4.1 决策内容

L2 (CLI Core) 保持零 LLM 调用，L3 (Intelligence Layer) 继续承担 LLM 编排职责。不因用户"Agent 自带 LLM 能力"而将 LLM 引入 L2 搜索管道。

### 4.2 架构理由（重申）

| 维度 | L2 确定性搜索 | LLM 全量 RAG |
|------|:---:|:---:|
| 可复现性 | ✅ eval 可精确回归 | ❌ temperature 引入随机性 |
| 离线可用性 | ✅ 始终可用 | ❌ 依赖网络/GPU |
| GUI 直连延迟 | < 50ms | 500ms-5s |
| 规模适应性 | FTS5 + 向量，O(log N) | 需要全量扔进 context，不可行 |

L3 的 smart-search orchestrator **已经在用 Agent 的 LLM 能力**——查询改写、结果精筛、摘要生成。L2 不需要 LLM 不是因为"不喜欢 LLM"，而是因为 L2 需要确定性和低延迟。

### 4.3 未来演进空间

如果未来有足够小、足够快的本地 LLM（如 Llama-3.2-1B 量化版，<1GB，CPU <200ms），可引入 L3 做 rerank。**关键约束：放在 L3 而非 L2。**

---

## 5. 后果与影响

### 5.1 需更新的文档/Artifact

| Artifact | 更新 | 时机 |
|----------|------|------|
| `docs/adr/ADR-026-*.md`（本文件）| 新增 | 立即 |
| `docs/adr/INDEX.md` | 新增 ADR-026 条目 | 立即 |
| `tools/eval/run_eval.py` | ranx 整合 (~-800 行, +~50 行桥接) | Phase 1-D 关闭后 |
| `pyproject.toml` | 添加 `ranx` 依赖 | Phase 1-D 关闭后 |
| `tools/search_journals/semantic_search.py` | 添加 HNSW checkpoint 注释 | 可随时（不阻塞）|
| CHARTER.md | 无需修改（§1.5 已覆盖决策 3） | — |

### 5.2 不做的清单

- ❌ 不替换 L2 搜索管道为 LLM/RAG 框架
- ❌ 不引入 ChromaDB/LanceDB 等重量级向量数据库
- ❌ 不迁移到 Meilisearch/Typesense 等客户端-服务器架构
- ❌ 不在 Phase 1-D 内整合 ranx（会破坏 baseline 可比性）
- ❌ 不在当前规模 (N < 2,000) 引入 ANN 索引

---

## 6. 替代方案（已评估并拒绝）

| 替代方案 | 拒绝理由 |
|----------|----------|
| 用 LlamaIndex/LangChain 替换搜索管道 | 过度工程化（~100MB 依赖 + 秒级延迟），违反 CHARTER §1.7 "宁可功能简单" |
| 用 Meilisearch 做搜索后端 | 客户端-服务器架构，违反 CHARTER §1.1 数据主权和进程最小化原则 |
| 用 ChromaDB 替换向量搜索 | 只为向量搜索引入整个数据库（~50MB），过度工程化 |
| 自研 HNSW 实现 | 造真正的轮子，现有社区方案（usearch）API 简洁、实战验证 |
| 继续自研 eval，不加 ranx | 失去统计检验、多 run 对比、融合优化等能力；自研代码维护成本（~800 行）高于 ranx 桥接（~50 行）|
| Phase 1-D 内整合 ranx | 破坏 v4 baseline 可比性，影响 Phase 1-D exit criteria 审计追溯 |

---

## 7. 相关文档

| 文档 | 关系 |
|------|------|
| CHARTER.md §1.5 | 确定性 vs 智能硬线（决策 3 的宪章基础） |
| CHARTER.md §1.8 | 长期主义原则（决策 2 的推迟依据） |
| CHARTER.md §4.5 | 搜索性能 SLO（HNSW 延迟分析的上限参照） |
| `docs/ARCHITECTURE.md` §2 | 双管道并行检索架构 |
| `tools/lib/search_constants.py` | 搜索参数 SSOT（ADR-001~015 记录于此） |
| `.strategy/cli/round-19-phase1d-plan.md` | Phase 1-D 当前执行计划 |
| ranx 官方文档 | https://amenra.github.io/ranx |
| usearch 官方仓库 | https://github.com/unum-cloud/usearch |
| sqlite-vec ANN 路线图 | https://github.com/asg017/sqlite-vec/issues/25 |

---

> 本 ADR 覆盖三个维度的架构决策：工具链 (ranx)、远期性能 (HNSW)、架构边界 (RAG/LLM)。决策间独立，撤销成本均可控。
>
> 下次评审点：Phase 1-D 关闭，ranx 整合独立 task 启动时。
