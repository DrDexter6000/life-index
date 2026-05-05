# Life Index Architecture

> **本文档职责**: 架构实现细节、参数快照、基础设施演进记录
> **目标读者**: 开发者、架构师、贡献者
> **权威层级**: 本文档从属于 [`CHARTER.md`](../CHARTER.md)。若本文档与宪章冲突，以宪章为准。

---

## 0. 读前必读：宪章关系

**本文档不再重复以下不变量** — 请直接读 [`CHARTER.md`](../CHARTER.md)：

| 原则 | 归属位置 |
|------|----------|
| Agent-Native、CLI 作为 SSOT | CHARTER §1.3、§2.3 |
| 数据主权（100% 本地） | CHARTER §1.1 |
| 纯文本永久性（Markdown + YAML） | CHARTER §1.2 |
| 层级隔离（L1-L4 四层模型） | CHARTER §1.4、第二章 |
| 确定性 vs 智能边界（L2 不得调 LLM） | CHARTER §1.5 |
| 向后兼容性（50 年数据读取保证） | CHARTER §1.6 |
| 设计三底线（简单/人工/可靠） | CHARTER §1.7 |
| 交互范式（人-Agent-CLI 三层信息流） | CHARTER §1.3 + §2 |
| 系统边界（做什么 / 不做什么） | CHARTER §1.7 + 第四章反模式黑名单 |
| 数据隔离（用户数据 vs 代码） | CHARTER §1.1 |

**本文档聚焦可演化的实现细节** — 索引树结构、双管道参数、ADR-003/004 等可演化决策、目录快照、基础设施增量记录。这些随实现版本迭代，不属于宪章不变量。

---

## 1. 分布式索引树架构

### 1.1 索引树结构

索引文件与数据物理共存，每层目录携带自己的索引：

```
~/Documents/Life-Index/
├── INDEX.md                              ← 根锚点（系统地图，<2KB）
├── Journals/
│   ├── 2026/
│   │   ├── index_2026.md                 ← 年度索引：全量元数据聚合 + 月份指针
│   │   ├── 01/
│   │   │   ├── index_2026-01.md          ← 月度索引：逐条全量元数据 + 回顾 placeholder
│   │   │   └── life-index_2026-01-05_001.md
│   │   └── 03/
│   │       ├── index_2026-03.md
│   │       ├── life-index_2026-03-04_001.md
│   │       └── report_2026-03.md         ← 月度叙事报告（Agent 生成）
│   └── 2025/
│       └── index_2025.md
├── by-topic/                             ← 主题维度索引
│   ├── 主题_work.md
│   └── ...
└── .index/                               ← 机器检索层（FTS5 + 向量 DB）
```

### 1.2 确定性边界线

| 内容类型 | 归属工具 | 所在层级 |
|---------|---------|---------|
| 条目表格行 + frontmatter 聚合 | `generate_index`（确定性） | CLI Core |
| 年度/月度回顾段 | `generate_report`（Agent 驱动） | Intelligence Layer |
| by-topic 摘要文字 | `generate_index`（确定性） | CLI Core |

`generate_index` 生成的文件中，叙事区域留 placeholder。`generate_report` 是 Agent 编排任务，不是 Python CLI 工具。此划分对应 CHARTER §1.5 的「确定性 vs 智能」硬线。

### 1.3 渐进式元数据披露

INDEX.md < index_YYYY.md < index_YYYY-MM.md

每层索引是其覆盖时间段的元数据聚合体，Agent 阅读一个索引文件即可了解该阶段内容，无需逐条阅读日志。

---

## 2. 双管道并行检索架构

**核心目的**: 逐层缩小候选集以节省 Agent 上下文 token 消耗。

```
                    用户查询
                      │
              L0: 索引树预过滤（可选）
              --year / --month / --topic
              缩小候选集为布尔集（不产生分数）
                      │
                   ┌──┴───┐
            ┌──────▼──────┐  ┌──────▼──────┐
            │ Pipeline A  │  │ Pipeline B  │
            │   关键词     │  │   语义      │
            │ L1 filter   │  │ (bge-m3)    │
            │ L2 filter   │  │ 向量搜索    │
            │ L3 FTS5     │  │             │
            └──────┬──────┘  └──────┬──────┘
                   └────┬────┘
              RRF 融合 (k=60)
                      │
                 最终排序结果
```

