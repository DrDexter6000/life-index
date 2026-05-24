# RFC-2026-05-23: L2 Recall-First Retrieval Truthfulness Model

> **Status**: Pending主理人 Ack
> **Author**: CTO (Claude)
> **Date**: 2026-05-23
> **CHARTER impact**: v1.5.0 → v1.6.0 (新增 §1.11，修订次数 5 → 6)
> **§5.2 substantive gate**: 4 项齐备见 §1 / §4 / §5 / §7
> **Related**: ADR-028 (架构决策), `tests/eval/baselines/round-18-semantic-baseline.json` (历史 evidence), `.agent-reports/v120-search-fusion-m3/phase-a/A6_baseline_result.json` (v1.2.0 cycle2 baseline)

---

## §1 Rationale — 为什么要改

### 1.1 问题陈述

Life Index 在 README.en.md line 295 对用户作出灵魂级承诺：

> "...can recover **key memory fragments** from decades of growing personal journals while remaining **fully offline, deterministic, and zero-token**."

中文版口语化为 **"不遗漏您每一个人生碎片"**。

这是一个 **recall-first 信号** —— 漏比假阳更糟，因为用户不知道自己漏了什么。

但当前 CHARTER 中**没有任何条款** enshrine 这个产品承诺。它只活在 README 的口语里。

后果：架构层做"产品默认行为"决策时缺乏宪法约束。具体表现为：

1. `tools/search_journals/core.py:1026` 设置 production default = "hybrid" (keyword + semantic + RRF)，**recall 与 precision 同时打折**
2. `tools/eval/__main__.py:38-40` 设置 eval gate default = keyword-only，**与 production 不一致**
3. CHARTER §1.5 把"向量搜索"列入"确定性允许"列，**没有禁止它在 L2 主路径，但也没强制它必须在**
4. 没有任何文档明示 "L2 retrieval 的承诺是什么"

历史 2026-05-05 注释（CHARTER §4 末尾）显示 Round 19 Phase 1-D hybrid mode 实测 **R@5=0.8387, P@5=0.4894** —— **近半数返回结果是噪音**。这与 "不遗漏" 承诺在表面上一致（recall 较高），但暗中违背了"用户能信任搜索结果"的隐性承诺（precision 太低导致心智污染）。

### 1.2 触发条件归档（对应 §5.1）

- ✅ **真实场景反效果**：v1.2.0 cycle2 baseline 在 keyword-only mode 跑出 R@5=0.6786, C2 paraphrase R@5=0.14 (灾难)。CTO 起初误读为 "C2 paraphrase 不可解" 并差点 design 错 PRD scope。后 surface 是 eval gate keyword-only + production hybrid 的 mode mismatch。问题根源 = **truthfulness model 未定调**。
- ✅ **完成里程碑后的有意识演进**：v1.1.1 ship 完成、v1.2.0 absorption 接近 PRD 阶段，正是 enshrine 产品承诺的最佳窗口。

### 1.3 目标

在 CHARTER §1（不变量）中新增 **§1.11 Recall-First Retrieval Truthfulness Model**，把"不遗漏每一个人生碎片"从口语承诺升格为 50 年宪法不变量。

---

## §2 当前条款 vs 目标条款

### 2.1 当前条款（v1.5.0）

CHARTER §1.5 (确定性与智能的边界) 表格中：

| 操作类型         | 必须确定性     | 允许 LLM |
| ------------ | --------- | ------ |
| 关键词搜索（FTS5）  | ✅         | ❌      |
| 向量搜索（嵌入模型推理） | ✅ 推理结果可预期 | —      |
| RRF 融合、排序    | ✅         | ❌      |

**含义**：keyword 和 vector 都允许在 L2，但没规定哪个是 default、哪个是承诺主路径。

CHARTER 附录 A 把"双管道"定义为 "FTS5 关键词管道 + 向量语义管道并行 + RRF 融合" —— 这是术语 definition，**不强制 default behavior**。

CHARTER **无任何条款** 涉及 "L2 retrieval 的产品承诺是 recall-first 还是 precision-first"。

### 2.2 目标条款（v1.6.0 新增 §1.11）

