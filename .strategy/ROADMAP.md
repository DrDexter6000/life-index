# Life Index Evolution Roadmap

> **层级**：L1 — 项目架构演进路线图与战略决策记录
> **上级文档**：`.strategy/strategy.md`（全局战略入口）
> **下级文档**：`.strategy/gui/PHASE-OVERVIEW.md`（GUI 阶段概览）、`.strategy/cli/`（CLI 执行文档）
> **冲突仲裁**：本文件是架构决策与产品路线图的权威来源；子文档如有冲突以本文件为准
>
> **文档角色**: 项目架构演进路线图与战略决策记录
> **创建日期**: 2026-03-31
> **最后更新**: 2026-04-14（Round 7 完成归档 + CLI 状态校准）
> **参与者**: 项目 Owner + CTO 级架构评审
> **状态**: 双产品线战略已确认，CLI / GUI 共享战略治理已落地

---

## 1. 战略背景

### 1.1 项目评估

Life Index v1.5.x 综合评级 **B+**：设计理念领先行业，工程接近 production-ready。核心优势：

- **"CLI 是 Agent 的母语"** — 比行业共识更早落地的正确架构
- **双管道并行检索 + RRF 融合** — production-grade retrieval
- **Markdown + YAML Frontmatter** — 面向 50 年持久性的数据承诺
- **三层产品边界（Layer A/B/C）** — 罕见的产品纪律

### 1.2 市场现实：Vibe Coding 时代的竞争压力

2026 年现实：代码和产品概念急速贬值，爆款时间窗口越来越短。

| 你花 3 个月做的事 | 别人用 vibe coding 需要 |
|---|---|
| 双管道搜索 + RRF 融合 | 一个周末 |
| CLI 工具链 | 3 天 |
| Web GUI 基础功能 | 1 周 |

**代码不是壁垒。架构不是壁垒。**

Life Index 真正不可复制的竞争优势：

1. **愿景** — "给 20 年后我的女儿留下数字化的父亲"。没有人能 vibe code 出灵魂。
2. **审美** — 纪念碑谷/风之旅人级别的体验标准。品味是最稀缺的资源。
3. **数据承诺** — "50 年后还能读"。这是品牌，不是技术。

### 1.3 核心矛盾与战略转折

Web GUI 开发暴露了两个问题：

1. **底层问题**：搜索结果质量不足（漏网之鱼 + 噪音），Agent CLI 用户感知不到是因为 Agent 自动过滤
2. **架构问题**：在 Web GUI 里手工重建 agent intelligence（`intelligent_search.py` 的 4-phase workflow）

**Owner 关键反思**：

> Agent 不应成为遮掩底层工具质量问题的遮羞布。但同时，如果按原计划自下而上地迭代三步走，可能还没到第三步就被市场淘汰。

**结论：不能自下而上慢慢建，必须从终局用户体验倒推。但地基也必须先打牢。**

---

## 2. 战略决策：双产品线

### 2.1 产品线定义

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Life Index v1.x (CLI)          Life Index v2.0 (Experience) │
│  ─────────────────────          ──────────────────────────── │
│  极客的 agent-native 工具        面向大众的体验层              │
│  干净、可靠、承诺兑现            精美、动人、终局品质           │
│                                                              │
│  目标用户：开发者/极客            目标用户：所有人              │
│  接入方式：Agent IDE             接入方式：Web/App             │
│  交互语言：CLI                   交互语言：视觉+自然语言       │
│  仓库：life-index (现有)         仓库：life-index_gui（本地已建） │
│                                                              │
│          v2.0 叠加在 v1.x CLI 之上，CLI 是 SSOT              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 为什么分离

| 理由 | 说明 |
|------|------|
| **产品纯粹性** | v1.x 保持 agent-first 的干净清爽，兑现 README 初心 |
| **开发节奏独立** | CLI 版可以快速完善并发布，不被 UI 工作阻塞 |
| **技术栈自由** | v2.0 可以选择最适合视觉体验的技术栈（React/Svelte/Three.js 等），不受 Python FastAPI 限制 |
| **用户定位清晰** | 极客用 CLI，大众用 v2.0，各取所需 |
| **关注点分离** | CLI 仓库专注可靠性和工具完整性；v2.0 仓库专注视觉品质和用户体验 |

### 2.3 两条线的关系

```
Life Index v2.0 (Experience Layer)
  │
  │  调用（Agent-as-Backend 模式）
  │  或 MCP（当多智能体场景出现时）
  ▼
Life Index v1.x (CLI Core)
  │
  │  读写
  ▼
~/Documents/Life-Index/ (用户数据，Markdown + YAML)
```