| 层级 | 数据来源 | 返回内容 | 设计意图 |
|:---:|:---:|:---:|:---|
| **L1 索引层** | `by-topic/` 索引文件 | 日期+标题+路径（~80字节/篇） | 按主题/项目/标签快速缩小候选集 |
| **L2 元数据层** | YAML Frontmatter（SQLite 缓存） | 全部元数据（~500字节/篇） | 按日期、心情、人物等多维度过滤 |
| **L3 内容层** | FTS5 全文索引 | 匹配片段+上下文（~300字节/条） | 关键词精确匹配，返回段落而非全文 |
| **语义层** | 向量嵌入（sentence-transformers / bge-m3） | 路径+相似度（~100字节/条） | 找到"意思相近"但关键词不同的日志，支持多语言长文本检索 |

**核心原则**：每一层是过滤器，不是数据源。两条管道并行执行，RRF 融合排序。Pipeline A 内部执行三层递进过滤：L1 索引层快速预筛（by-topic 索引文件），L2 元数据层多维度过滤（YAML Frontmatter + SQLite 缓存），L3 FTS5 内容层精确匹配。Pipeline B 独立执行向量相似度搜索。两条管道结果经 RRF 融合后返回。

> 本双管道是 **确定性检索原语**，零 LLM 依赖。Agent 编排层（query understanding、result filtering）仅可在 `tools/search_journals/orchestrator.py` 内出现 —— 详见 CHARTER §3。

---

## 3. 关键架构决策（可演化）

> Agent-Native 架构原则已提升为宪章 §1.3 不变量（见 CHARTER.md）。本节仅保留**可演化的**架构决策 ADR。

### ADR-003: YAML Frontmatter 格式选择

**决策**: 采用 YAML + JSON 数组混合格式。

```yaml
mood: ["专注", "充实"]
tags: ["重构", "优化"]
```

**原因**: 兼顾人类可读性和紧凑性。

**收益**:
- YAML 基础格式人可读性好
- JSON 数组格式紧凑
- 兼容 Jekyll/Obsidian 等工具

### ADR-004: MCP 迁移评估

**决策**: 不迁移到 MCP，保持当前 CLI + SKILL.md 架构。

**原因**:

1. **上下文经济性**：MCP 要求在连接建立时一次性向 Agent 暴露所有 tool schema（tool listing），这意味着即使 Agent 只想写一篇日记，也必须加载全部 12 个工具的完整参数定义。相比之下，当前 SKILL.md 方案支持**渐进式披露**——Agent 按需阅读对应 workflow 段落，仅加载当前任务所需的工具签名和约束，大幅降低上下文和 token 负载。
2. **私人日志系统的场景适配**：Life Index 是单用户、低频调用的个人系统，MCP 的多客户端连接管理、工具发现协议等能力属于"大炮打蚊子"。当前 CLI JSON-in/JSON-out 的原子操作模式完全胜任。
3. **收益/成本比低**：~10 小时工作量换取的体验提升对单用户不显著。
4. **协议稳定性**：MCP 协议仍处于快速发展期，过早绑定可能引入不必要的迁移成本。

**与 MCP 方案的对比**:

| 维度 | MCP | 当前 CLI + SKILL.md |
|------|-----|---------------------|
| 工具发现 | 连接时全量暴露 | Agent 按需阅读，渐进披露 |
| 上下文开销 | 高（全部 schema 常驻） | 低（仅加载当前 workflow） |
| 适用场景 | 多客户端、高频、工具市场 | 单用户、低频、深度集成 |
| 维护成本 | 需维护 MCP Server 进程 | 零额外进程 |

**结论**: 对 Life Index 而言，渐进式披露的 token 节约 > MCP 的协议便利。除非出现强制要求 MCP 的 Agent 宿主（且无 CLI fallback），否则不迁移。

---

## 4. 目录结构

```
~/Documents/Life-Index/           # 用户数据目录
├── INDEX.md                      # 根锚点（系统地图）
├── Journals/                     # 日志文件存储
│   └── YYYY/                     # 按年分层
│       ├── index_YYYY.md         # 年度索引
│       └── MM/                   # 按月分层
│           ├── index_YYYY-MM.md  # 月度索引
│           └── life-index_*.md   # 日志原文
├── by-topic/                     # 主题维度索引
│   ├── 主题_work.md
│   ├── 项目_Life-Index.md
│   └── 标签_重构.md
├── attachments/                  # 附件存储
│   └── YYYY/MM/
└── .index/                       # 机器检索层（FTS5 + 向量 DB）
```

> 数据隔离（用户数据 vs 项目代码物理隔离）已提升为宪章 §1.1 不变量，见 CHARTER.md。

---

## 5. 基础设施增强

### 5.1 Schema 迁移（Round 6）

- `life-index migrate --dry-run` — 扫描 schema 版本分布
- `life-index migrate --apply` — 确定性迁移（补字段 + bump version）+ needs_agent 输出
- 迁移链框架：`register_migration(from, to)` 装饰器注册，`run_migration_chain()` 执行