```markdown
### §1.11 召回优先检索真实模型（Recall-First Retrieval Truthfulness Model）

Life Index L2 检索层对用户的承诺是 **"不遗漏您每一个人生碎片"**。
这要求 L2 默认行为必须是 **recall-first 而非 precision-first** —— 漏掉
用户能用 token 描述的内容是宪法级违约；返回相关度较低但 token-match
的结果不是。

**L2 retrieval truthfulness model 三条**：

1. **Token-match 完整性**：L2 默认 retrieval 路径必须返回所有 token-match
   文档（基于 FTS5 / 关键词 / entity tokenize）的完整 candidate set。不得在
   retrieval 层做"相关度阈值截断"。

2. **Ranking 与 truncation 解耦**：
   - L2 search core 返回**完整** ranked result set + `total_matches` count
   - **截断只在 display layer**（CLI、JSON output）发生，且必须可显式解除
     （`--limit 0` 或等价开关）
   - 用户必须知道"还有多少没显示"（CLI 输出必须包含 total_matches 提示）

3. **Semantic / 向量检索作为 explicit opt-in**：
   - L2 默认 retrieval 路径不调用向量检索（embedding noise 与 recall-first
     承诺有结构性张力）
   - 向量检索代码保留，仅在以下情形启用：
     a. 用户显式 `--semantic` flag
     b. L3 agent 编排显式请求
     c. Zero-result keyword fallback（已 shipped 的 ADR-006 行为，保留）
   - 向量检索的 noise 必须由 calling agent (L3) 或用户显式 acknowledgement
     负责过滤，不得污染 L2 默认 result set

**Paraphrase / 抽象语义类查询的责任分配**：
- L1（写入层）：通过 frontmatter tags / topics / entity aliases 富化 corpus，
  使 keyword retrieval 能命中更多语义变体（L1 enrichment 允许 LLM 协助，
  per §1.5）
- L3（agentic 层）：通过 query rewrite / multi-pass keyword 调用 L2，
  覆盖 paraphrase 场景（L3 允许 LLM）
- L2（CLI core）：**不承担 paraphrase 责任**，只忠实返回 token-match 结果

**违宪示例**：
- ❌ L2 默认 retrieval 在源头丢弃 candidate 因 BM25 score 低于阈值
- ❌ L2 默认 truncation = 20 且无 `total_matches` 提示
- ❌ L2 默认开 semantic / vector retrieval 并把结果混进主 result set
- ❌ 通过 "noise gate" 在 L2 默认路径过滤"低相关度"结果

**合宪示例**：
- ✅ L2 返回 137 条 token-match，display 默认显示 top 20 + "still 117 results, use --limit 0"
- ✅ `--semantic` flag 显式 opt-in 启用向量检索
- ✅ L3 agent 把 "想摆烂" rewrite 为 "to-do-list", "overload", "退缩"
  多次调 L2 keyword search 后综合

**与 §1.5 的关系**：§1.5 划定"L2 不得调 LLM"层级边界；§1.11 进一步
划定"L2 默认 retrieval 不得调向量检索作为主路径"产品承诺边界。二者
互补：§1.5 防 LLM 渗透，§1.11 防"概率性 retrieval"渗透 L2 真相承诺。

**与 §1.6（向下兼容）的关系**：本条不修改任何 L1 数据格式；只规约 L2
runtime 默认行为。`.index/` 重建可继续生成 vector index，但默认不启用
其结果路径。

**与 §1.7（三条底线）的关系**：
- "宁可功能简单，不可系统复杂" → L2 默认 keyword-only 简单可审计
- "宁可人工维护，不可自动化陷阱" → 向量阈值/noise gate 调参是自动化陷阱
- "宁可牺牲性能，不可牺牲可靠性" → keyword retrieval 比 hybrid 更快且更
  deterministic

**§5.3 保护**：本条 §1.11 加入 §5.3 保护清单 —— 只允许变得更严，不允许
变得更松。未来"为让 paraphrase 数字好看而打开 hybrid default"的提案，
必须先通过 §5.2 修订本条。
```

### 2.3 同步附加 §3.2 amendment note

CHARTER §3.2 "双管道作为确定性原语" 当前措辞暗示双管道（FTS5 keyword + 向量 + RRF）始终是 default runtime 形态。§1.11 把 default 收紧为 keyword-only，向量 explicit opt-in。为保持 §3.2 主体不变（双管道仍是地基），在 §3.2 末尾追加一行 amendment note：

```markdown
> **§3.2 amendment (v1.6.0, 2026-05-23, RFC-2026-05-23-l2-recall-first-
> truthfulness-model)**: 本条 §3.2 提及的"双管道"指其作为确定性搜索原语的
> 存在（FTS5 + 向量 + RRF 均保留可用）；其 **默认 runtime 启用形态**
> 见 §1.11。即 default search path = keyword pipeline only，向量 pipeline
> 通过 explicit opt-in（`--semantic` / L3 agent 显式请求 / zero-result
> fallback）启用。§3.2 主体的"地基不可替换"承诺保持不变。
```