**铁律**：v2.0 的所有写入操作必须经过 v1.x CLI。数据格式由 CLI 定义，v2.0 不得发明私有格式。

### 2.4 共享战略文档治理（2026-04-09）

双产品线虽然分开开发，但**高层战略、路线图、阶段 progress 不再分散维护**。

当前已落地的治理方式：

- canonical hub：D:\Loster AI\Projects\.strategy\
- CLI 入口：life-index\.strategy\
- GUI 入口：life-index_gui\.strategy\
- 统一读取顺序：.strategy/strategy.md → .strategy/ROADMAP.md → .strategy/cli/ 或 .strategy/gui/

这意味着：

- CLI / GUI 不得各自维护平行战略文档
- 顶层战略与 progress 一律在共享 .strategy/ 中维护
- 产品线差异通过 .strategy/cli/ 与 .strategy/gui/ 细分，而不是复制顶层文件

---

## 3. v1.x CLI 路线（先完成）

> **目标**：打磨至 production-ready，交付给极客社区，然后转入维护模式。

### 3.0 Maintenance Round 6→7（2026-04-14 状态更新）

v1.x 主建设阶段已完成并进入 maintenance mode。当前活跃的 CLI 执行计划是 `.strategy/cli/TDD.md`，对应 **Round 7: Entity Graph Evolution**。

- **Round 6** 已完成：Schema Migration、Event Piggyback、Entity Audit、Observability 等 Agent-Native 基础设施增强
- **Round 7** 已完成并归档关闭：Entity Graph 从"静态登记表"升级为 active serving layer
  - ✅ **Phase 1 已完成** (2026-04-13)：runtime view + search expansion v2 + entity_hints
  - ✅ **Phase 2 已完成** (2026-04-13)：write-time candidates + entity review hub + merge/delete
  - ✅ **Phase 3 已完成** (2026-04-14)：stats/check + relation normalization + CSV/Excel review aid
  - ✅ **归档审计完成** (2026-04-14)：见 `.strategy/cli/Round_7_Audit.md`

- **Round 8**：准备阶段
  - 参考：`.strategy/cli/Round_8_TDD_prep.md`

当前 v1.x 的现实状态：
- **主路线已完成**
- **历史执行记录已归档到 `.strategy/cli/archive/`**
- **当前活跃执行计划为 `.strategy/cli/TDD.md`（Round 7）**

### 3.1 搜索质量修复（P0，最高优先级）

**代码审计发现的具体病因**：

**"漏网之鱼"根因**：

| # | 根因 | 严重度 | 修复方案 |
|---|------|--------|---------|
| 1 | Embedding 模型 `MiniLM-L12-v2` 只取前 128 tokens，长日志后半部分搜不到 | **P0** | 换 `bge-m3`（8192 tokens，中英文更均衡）**[已决策：选定 bge-m3，不做 chunking]** |
| 2 | FTS 多词查询默认 OR 展开，语义搜索不分词，两管道对查询理解不一致 | P1 | 对齐查询理解逻辑 |
| 3 | `FTS_MIN_RELEVANCE = 25` 过早丢弃低分命中 | P1 | 动态阈值（基于结果分布） |

**"结果太多"根因**：

| # | 根因 | 严重度 | 修复方案 |
|---|------|--------|---------|
| 1 | 多词 OR 展开导致召回爆炸 | **P0** | AND-first、OR-fallback |
| 2 | 语义阈值 0.15 太宽松 | P1 | 提高到 0.25 或换模型后重标定 |

**执行顺序**：换 embedding 模型（bge-m3）→ 一次性全量重建向量索引 → FTS AND-first → 阈值重标定（Agent 从真实日志构建测试集 + 用户审阅）→ 动态阈值 → 回归测试

### 3.2 Entity Graph（实体注册 + 别名解析 + 关系图谱）

**问题**：用户人生中的实体有多个名字和复杂关系。"团团的奶奶" = "妈妈" = "婆婆"。Agent CLI 用户靠 Agent 碰巧从上下文推理，但不稳定。v2.0 完全无法依赖。

**方案**：`~/Documents/Life-Index/entity_graph.yaml`（YAML SSOT + SQLite 缓存，和 L2 metadata 同 pattern）

覆盖实体类型：`person` / `place` / `project` / `event` / `concept`