### 5.2 搭便车事件通知（Round 6）

- 在 CLI 响应中增加 `events` 字段（零 cron、零进程、零外部依赖）
- 5 个内置事件：`no_journal_streak`、`monthly_review_due`、`entity_audit_due`、`schema_migration_available`、`index_stale`
- 检测总耗时 < 50ms（只做文件 stat，不读内容）

### 5.3 Entity 质量审计（Round 6）

- `life-index entity --audit` — CLI 检测 + Agent 访谈协作模式
- 检测：重复实体、孤立实体、频繁共现无关系
- Agent 逐项访谈用户决定 merge/archive/add_relationship

### 5.4 操作级可观测性（Round 6）

- 所有 CLI 响应中增加 `_trace` 字段（trace_id + command + total_ms + steps）
- 上下文管理器模式：`with Trace("write") as t: t.step("validate")`

### 5.5 搜索评估与可观测体系（Round 8）

Round 8 在双管道并行检索架构之上，建立了完整的搜索质量保障闭环：

- **结构化搜索指标落盘**：每次搜索自动写入 `~/.life-index/metrics/YYYY-MM.jsonl`，记录 query、latency、pipeline signal、result count 等关键字段
- **搜索诊断入口**：`life-index search --diagnose` 聚合最近搜索行为，输出退化线索（zero-result queries、degraded searches、latency outliers）
- **Eval 质量闸门**：CI 集成搜索 eval gate，验证 golden query 覆盖、噪声拒绝、正向召回、baseline 比较
- **中文分词模块**：jieba 集成（index/query 双模式），支持 FTS5 中文精确匹配
- **17 个 ADR 常量集中管理**：所有搜索参数（RRF k、min_relevance、score weights 等）通过 `search_constants.py` 集中管理，每个参数有 ADR 编号和决策记录

### 5.6 不做什么（本轮实现层约束）

- 不做 WAL/checkpoint、Vector 增量更新、Agent Memory、Multi-Agent、Plugin、MCP

> 更宽泛的"我们不做什么"系统边界已由 CHARTER §1.7 与第四章反模式黑名单承担。

### 5.7 自动索引重建与新鲜度检查（Round 8 Phase 1 + Round 12）

搜索索引（FTS5 + 向量）通过 `tools/build_index/` 模块管理，支持自动新鲜度检测和增量重建：

- **TOKENIZER_VERSION 机制**：`search_constants.py` 中的 `TOKENIZER_VERSION` 整数与 FTS 索引一起存储。当 jieba 分词器配置变更时，bump 版本号触发自动全量重建，确保索引 token 与查询时一致（ADR-011）
- **Index Manifest**：`tools/lib/index_manifest.py` 管理索引构建状态（counts + checksums + partial flag），支持增量更新的原子性和恢复
- **Pending Queue**：`tools/lib/pending_writes.py` 实现写入穿透缓存，写入/编辑后标记 pending，搜索前消费，确保搜索结果包含最新数据（ADR-017）

### 5.8 搜索编排器（Round 17 Phase 5 — 已实现）

CHARTER §1.5 定义了"确定性 vs 智能"的边界：CLI Core 层（`tools/search_journals/`）执行纯确定性搜索，Intelligence Layer 的编排器负责 LLM 调用。

编排器架构（`tools/search_journals/orchestrator.py`）：
- **CLI 入口**：`life-index smart-search`（注册于 `tools/__main__.py`，实现于 `tools/smart_search/__main__.py`）
- **三段式流程**：前置改写（LLM 拆解 query）→ 中间调用（按意图调 search 原语）→ 后置筛选 + 摘要（LLM 精筛）
- **降级策略**：LLM 超时/失败时自动回退到纯双管道
- **Data Minimization**：候选仅送 title + abstract + snippet（≤200 chars），最多 `ORCHESTRATOR_MAX_LLM_CANDIDATES`（15）条，禁止送 full_content

### 5.9 常量集中管理（Round 17 Phase 1-A）

`search_constants.py` 作为搜索子系统所有阈值的唯一来源（CHARTER §4.3 合规）：

- **50** 个导出常量（`__all__` 已补齐，Round 19 新增 fuzzy typo 4 个 + structured intent 3 个 = +7），涵盖 RRF、语义、FTS、评分、置信度、标题加权、L3 回退、关键词管道、编排器、fuzzy typo correction、structured metadata retrieval 等全部参数
- 每个常量带 ADR 编号和决策 rationale
- 散落在 `confidence.py`、`title_promotion.py`、`l3_content.py`、`keyword_pipeline.py` 中的 14 个裸字面量已于 Round 17 Phase 1-A 迁移完毕