---

## §3 触发场景与证据

### 3.1 真实证据链

| 证据                                  | 出处                                                                     | 说明                                                                                          |
| ----------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| README 口语承诺                         | `README.en.md:295`                                                     | "recover key memory fragments... fully offline, deterministic, and zero-token"              |
| Production default = hybrid         | `tools/search_journals/core.py:1026`                                   | "hybrid: keyword + semantic run in parallel, merged via RRF (default)"                      |
| Eval gate default = keyword-only    | `tools/eval/__main__.py:38-40`                                         | `--semantic` default disabled                                                               |
| Round 19 hybrid P@5 仅 0.49          | `CHARTER.md:423` 注释                                                    | "Round 19 Phase 1-D 当前指标（107 queries, hybrid 模式）：MRR@5=0.6006, Recall@5=0.8387, P@5=0.4894" |
| v1.2.0 cycle2 keyword-only baseline | `.agent-reports/v120-search-fusion-m3/phase-a/A6_baseline_result.json` | overall R@5=0.6786, C2=0.14, C3=0.57, C1=C4=1.0                                             |
| BGE-M3 model (当前 embedding)         | `tools/lib/search_config.py:138`                                       | 业界 SOTA-tier 中文 embedding，证明 "升级 model 解 paraphrase" 路径无效                                   |
| 历史 round-18 semantic-on baseline    | `tests/eval/baselines/round-18-semantic-baseline.json`                 | semantic_enabled=true R@5=0.8778 但需对照 precision 数字                                          |

### 3.2 主理人 historical context（2026-05-23 对话引用）

> "...semantic搜索一打开就确实能够提高搜索的全面性...但是当时无论如何调试semantic的一个什么取值都无法获得一个两全其美的效果 —— 要么取值太低匹配为零、对双管道搜索结果贡献为零，要么就井喷出一堆噪音...所以当时的主编排agent（不是现在这个）就建议干脆把semantic搜索默认关闭算了..."

> "搜索结果会强行截断20条 —— 这一点同样会打破"不遗漏您每一个人生碎片"的产品承诺..."

> "现在这个"难以两全其美"的结果，是否是因为我们选的embedding model不够好？"

CTO 回应（同对话）：当前 model 是 BGE-M3，业界 SOTA-tier；升级 model 只能 marginal 改善，不能解决 dense retrieval 在 short Chinese journal corpus 上的 inherent 噪音问题。即使升级到 OpenAI text-embedding-3-large 也违反 §1.5 / Foundation Freeze offline。

### 3.3 v1.2.0 PRD scope 错配的因果

CTO 在 v1.2.0 cycle2 M1 PRD 中错误地假设了 baseline ~0.6 大致均匀分布，并 design 了 Sub-PRD-2.1 (BM25 norm) + Sub-PRD-2.2 (entity_boost) + Sub-PRD-2.3 (RRF recalibrate) 三件武器。Baseline 跑出来后发现：

- C1/C4 已 ceiling 1.0 → Sub-PRD-2.1/2.2 无信号空间
- C2 0.14 在 keyword-only mode 下 → CTO 起初误判"C2 不可解"
- Sub-PRD-2.3 RRF 调 k 在 single-source 情形下无意义

后 surface root cause = **truthfulness model 未定调 → eval mode vs production mode mismatch → PRD anchor 错位**。

修订 §1.11 直接解决这个 root cause。

---

## §4 反对意见 + 回应（CTO 自审，≥2 条）

### 反对意见 #1：放弃 hybrid 等于放弃 R@5 +0.16 的 recall 收益

**陈述**：Round 19 Phase 1-D 数据显示 hybrid mode R@5=0.8387，keyword-only mode ~0.68。差 0.16 的 recall 是用户能查到信息的 16%。enshrine "keyword-only default" 等于明示放弃这 16%。这跟 "不遗漏每一个人生碎片" 承诺不矛盾吗？

**CTO 回应**：

