# Life Index Architecture

> **本文档职责**: 项目架构设计与关键决策记录
> **目标读者**: 开发者、架构师、贡献者

---

## 1. 核心原则

### 1.1 Agent-Native

- 能由 Agent 直接完成的操作，不开发专用工具
- 专用工具仅在需要**原子性**、**高可靠性**或**复杂计算**时引入
- Agent 负责理解意图与编排流程；稳定读写能力通过 CLI 工具暴露

### 1.2 数据主权

- 100% 本地存储，用户拥有绝对数字主权
- 数据格式为人可读（Markdown + YAML），不依赖特定软件
- 目录结构清晰，便于人工浏览和维护

### 1.3 单层透明

```
用户 ↔ Agent ↔ CLI ↔ 文件系统
```

禁止在 CLI SSOT 之外再引入额外的长期写入层（数据库、服务进程、API 网关等）。

### 1.4 设计底线

```
宁可功能简单，不可系统复杂
宁可人工维护，不可自动化陷阱
宁可牺牲性能，不可牺牲可靠性
```

### 1.5 交互范式：人-Agent-CLI 三层信息流

Life Index 的用户界面架构基于一个核心认知：

> **CLI 是 Agent 的母语，GUI 是人的母语。**

#### 信息流分层

| 层级 | 服务对象 | 最佳接口 | 设计意图 |
|------|----------|----------|----------|
| **CLI 层** | Agent | 命令行 | 结构化输入输出、可 pipe、自描述 |
| **Agent 层** | 人 + CLI | 自然语言理解 | 翻译人语→CLI，解析 CLI→人语 |
| **GUI 层** | 人 | 可视化界面 | 直观交互、表单触发、结果渲染 |

#### 核心约束

1. **CLI 是 SSOT**：所有能力以 CLI 暴露，Agent 和 GUI 只是 CLI 的不同"封装形态"
2. **当前仓库以 CLI Core 为主**：任何未来 GUI / Experience Layer 都必须消费 CLI 契约，而不是成为当前仓库的并行 authority surface
3. **Agent 不替代 CLI**：Agent 负责理解意图，但执行必须通过 CLI

#### 行业验证

2026 年钉钉/飞书 CLI 化转型证明：Agent 操作软件的最佳方式是命令行（成本 17 倍低于 MCP）。Life Index 的设计与行业共识一致。

---

## 2. 分布式索引树架构

### 2.1 索引树结构

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

### 2.2 确定性边界线

| 内容类型 | 归属工具 | 所在层级 |
|---------|---------|---------|
| 条目表格行 + frontmatter 聚合 | `generate_index`（确定性） | CLI Core |
| 年度/月度回顾段 | `generate_report`（Agent 驱动） | Intelligence Layer |
| by-topic 摘要文字 | `generate_index`（确定性） | CLI Core |

`generate_index` 生成的文件中，叙事区域留 placeholder。`generate_report` 是 Agent 编排任务，不是 Python CLI 工具。

### 2.3 渐进式元数据披露

INDEX.md < index_YYYY.md < index_YYYY-MM.md

每层索引是其覆盖时间段的元数据聚合体，Agent 阅读一个索引文件即可了解该阶段内容，无需逐条阅读日志。

---

## 3. 双管道并行检索架构

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

**核心原则**：每一层是过滤器，不是数据源。两条管道并行执行，RRF 融合排序。

---

## 3. 关键架构决策

### ADR-001: Agent-Native 架构设计

**决策**: 仅开发必要的原子工具，其他由 Agent 完成。

**原因**: Life Index v2 版本因过度工程化导致系统失效。Agent-Native 方案最能发挥 Agent 能力同时保持系统简洁。

**收益**:
- 减少代码量，降低维护成本
- 充分利用 Agent 的自然语言能力
- 系统架构简洁透明

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

## 4. 系统边界

### 4.1 我们做什么

- ✅ 自然语言日志记录
- ✅ 结构化元数据提取
- ✅ 多维度索引维护（时间、主题、项目、标签）
- ✅ 分层级日志检索
- ✅ 附件管理

### 4.2 我们不做什么

- ❌ 云端同步（用户可自行用云盘备份）
- ❌ 多人协作（当前单用户设计）
- ❌ 富文本编辑（纯 Markdown）
- ❌ 实时分析仪表盘（定期摘要替代）

---

## 5. 目录结构

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

---

## 6. 数据隔离原则

| 存储位置 | 内容 | 说明 |
|---------|------|------|
| `~/Documents/Life-Index/` | 用户数据 | 日志、附件、索引 |
| 项目代码目录 | 程序代码 | 工具、配置、文档 |

**两者物理隔离，不可混淆。**

---

## 7. Round 6 基础设施增强

### 7.1 Schema 迁移

- `life-index migrate --dry-run` — 扫描 schema 版本分布
- `life-index migrate --apply` — 确定性迁移（补字段 + bump version）+ needs_agent 输出
- 迁移链框架：`register_migration(from, to)` 装饰器注册，`run_migration_chain()` 执行

### 7.2 搭便车事件通知

- 在 CLI 响应中增加 `events` 字段（零 cron、零进程、零外部依赖）
- 5 个内置事件：`no_journal_streak`、`monthly_review_due`、`entity_audit_due`、`schema_migration_available`、`index_stale`
- 检测总耗时 < 50ms（只做文件 stat，不读内容）

### 7.3 Entity 质量审计

- `life-index entity --audit` — CLI 检测 + Agent 访谈协作模式
- 检测：重复实体、孤立实体、频繁共现无关系
- Agent 逐项访谈用户决定 merge/archive/add_relationship

### 7.4 操作级可观测性

- 所有 CLI 响应中增加 `_trace` 字段（trace_id + command + total_ms + steps）
- 上下文管理器模式：`with Trace("write") as t: t.step("validate")`

### 7.5 不做什么

- 不做 WAL/checkpoint、Vector 增量更新、Agent Memory、Multi-Agent、Plugin、MCP

---

## 相关文档

- [bootstrap-manifest.json](../bootstrap-manifest.json) - Authority anchor；onboarding 必须先刷新此文件
- [AGENT_ONBOARDING.md](../AGENT_ONBOARDING.md) - 基础版 Agent 安装与初始化流程
- [API.md](./API.md) - 工具接口详细文档
- [AGENTS.md](../AGENTS.md) - 开发者上下文；Web GUI 开发约束引用 §1.5 交互范式
- [SKILL.md](../SKILL.md) - Agent 技能定义；相关文档引用 §1.5 交互范式
- [README.md](../README.md) - 用户入口与安装提示