搜索时做 entity resolution + query expansion：
```
"团团的奶奶在老家" → mama(aliases) AND chongqing(aliases)
```

维护方式：写入时自动检测新实体 + 定期 Agent 审阅 + 用户手动编辑。

详见 `.strategy/cli/archive/PHASE-OVERVIEW.md` 阶段 2。

### 3.3 写入功能增强（为 v2.0 打数据基础）

| 增强 | 说明 | 为什么现在做 |
|------|------|-------------|
| **结构化情感字段** | `sentiment_score`（-1.0~1.0）、`themes` | 心理分析需要时间序列数据，回填成本远高于写入时生成。**LLM 策略：在线优先，离线 = 留空（不做规则降级），减少 CLI 复杂度，未来 Agent 可搜索降级日志批量回填** |
| **实体引用** | `entities` 字段引用 entity_graph 中的 ID | 日志与实体的精确关联 |
| **日志修订历史** | edit 时旧版本保存到 `.revisions/` | 数字人格需要思想变化轨迹。**存储位置：co-located（`YYYY/MM/.revisions/`），与日志同级，备份/迁移时自动跟随** |
| **新实体检测** | 写入后检测未注册实体，提示补充到 entity_graph | 保持 entity_graph 鲜活 |

### 3.4 Tool Schema 标准化

为每个 CLI 工具创建 `schema.json`（JSON Schema 格式）。包含新增的 `entity` 子命令。这是 v2.0 调用 CLI 的接口契约。

### 3.5 清理与发布

- 从 v1.x 主仓中剥离旧 Web GUI / 原型遗留物，确保远端 `life-index` 保持 CLI 纯净；历史资产仅保留在本地备份或独立 GUI 工作线中
- 保持 CLI 的 agent-first 纯粹性
- 完善 README，兑现最初承诺
- 发布为独立可用的极客工具
- **PyPI 发布降优先级，不阻塞工程进度**

### 3.6 技术决策备忘

**Rust**：不跟风。I/O bound + LLM latency bound，Python 最优。

**MCP**：CLI 版不需要。Agent IDE 直调 CLI 最高效。

**图数据库**：不需要。实体量级 ~2000，YAML + SQLite JOIN 绰绰有余。v2.0 Phase 3 如需复杂多跳推理，YAML 可直接导入图数据库作为种子数据。

---

## 4. v2.0 Experience Layer 路线（CLI 完成后全力投入）

> **目标**：不是"做一个 Web GUI"，而是做一个 **让人第一眼就说"卧槽"的体验**。

### 4.1 产品定位

> Life Index v2.0 是一座数字化的 **人生档案馆**，拥有纪念碑谷般的视觉品质和风之旅人般的情感温度。它让你的人生碎片变成一部可以回溯、可以对话、可以传承的活档案。

### 4.2 设计标杆

| 参考 | 借鉴什么 |
|------|---------|
| **纪念碑谷** | 寓言美学、色彩叙事、每一帧都是壁纸 |
| **风之旅人** | 情感留白、氛围动画、陪伴感 |
| **禅意/寓言** | 安静、克制、有层次有回味的交互 |
| **独立游戏** | 美术和交互作为核心体验，不是装饰 |

### 4.3 功能按爆款潜力排序

> **原则**：用户冲击力优先。从"第一眼心动"到"不可替代"渐进。

#### Phase 1 — "第一眼心动"（冷启动 + 传播力）

用户打开就被震撼，截图即传播。**不需要用户先积累大量日志。**

| 功能 | 用户冲击力 | 技术依赖 | 说明 |
|------|-----------|---------|------|
| **纪念碑谷级 UI/UX** | 极高 | 美术设计 | 每个界面都是作品级别，氛围感、禅意 |
| **社媒回溯导入** | 极高 | OAuth + 爬虫 | 授权后自动导入微博/朋友圈/Twitter 历史，Day 1 就有内容 |
| **照片 EXIF 时间线** | 高 | EXIF 解析 | 手机/相机照片自动归档，人生每一刻有迹可循 |
| **精美时间轴可视化** | 极高 | D3.js/Three.js | 动画化呈现记录时间轴、热词云、人物关系 |

**Phase 1 的核心指标**：用户打开后的前 30 秒体验。

#### Phase 2 — "越用越深"（留存 + 价值感知）

用户开始感受到"这个东西理解我"。**需要 ~50-100 篇日志。**