1. **R@5 差值的实际含义**：R@5 衡量的是 "expected_relevant 前 5 排名" 的覆盖率，不是 "返回所有 token-match" 的覆盖率。keyword-only mode 仍然返回**所有 token-match** 文档；hybrid mode 多召回的是 **token-不 match 但语义相似**的文档。"不遗漏" 的对象是用户能用 token 描述的内容；用户用不出 token 的内容本来就**只能** L3 agent rewrite 帮忙找。
2. **Hybrid 的 16% recall 实际质量**：Round 19 Phase 1-D P@5=0.4894 意味着这多召回的 16% 里有近半是噪音。用户看到 "似乎相关但读完发现不相关" 的结果，是 **认知层面的"遗漏"** —— 用户以为这就是全部，实际真相被噪音淹没。
3. **L3 兜底是 superior recovery path**：L3 agent 把 "想摆烂" rewrite 为多个具体 keyword 多次调 L2，最终用户可以 grok 每一条命中是为什么。这比 hybrid 黑盒"似乎相关"的 16% noise-laden recall 信任度高得多。
4. **结论**：§1.11 的 recall-first 是 **"对用户能 articulate 的内容不遗漏"**，不是 "对embedding 计算出来的近邻不遗漏"。后者本质是 precision 而非 recall。

### 反对意见 #2：没有 LLM provider 的终端用户失去 paraphrase 能力

**陈述**：§1.9 Agent-Native 模块原则承诺"没有 LLM provider 的终端用户也能完成核心价值"。但 §1.11 把 paraphrase 推到 L3 agentic，等于说没 LLM 的用户搜不到 paraphrase。这违反 §1.9。

**CTO 回应**：

1. **§1.9 承诺的边界**：§1.9 说"无 LLM provider 时模块能输出核心价值" = "能搜到 token-match 文档 + 能输出 evidence pack + 能 navigate index 树"。它**没有承诺** "无 LLM 时也能解 paraphrase"。Paraphrase 本质需要语义理解，是 L3 范畴。
2. **§1.11 提供的兜底**：
   - L1 enrichment 路径（用户写入时 LLM 助手 enrich，或 deterministic rule-based topic/tag 富化）使 keyword retrieval 能命中更多变体。这是**长期 fix**，不依赖运行时 LLM。
   - 用户 explicit `--semantic` flag 仍可启用向量检索（接受 noise tradeoff）—— 这是 escape hatch，不是 default。
3. **结论**：§1.11 收紧 default 行为，但保留 escape hatch。无 LLM 用户仍可：(a) 用 keyword 搜 token-match；(b) explicit `--semantic` 进 hybrid mode；(c) 接受 paraphrase 是 L3 范畴的限制。没有违反 §1.9。

### 反对意见 #3（次要）：行业惯例都是 hybrid default，Life Index "逆潮流"

**陈述**：Notion AI / Mem0 / Obsidian smart-search 等都默认 hybrid。Life Index 单独走 keyword-only 是 "逆向"，会让用户体验落后。

**CTO 回应**：

1. **行业产品定位不同**：Notion AI / Mem0 是 SaaS + cloud LLM，hybrid noise 由后端 LLM 自动 filter，用户体验是 "提问 → 干净答案"。Life Index 是 **offline-first CLI + agent-native**，noise 没法被 L2 自动 filter。
2. **§1.7 三条底线**：宁可功能简单，不可系统复杂。Life Index 故意选 simpler base + agent 兜底，是 deliberate 设计。
3. **§1.10 模块-基础层契约**：L2 是基元层，L3 是模块/agent 层。让 L2 抢 L3 的 paraphrase 职责是 layer violation。
4. **结论**：Life Index 走自己的路是 deliberate 而非 ignorant。"逆潮流"是 feature 不是 bug。

---

## §5 影响清单

### 5.1 文档变更

| 文档                                                                      | 变更类型                                                                                        | 备注                 |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------ |
| `CHARTER.md`                                                            | 新增 §1.11 + §3.2 末尾加 amendment note + header 版本 v1.5.0→v1.6.0 + 修订次数 5→6 + §5.3 保护清单追加 §1.11 | 主要载体               |
| Private local charter-history archive                                    | 新建归档                                                                                        | per §5.2 流程 #5     |
| `docs/adr/ADR-028-l2-recall-first-keyword-pure.md`                      | 新建                                                                                          | 架构决策记录             |
| `docs/ARCHITECTURE.md`                                                  | 修订 L2 default behavior 描述                                                                   | 反映 §1.11           |
| `docs/rfc/RFC-2026-05-23-l2-recall-first-truthfulness-model.md`         | 本文件                                                                                         | RFC 载体             |
| Private local v1.2.0 search-fusion PRD                                    | 加 superseded marker                                                                         | v1.2.0 cycle2 范围作废 |
| Private local v1.2.0 truthfulness/recall-first plan                        | 新建占位                                                                                        | 新 v1.2.0 cycle 起点  |

### 5.2 Invariants 受影响