### 5.10 Phase 1-D 搜索增强（Round 19 Phase 1-D）

Round 19 Phase 1-D 在搜索子系统中新增以下能力：

- **Eval Anchor 确定性注入**（F1）：`LIFE_INDEX_TIME_ANCHOR` 环境变量使 eval baseline 在任意日期产出 byte-identical metric，解决相对时间漂移问题。`run_eval.py` 启动时读取 baseline `frozen_at` 注入 env。
- **Fuzzy Typo Correction**（C1-a）：`FUZZY_TYPO_*` 常量组（阈值 0.85, 长度差 ≤2, 规范字符串 `("life index",)`）在 `query_preprocessor.py` 中做 Levenshtein 模糊匹配，覆盖 GQ80 等拼写错误查询。
- **Bilingual Alias Expansion**（C1-b）：`query_preprocessor.py` 内置中英别名映射（如 `birthday↔生日`），覆盖 GQ81 等跨语言查询。
- **Structured Intent Match Bonus**（R1 safe）：`STRUCTURED_*` 常量组在 keyword-only 路径上对同时命中 date_range + topic_hints 的候选结果加分（+50 keyword path, +0.035 hybrid path），安全实现不做全局排序补丁。
- **Broad Eval Soft Gate**：15 个 broad recall 查询从 MRR 强塞转为 `predicate_precision@5` 评估，precision < 0.8 / min_results fail / broad_eval_error 进入 failures；exact MRR 查询完全隔离，旧 metrics zero-drift 验证通过。

---

## 6. 工程规范

### 6.1 代码风格指南

**命名约定**: 函数/变量 `snake_case` | 常量 `UPPER_SNAKE_CASE` | 类 `PascalCase`

**类型注解**: 必须使用

**路径处理**: 统一使用 `pathlib.Path`

**编码**: UTF-8

**JSON 输出格式**:
```json
{
  "success": true,
  "data": { ... },
  "error": "错误信息（如有）"
}
```

### 6.2 模块结构

```
tools/                         # Core CLI/tool layer
├── write_journal/
├── search_journals/
├── edit_journal/
├── entity/                    # 实体图谱 + 质量审计 + review hub + merge/delete
├── generate_abstract/
├── build_index/
├── query_weather/
├── backup/
├── migrate/                   # Schema 链式迁移
├── dev/                       # 开发/验收辅助工具
├── smart_search/              # LLM 编排智能搜索
├── eval/                      # 搜索质量评估
└── lib/                       # 共享库（SSOT）
```

### 6.3 日志文件格式

#### 目录结构

```
~/Documents/Life-Index/
├── Journals/                    # 日志主目录
│   └── YYYY/MM/                 # 按年月组织
├── by-topic/                    # 主题索引
└── attachments/                 # 附件存储
```

#### Markdown 格式

```yaml
---
title: "日志标题"
date: 2026-03-07T14:30:00
location: "Lagos, Nigeria"
weather: "晴天 28°C"
mood: ["专注", "充实"]
tags: ["重构", "优化"]
topic: ["work", "create"]
abstract: "100字内摘要"
---

# 日志标题

正文内容...
```

#### Topic 分类（必填）

> **SSOT**：`tools/lib/llm_extract.py` `VALID_TOPICS`。共 7 个有效值：`work`, `learn`, `health`, `relation`, `think`, `create`, `life`。此处不重复枚举，以代码为准。

---

## 相关文档

- [CHARTER.md](../CHARTER.md) — **项目宪章**（本文档从属于此；不变量与治理规则在此）
- [bootstrap-manifest.json](../bootstrap-manifest.json) - Authority anchor；onboarding 必须先刷新此文件
- [AGENT_ONBOARDING.md](../AGENT_ONBOARDING.md) - 基础版 Agent 安装与初始化流程
- [API.md](./API.md) - 工具接口详细文档
- [AGENTS.md](../AGENTS.md) - 开发者上下文；交互范式已迁至 CHARTER §1.3 + §2
- [SKILL.md](../SKILL.md) — Agent 技能定义
- [README.md](../README.md) — 用户入口与安装提示
- [ADR Index](./adr/INDEX.md) — ADR 分类索引（🔒 Invariant / 📋 Decision）

---

> **校对日期**: 2026-05-05
> **校对人**: Claude (Opus 4.7) / Round 19 Phase 1-D 收束
> **对应状态**: Round 19 Phase 1-D 已完成（Broad eval soft gate + eval anchor + fuzzy/alias + structured intent）。当前 CHARTER v1.2.0，search_constants.py **50** 常量。