| 功能 | 用户冲击力 | 技术依赖 | 说明 |
|------|-----------|---------|------|
| **智能搜索 + 归纳建议** | 中高 | Agent-as-Backend | "去年这个时候你在做什么" → 综合回答 |
| **关联推荐** | 高 | 语义搜索 + related_journals | 写完日志自动推荐"你可能想回顾的过去" |
| **个人回忆录自动撰写** | 高 | LLM + 全量日志 | Agent 自动将碎片编织成叙事 |
| **情绪趋势仪表盘** | 高 | sentiment_score 时间序列 | 可视化你的情感变化曲线 |

**Phase 2 的核心指标**：周留存率、日志记录频率。

#### Phase 3 — "不可替代"（终极壁垒）

迁移成本极高。**需要 ~300-500 篇日志。**

| 功能 | 用户冲击力 | 技术依赖 | 说明 |
|------|-----------|---------|------|
| **数字人格问答** | 极高 | MCP + 全量 RAG + Persona | "爸爸会怎么看这件事？" |
| **人格画像分析** | 高 | LLM + 情感/主题时序 | 你的价值观、性格特征、思维模式 |
| **心理健康评估** | 中高 | 需要专业审慎 | 情绪模式识别、温柔的反思引导 |
| **人生群像** | 高 | 知识图谱 + 可视化 | 人物关系网络、事件脉络、人生章节 |

**Phase 3 的核心指标**：NPS（净推荐值）、用户故事传播。

### 4.4 v2.0 架构设计

```
┌─────────────────────────────────────────────┐
│  v2.0 Experience Layer                      │
│                                             │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ Visual UI   │  │ Feature Modules      │  │
│  │ (禅意设计)   │  │ ┌──────────────────┐ │  │
│  │             │  │ │ 时间轴可视化      │ │  │
│  │ React/Svelte│  │ │ 社媒导入         │ │  │
│  │ + Three.js  │  │ │ EXIF 解析        │ │  │
│  │ + D3.js     │  │ │ 回忆录生成       │ │  │
│  │             │  │ │ 数字人格         │ │  │
│  │             │  │ │ ...              │ │  │
│  └──────┬──────┘  └────────┬─────────────┘  │
│         │                  │                │
│  ┌──────▼──────────────────▼──────────────┐ │
│  │  Agent Runtime (Agent-as-Backend)      │ │
│  │  LLM + Tool Calling + Tool Schemas    │ │
│  └──────────────────┬────────────────────┘ │
└─────────────────────┼──────────────────────┘
                      │ 调用
┌─────────────────────▼──────────────────────┐
│  v1.x CLI Tools (SSOT)                     │
│  write / search / edit / abstract / index  │
└─────────────────────┬──────────────────────┘
                      │ 读写
┌─────────────────────▼──────────────────────┐
│  ~/Documents/Life-Index/                   │
│  Markdown + YAML (永久可读)                 │
└────────────────────────────────────────────┘
```

**技术栈方向**（v2.0 仓库独立选型）：

| 层 | 候选 | 理由 |
|---|------|------|
| 前端框架 | Svelte / React | 动画性能、组件生态 |
| 可视化 | D3.js + Three.js | 时间轴、3D 效果、粒子动画 |
| 后端 | Python FastAPI（复用）或 Node.js | Agent SDK 集成 |
| Agent Runtime | Anthropic SDK / Agent SDK | Tool Calling 自动编排 |
| 协议层 | 初期直调 CLI → 后期 MCP | 按需演进 |

### 4.5 MCP 的时机

MCP 在 v2.0 的 **Phase 3** 自然出现——当数字人格、心理咨询、知识图谱等多个智能模块需要并行访问 CLI 工具时，MCP 从"大炮打蚊子"变成"必需品"。

不需要提前规划 MCP。Phase 1-2 用 Agent-as-Backend 直调 CLI 即可。

### 4.6 当前现实状态（2026-04-12）

- life-index_gui/ 本地工作目录已建立，且已形成可运行的 React 19 + Vite 6 + Tailwind 4 GUI 工程
- GUI 共享战略入口已接入 .strategy/
- gui/PHASE-OVERVIEW.md、gui/GUI_ARCHITECTURE.md、gui/phase-1/TECH-STACK.md 已存在
- 当前更准确的表述应是：**GUI 已完成 Phase 1 工程骨架与核心体验实现，并形成首轮视觉验收记录；当前处于首页 / 全局壳层持续视觉打磨、加载与过渡收口、以及文档校准阶段，而非纯预研阶段**
- 需要特别说明的是：The Core 与全局壳层已进入高保真打磨阶段，但 Recall / Archives / Journal Detail 仍有占位实现尚未完全替换为真实集成，不应在顶层文案中被误表述为“所有页面 fully complete”