- **§1.5（确定性与智能的边界）**：不修改，但 §1.11 进一步 narrow 其含义
- **§1.7（三条设计底线）**：reinforced，§1.11 是 §1.7 的具体应用
- **§1.10（模块-基础层契约）**：reinforced，§1.11 强化 L2/L3 layer split
- **§5.3（不可弱化清单）**：追加 §1.11

### 5.3 既有 RFC / ADR 受影响

- **ADR-006 (Semantic Adaptive Threshold)**：保留有效。其规约的 zero-result fallback semantic 行为符合 §1.11 例外条款 (c)。
- **ADR-010 (RRF Weight Tuning)**：行为不变，但 default 不启用（仅在 `--semantic` 或 L3 调用时启用）
- **RFC-2026-05-19 (Foundation Freeze)**：reinforced，§1.11 是 Foundation Freeze v1 在 retrieval truthfulness 上的具体化

### 5.4 代码变更（NOT in this RFC scope）

本 RFC 只修订 CHARTER / ADR / ARCHITECTURE 文档。**不改任何代码**。代码变更（reset default semantic flag, 解除 truncation, 增加 total_matches 等）按新 v1.2.0 cycle PRD 走 M1→M4 工作流。

### 5.5 用户可见行为变更（after 代码变更落地）

| 变更                 | Before                            | After                                             |
| ------------------ | --------------------------------- | ------------------------------------------------- |
| CLI default search | hybrid (keyword + semantic + RRF) | keyword-only                                      |
| CLI truncation     | 强制截断 20                           | default 20 但可 `--limit 0` 解除 + `total_matches` 提示 |
| `--semantic` flag  | flag 存在但 default on               | flag 存在，default off，explicit opt-in               |
| L3 agent 体验        | 不变                                | 不变（agent 通过 query rewrite 多次调 L2）                 |

### 5.6 回滚方案

如果 §1.11 land 后 6 个月内出现以下情况之一，可走 §5.2 反向修订：

- 用户 explicit 反馈"漏掉太多我能模糊描述但用不出 token 的内容"
- L3 agent 生态在 6 个月内未能成熟到能稳定提供 paraphrase 兜底
- 业界出现 deterministic 非 LLM 的语义检索新范式（unlikely but possible）

反向修订仍走 §5.2 substantive gate。**不允许通过普通 commit 弱化 §1.11**（§5.3 保护）。

---

## §6 Gold Set 回归状态

§5.2 流程 #2 要求 Gold Set 回归。本 RFC 本身不改代码，所以 Gold Set 不会回归失败。

但**新 v1.2.0 cycle 实施 §1.11 的代码变更时**必须跑 Gold Set 回归。预期：

- keyword-only baseline 已跑（v1.2.0 cycle2 R@5=0.6786）
- 解除 truncation 后 R@5 不变（truncation 只影响 display，不影响 retrieval truthfulness 数字）
- semantic 改 explicit opt-in 后默认 baseline 与当前 keyword-only baseline 一致

代码 PR 时附带 baseline 对比（Round 19 hybrid 0.8387 vs keyword-only 0.6786 已是公开 evidence，无需再跑）。

---

## §7 主理人 Ack 签字位

> Per §5.2 流程 #3 第 4 项 "**主理人 ack 签字**：作者本人书面 ack（不可委托）"，本 RFC 需主理人在此签字方可 land：

```
我（主理人）已阅读本 RFC §1-§6 全部内容，理解：

1. CHARTER 将新增 §1.11 "Recall-First Retrieval Truthfulness Model" 作为不变量
2. §1.11 enshrine "不遗漏每一个人生碎片" 为 50 年宪法承诺
3. L2 default behavior 将变为 keyword-only，semantic 改为 explicit opt-in
4. Truncation 将与 retrieval 解耦，可通过 --limit 0 显式解除
5. Paraphrase 责任明确 transfer 到 L1 enrichment + L3 agentic rewrite
6. §1.11 加入 §5.3 不可弱化清单
7. 本 RFC 仅修订文档，不改代码；代码变更按新 v1.2.0 cycle 单独走 M1→M4

我 ack 此 RFC 立即 land。

签字: Dexter
日期: 2026-05-23
```

---

## 附录 — §5.2 4 项 substantive gate 自检表

| 项                      | 状态        | 位置  |
| ---------------------- | --------- | --- |
| ① rationale            | ✅         | §1  |
| ② 反对意见 addressed（≥2 条） | ✅（3 条）    | §4  |
| ③ 影响清单                 | ✅         | §5  |
| ④ 主理人 ack 签字           | ⏳ Pending | §7  |

④ 完成 → 立即 land，CHARTER 版本递增 v1.5.0 → v1.6.0。