---

## 5. 执行节奏

```
         NOW                                          v1.x done      v2.0 Phase 1
          │                                              │                │
v1.x ════╪══ 搜索修复 ══ Entity Graph ══ 写入增强 ══ Schema ══ 清理发布 ═╗
          │                                                          ║ 维护模式
v2.0     │                                                          ╠══ Phase 1 ══ Phase 2 ══ Phase 3 ═→
          │                                                          ║  第一眼心动   越用越深    不可替代
          ▼                                                          ▼
     全力 v1.x CLI                                              全力 v2.0 体验
```

**关键决策**：
- v1.x 快速完善后转入维护模式，不再加新功能
- v2.0 在独立工作目录中推进，技术栈独立选型
- 两条线共享同一份用户数据（`~/Documents/Life-Index/`）
- v2.0 通过 v1.x CLI 的 Tool Schema 调用底层能力

---

## 6. 不变的原则

- **CLI 是 SSOT** — v2.0 的所有写入必须经过 v1.x CLI
- **本地优先** — 用户数据永远在本地，永远是 Markdown
- **品味 > 功能** — 宁可少一个功能，不可降低一帧的视觉品质
- **终局思维** — 每一个发布的界面都必须是终局品质，不是"先凑合再迭代"
- **Python 为 CLI 主语言** — v2.0 前端可自由选型

---

## 7. FAQ

**Q: 旧 Web GUI / 原型资产现在怎么处理？**
远端 `life-index` 主仓不再承载这类历史 GUI 资产，保持 CLI 纯净。需要保留的内容只作为本地备份、迁移参考，或沉淀到独立 GUI 工作线中；实现思路可以参考，但不直接复用旧代码。

**Q: 为什么不直接在现有仓库做 v2.0？**
技术栈不同（Python CLI vs 现代前端框架）、发布节奏不同、用户群体不同。分离仓库让两条线各自纯粹。

**Q: v2.0 需要 MCP 吗？**
Phase 1-2 不需要（Agent-as-Backend 直调 CLI）。Phase 3 多智能体场景出现时自然引入。

**Q: Rust/Go？**
不跟风。CLI 是 I/O bound，Python 最优。唯一例外：10 万+ 日志后向量索引瓶颈可以用 Rust binding 局部优化。

**Q: 搜索还需要知识图谱吗？**
v1.x 引入轻量级 Entity Graph（`entity_graph.yaml`），覆盖人物/地点/项目/事件/概念的别名和关系。YAML SSOT + SQLite 缓存，不引入图数据库。v2.0 Phase 3 如需复杂多跳推理，YAML 直接导入图数据库作为种子。

**Q: 为什么叫 entity_graph 而不是 knowledge_base？**
`entity_graph` 精确传达"实体 + 关系网络"的含义，`knowledge_base` 过于宽泛。`graph` 也暗示了可视化和关系遍历能力。

**Q: LLM 离线时 sentiment/themes 怎么办？**
**留空，不做规则降级。** 理由：(1) 规则降级增加 CLI 复杂度但效果差；(2) 留空后 Agent 可通过搜索降级日志批量回填，数据质量更高。这是全局 LLM 策略（Q10），所有 LLM 依赖功能统一执行。

**Q: PyPI 发布优先级？**
**降优先级。** 包名 `life-index`、Apache 2.0、中文 README。发布是锦上添花，不阻塞工程进度。

**Q: 向量索引升级时怎么迁移？**
**一次性全量重建。** 日志 ~200 篇，全量重建仅需数分钟。不做增量迁移（复杂且易出错）。

---

## 8. 参考文档

| 文档 | 关系 |
|------|------|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | v1.x 核心架构，v2.0 尊重其 SSOT 原则 |
| [PRODUCT_BOUNDARY.md](../PRODUCT_BOUNDARY.md) | v1.x 产品边界定义 |
| [API.md](../API.md) | Tool Schema 应与其一致 |
| [AGENTS.md](../../AGENTS.md) | CLI 开发约束 |

---

*本文档记录架构演进方向与战略决策。当前状态：CLI 已完成 Round 7 并进入 maintenance / Round 8 准备阶段；GUI 已完成 Phase 1 工程骨架与核心体验落地，并处于持续视觉打磨 / 文档收口阶段；双产品线共享 .strategy/ 统一治理。*
