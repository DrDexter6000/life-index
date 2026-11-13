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
| 召回优先检索真实模型（L2 default keyword-only） | CHARTER §1.11 |
| 设计三底线（简单/人工/可靠） | CHARTER §1.7 |
| 交互范式（人-Agent-CLI 三层信息流） | CHARTER §1.3 + §2 |
| 系统边界（做什么 / 不做什么） | CHARTER §1.7 + 第四章反模式黑名单 |
| 数据隔离（用户数据 vs 代码） | CHARTER §1.1 |
| 运行时/平台可移植性（换 runtime/OS 只改配置不改代码） | CHARTER §1.12 |

**本文档聚焦可演化的实现细节** — 索引树结构、分层搜索参数、ADR-003/004/005 等可演化决策、目录快照、基础设施增量记录。这些随实现版本迭代，不属于宪章不变量。

<!-- PLATFORM-SSOT:CURRENT-TARGET-STATUS:START -->
### Platform program: current runtime vs ratified target

Current runtime: direct CLI/Core contracts are the implemented canonical public
route. The accepted `--synthesize` flag follows the deterministic no-LLM/no-answer
contract named below, and the current bridge is non-Core and GUI-owned. The
design memo is not an authority or SSOT. The exact closed Core admission domains
in `CHARTER.md §1.10` are active Charter authority, and the former §1.9 direct
provider-fallback direction is superseded: Host Agent + Skill own provider
selection and intelligence.

The D4 runtime is accepted: it includes direct CLI/Core plus an optional,
exact-pinned and lazily loaded, generic MCP projection with exactly `health`,
`journal.get`, and `search`. That projection is generated from the closed
registry, remains removable and non-authoritative, and does not replace the
direct CLI/Core route.

The original D5 hand-written newline-JSON-RPC transport is Human-Owner
**DEFERRED / NOT NECESSARY NOW**. It remains unnecessary unless a named non-MCP
consumer or a verified incompatibility establishes a need.

D6-A is release-readiness only; no D6-A merge, release, or publication has
occurred. See [`docs/VERSIONING.md`](./VERSIONING.md) for CLI maturity and release
semantics.
<!-- PLATFORM-SSOT:CURRENT-TARGET-STATUS:END -->

<!-- PLATFORM-SSOT:PLATFORM-ROLE-BOUNDARY:START -->
### Platform role boundary

| Role | Authority boundary |
|---|---|
| Core | Deterministic tools; no planning, reasoning, orchestration, interpretation, or synthesis. |
| Host Agent + Skill | Owns planning, multi-hop reasoning, orchestration, interpretation, and synthesis. |
| GUI | Presentation only; no intelligence; strict adapter stays GUI-owned. |
| Current bridge | Non-Core and GUI-owned. |
| Core Capability Gateway | Optional implemented generic typed 1:1 projection under #164; not a second semantic API; no intelligence. |

The table above is the sole normative role-assignment surface in this block.
The optional Core Capability Gateway is only a contract-equivalent transport of
Core operations. It cannot create a parallel semantic contract, and direct Core
use does not depend on it. The active closed admission-domain catalog belongs
only to `CHARTER.md §1.10`; this document references the Charter's closed Core
admission domains without duplicating their domain descriptions.
<!-- PLATFORM-SSOT:PLATFORM-ROLE-BOUNDARY:END -->

Structured write-input projection: `CHARTER.md §2.3` is the sole authority.
Host Agents translate natural language and GUI collection/edit surfaces emit the
same structured arguments; Core deterministically honors non-empty trimmed
`location` / `weather`, applies defaults only to missing fields, and leaves
marker-like journal body lines uninterpreted and verbatim.

<!-- PLATFORM-SSOT:ADVANCED-ADDON-DUAL-CHANNEL:START -->
### Future advanced Addon dual-channel boundary

This is normative guidance for future advanced Addons, not an implemented Addon
contract, SDK, runtime, schema, or UI. An advanced Addon is composed of a
presentation layer, a Domain Skill, and, only when needed, an optional
deterministic helper.

```text
User <-> Addon presentation
           |-- deterministic data/view/atomic operation
           |     -> Core Capability Contract
           |        -> direct local CLI or optional Core Capability Gateway projection
           |           -> Core -> L1
           |-- semantic understanding/multi-step retrieval/orchestration/interpretation/synthesis
                 -> shared Host Agent Handoff
                    -> Host Agent + Life Index Skill + Domain Skill
                       -> Core Capability Contract for deterministic evidence/operations
```

#### Access paths

| Need | Required path | Boundary |
|---|---|---|
| Deterministic data, view, or atomic operation | Addon presentation/helper -> Core Capability Contract | May call the local CLI directly or use a contract-equivalent Core Capability Gateway projection; no Host Agent round trip is required. |
| Semantic understanding, multi-step retrieval or orchestration, interpretation, or synthesis | Addon presentation -> shared Host Agent Handoff -> Host Agent + Life Index Skill/Domain Skill | The Host Agent owns intelligence and uses the Core Capability Contract for deterministic evidence and operations. |

#### State ownership

| State | Owner | Rule |
|---|---|---|
| Canonical durable journal, frontmatter, entity, index, and metric state | L1/L2 through Core | Addons and Host Agents never create a second truth source or bypass Core. |
| Reasoning, orchestration, and agent-session state | Host Agent/runtime | It remains outside Core and is not owned by the Addon presentation or helper. |
| Presentation and user-visible draft state | Addon | It is non-canonical, replaceable, and cannot become a Core correctness dependency. |
| Optional deterministic-helper state | Addon unless admitted to Core | It remains local, non-canonical, clearable, and cannot read or write L1 directly. |

#### Optional deterministic-helper admission

| Candidate | Decision |
|---|---|
| Already covered by the Charter's closed Core admission domains (`CHARTER.md §1.10`) | Consume the canonical Core capability; do not duplicate it in the Addon. |
| Satisfies every already-ratified admission constraint and belongs within the closed Core admission domains, or receives new Human Owner substantive approval for the required authority expansion | Propose Core admission through the existing RFC/substantive-gate process; determinism and all non-waivable constraints still apply. |
| Does not satisfy those conditions | Keep it Addon-local and non-canonical. |
| Performs semantic understanding, orchestration, interpretation, or synthesis | It is not a deterministic helper; route it through the shared Host Agent Handoff and Host Agent + Skills. |

#### Prohibitions and gateway distinction

- An Addon must not own an LLM, provider selection, API-key handling, or an agent runtime.
- An Addon and its helper must not bypass Core to read or write L1, duplicate a canonical Core capability, or duplicate runtime adapters.
- A Core Capability Gateway is only a typed transport projection of the canonical Core Capability Contract. It is not an Agent Runtime Gateway, Host Agent, Life Index brain, reasoning or session owner, or provider boundary.
- The local CLI remains a canonical direct Core consumer surface. A Core Capability Gateway is optional and cannot become mandatory for direct Core use or replace the CLI.

Advanced Addon implementation, its SDK and schemas, placeholder UI, and later
program phases remain deferred. This boundary does not claim that any such runtime
surface exists.
<!-- PLATFORM-SSOT:ADVANCED-ADDON-DUAL-CHANNEL:END -->

<!-- PLATFORM-SSOT:PUBLIC-COMMAND-CLASSIFICATION:START -->
### Public command constitutional ownership/admission mapping

| Command | Classification | Authority refs |
|---|---|---|
| abstract | Core | C3 |
| aggregate | Core | C4 |
| analyze | Core | C4 |
| attachment | Core | C3 |
| backup | Core | C6 |
| bootstrap | Non-Core — Distribution/Host Operations | Distribution/Host Operations |
| confirm | Core | C1, C2 |
| edit | Core | C1, C2 |
| entity | Core | C5 |
| entity-graph-eval | Core | C5, C7 |
| eval | Core | C7 |
| generate-index | Core | C3 |
| health | Core | C6 |
| import | Core | C1, C2 |
| index | Core | C3 |
| index-tree | Core | C3 |
| journal | Core | C3 |
| maintenance | Core | C2, C6 |
| migrate | Core | C2 |
| on-this-day | Core | C3 |
| recall | Core | C3 |
| search | Core | C3 |
| smart-search | Core | C3 |
| sync-skill | Non-Core — Distribution/Host Operations | Distribution/Host Operations |
| timeline | Core | C3 |
| trajectory | Core | C4 |
| upgrade | Non-Core — Distribution/Host Operations | Distribution/Host Operations |
| verify | Core | C6 |
| version | Non-Core — Distribution/Host Operations | Distribution/Host Operations |
| weather | Legacy External Adapter | #166 |
| write | Core | C1, C2 |

This table is the exhaustive current route mapping under the Charter-owned
closed Core admission domains and stable non-Core classification rules in
`CHARTER.md §1.10`.
It maps current routes only; it does not own or duplicate those stable rules.
<!-- PLATFORM-SSOT:PUBLIC-COMMAND-CLASSIFICATION:END -->

<!-- PLATFORM-SSOT:EVAL-LLM-DEVIATION:START -->
### Eval language-judge compatibility boundary

`eval` remains Core under C7. The public command classification is a
constitutional ownership/admission map, not a certification that every current
route or option complies.

Current runtime: the product CLI recognizes `life-index eval --judge llm` but
returns a stable non-success result before evaluation, configuration reading,
or provider-module import. It does not silently fall back to keyword and does
not claim a language-assisted evaluation ran.

Production `tools/eval` contains only deterministic C7 measurement and
serialization behavior; language-assisted evaluation belongs to Host Agent +
Life Index Skill. The A5 candidate does not close #163 or complete D1-A before
review and adjudication.
<!-- PLATFORM-SSOT:EVAL-LLM-DEVIATION:END -->

---

## 1. 分布式索引树架构

### 1.1 索引树结构

索引文件与数据物理共存。Canonical agent navigation 使用
`.life-index/index-b/`；旧的 `INDEX.md`、`index_YYYY.md`、`index_YYYY-MM.md`
和 `by-topic/` 文件保留为兼容生成物，不再是 host-agent 主导航面：

```
~/Documents/Life-Index/
├── .life-index/
│   └── index-b/                          ← canonical deterministic navigation
│       ├── INDEX.md
│       ├── Journals/2026/index.md
│       ├── Journals/2026/03/index.md
│       └── manifest.json
├── INDEX.md                              ← legacy generated root index
├── Journals/
│   ├── 2026/
│   │   ├── index_2026.md                 ← 年度索引：全量元数据聚合 + 月份指针
│   │   ├── 01/
│   │   │   ├── index_2026-01.md          ← 月度索引：逐条全量元数据 + 回顾 placeholder
│   │   │   └── life-index_2026-01-05_001.md
│   │   └── 03/
│   │       ├── index_2026-03.md          ← `life-index abstract --month 2026-03`
│   │       └── life-index_2026-03-04_001.md
│   └── 2025/
│       └── index_2025.md
├── by-topic/                             ← legacy compatibility indexes
│   ├── 主题_work.md
│   └── ...
└── .index/                               ← 机器检索层（FTS5 + 元数据缓存）
```

### 1.2 确定性边界线

| 内容类型 | 归属工具 | 所在层级 |
|---------|---------|---------|
| 条目表格行 + frontmatter 聚合 | `generate_index`（确定性） | CLI Core |
| 年度/月度回顾段 | `generate_report`（Agent 驱动） | Intelligence Layer |
| legacy by-topic 摘要文字 | `generate_index`（确定性） | CLI Core |

`generate_index` 生成的文件中，叙事区域留 placeholder。`generate_report` 是 Agent 编排任务，不是 Python CLI 工具。此划分对应 CHARTER §1.5 的「确定性 vs 智能」硬线。

日、月、年整理稿是叙事层的权威载体：由 Host Agent 撰写并署名，Core 原样保存、核对结构、列出所覆盖的碎片并保留版本（CHARTER §1.10 C1 范围说明）。待实现。

### 1.3 渐进式元数据披露

.life-index/index-b/INDEX.md < .life-index/index-b/Journals/YYYY/index.md < .life-index/index-b/Journals/YYYY/MM/index.md

每层 Index B 文档是其覆盖时间段的确定性 facet 聚合体，Agent 可先读根/年/月导航文档，
再用 `discover` / `navigate` 取得有界候选集。旧 generated index 仍可读，但不作为
agent playbook 的结构化导航入口。

### 1.4 未来兼容性基线（ADR-026）

Index Tree 的长期定位不只是浏览辅助，而是面向 10/20/50 年日志的导航基座：它应支持 long-running L3 模块做候选缩小、层级下钻、进度定位、checkpoint/resume 锚定与证据包组织。

该方向不要求立即实现人格分析、数字家书、数字人格等高级模块；这些是终局压力测试，不是当前路线图承诺。L1/L2 需要优先固化的是稳定 CLI contract、Evidence Pack / Claim Envelope、可导航 Index Tree、batch/cursor/pagination、addressable intermediate artifacts 与 eval contract。

Index B 的 facet navigation 是确定性执行器。`topic` 与 `weather` 直接来自 journal
frontmatter；`project`、`people`、`location` 与 `tag` 可用用户数据目录内
`entity_graph.yaml` 的显式 `primary_name` / `aliases` 规范化到 canonical value。该规范化
不做语义推断、不调用 LLM、不猜测未登记同义词；歧义 label fail-closed，图谱加载失败则
降级 no-op 并报告诊断。Index B manifest 记录规范化后的 alias-map hash，alias-map 变化会让
相关 scope stale，以便重建后的导航文档与 runtime discover/navigate 保持一致。
同一进程内 `load_entity_graph(path)` 以 resolved path + 文件 `(mtime_ns, size)` 记忆已验证的
解析结果；文件变化或消失即重新解析，返回给调用方的是独立深拷贝，调用方原地修改不会污染
memo。`save_entity_graph` 写入后同步更新该 memo。

L2 仍不得调用 LLM，也不得实现或存储 ADR-026 所列 persona interpretation、emotion interpretation、relationship judgment、narrative synthesis、digital letters、creative emulation、cross-journal LLM reasoning 等解释性能力或结论。L3/L4 模块若消费 L2 输出做解释或创作，必须保留证据、限制与 provenance。本条禁止的是 Core 自己形成解读，或把解读当作自己的结论保存。原样保存 Host Agent 提交并署名的整理稿（CHARTER §1.10 C1 范围说明）不在此列；整理稿在任何消费面上都不得被当作用户本人的原文。

### 1.5 模块-基础层契约边界（CHARTER §1.10 实现镜像）

CHARTER §1.10 将「模块-基础层契约边界」提升为不变量。本节记录实现侧对应原则，不重复宪章全文：

**模块消费面**：L3/L4 模块应通过以下方式消费 L2 基元，不直接读写 L1 文件：
- CLI JSON-in/JSON-out（`python -m tools.{tool_name}`）
- Python import of `tools.*` 公开 API（以模块方式调用，不假设内部实现细节）

**稳定契约维度**（模块可信赖的四维契约）：
- **JSON shape**：返回结构的顶层字段名称与类型。错误返回统一包含 `success`/`error`；成功返回采用工具自定义顶层字段 + `error: null`，不假设 universal `data` wrapper
- **字段语义**：每个字段的精确含义（如 `result.exactness` 的 `exact`/`approximate`/`not_measurable` 枚举）
- **错误码**：`E{module}{type}` 分类与 `recovery_strategy` 语义
- **关键 SLO**：`search` p95 ≤ 500ms；`smart-search` 默认路径 p95 ≤ 8s；公开合成 Core assertion 必须执行并通过，本地 / 私有 eval 始终 advisory

**模块状态目录原则**：
- 模块-local 过程状态（cursor、checkpoint、run_id 索引、模块自有 wiki/router/tree）应存放在模块安装目录下
- **不得**在 `~/Documents/Life-Index/` 下创建可写模块路径（CHARTER §1.1）
- 模块-local 状态属于「机器副产物」类别，与 `.index/` 同级概念：可清除、可重建、不进入 L1 真相源

**基元升格回流**（防止 over-stuffing vs over-delegation）：
- 当多个模块在生产路径上重复需要某项基元、某项基元明显具备跨模块复用价值，或开发者/用户明确判定其具备长期基础价值时，可通过 RFC 流程提议将其升格为 L2 CLI 原语；升格候选仍必须满足确定性、低 LLM 含量与 50 年语义稳定性
- 不满足四条任一项 → 留在模块本地
- CLI core 不得提前实现尚无真实消费者的工作流原语（YAGNI）

**热插拔的工程含义**：
- 模块可以是独立仓库、独立目录、独立 Python 包
- 不引入 plugin loader / dynamic discovery / entry-point registry（CHARTER §1.10 明确禁止）
- 模块与 CLI core 的耦合面仅限于上述「稳定契约四维」

> **实现状态**：当前尚无正式的高级模块（Memoir Engine、心潮地图等仅存在于路线图/远景）。本节作为架构契约占位，供未来模块开发时引用。可导航 Index Tree 与 addressable intermediate artifacts 是 §1.10 的具体实现 anchor。面向模块作者的具体消费/状态/升格契约以本文档与 `docs/API.md` 的公开契约为准。

---

## 2. 分层搜索架构

> **2026-06-28 §1.11 收紧后的对齐说明**：CHARTER §1.11 把 L2 检索收紧为 keyword + Entity Graph。`--semantic*` flags 保留为 deprecated compatibility no-op；L2 不再构建向量索引、加载 embedding 模型或执行 semantic fallback。详见 WP-CLI-SEM-RM。

**2026-06-28 搜索架构共识**：早期文档中的“关键词 + 语义双管道”已经废弃。当前搜索系统应理解为四层 stack：

| Stack | 所在层 | 责任 | 当前状态 |
|:---:|:---:|:---|:---|
| **S0 记录与索引基座** | L1/L2 | Markdown + YAML、FTS5、metadata cache、`entity_graph.yaml`；全部可由本地数据重建 | 已落地 |
| **S1 确定性检索与排序** | L2 | `life-index search`；关键词精确匹配、时间/主题过滤、Entity Graph 确定性扩展/加权；`--semantic*` 兼容 no-op | 官方质量门 |
| **S2 智能搜索编排** | L3 | `life-index smart-search` 默认路径输出 agent-ready 确定性检索 scaffold；意图识别、query expansion、有界多轮 search 调用、结果精筛/摘要由宿主 agent 与 Skills 完成 | v1 contract；当前例外与 #163 目标见下方命名块 |
| **S3 高级应用模块** | L3/L4 | 心理诊断、人格判断、数字人格、数字家书、家训提炼等领域编排 | 远景模块 |

<!-- PLATFORM-SSOT:SMART-SEARCH-CURRENT-CONTRACT:START -->
### Smart-search current contract

- Default/no-flag `life-index smart-search` returns a deterministic scaffold.
- Current explicit `--synthesize` is accepted for at least two major versions. The product CLI constructs `SmartSearchOrchestrator()` with no injection surface, emits no `answer`, and preserves the ordinary deterministic domain payload.
- The CLI emits exactly one stderr warning: `DEPRECATED: --synthesize is a compatibility no-op; synthesis belongs to the Host Agent + Life Index Skill.`
- Search/smart-search production packages contain no dormant/injectable LLM rewrite, filter, provider, prompt, trust-gate, or synthesis implementation; the Tier 1 no-LLM hard check enforces the documented static structural policy over these production roots.
- A5 extends the deterministic-only boundary and structural scan to product eval; #163 remains open pending review, so D1-A is not complete.
- Host Agent + Skill remain the intelligence owner; #163 does not change that role boundary.
<!-- PLATFORM-SSOT:SMART-SEARCH-CURRENT-CONTRACT:END -->

> S3 高级模块示例是终局压力测试，不是当前路线图承诺；其 L1/L2 地基要求见 ADR-026。

**核心原则**：
- 关键词检索的首要目标是精确、少噪音，是当前 eval gate 的官方口径（keyword/default）。
- 向量/语义检索已从 L2 原子工具移除。仓库外 operator eval 未证实可验证的 recall 增益；私有查询、计数、指标与失败样本不进入公开权威。继续维护模型下载、索引和 fallback 会增加复杂度但不增加质量。
- Entity Graph 是 S1 的 active serving layer，必须参与 retrieval/ranking、query expansion 与关系短语解析，不只是可视化数据源。
- LLM 的合法位置是宿主 agent / Skills：进入检索前做搜索编排，检索后做过滤/摘要/解释；`smart-search` 默认路径输出确定性检索 scaffold、`agent_instructions`、`answer_scaffold` 与 `query_plan`，当前显式例外与 #163 目标见上方 `SMART-SEARCH-CURRENT-CONTRACT` 命名块。LLM 不得绕过 CLI Core 直接读写 L1 数据。
- 高级模块必须建立在稳定记录格式、结构化检索、Entity Graph 增强与宿主 agent 编排之上。

以下图示仅描述 S1 的 CLI Core 检索基座内部结构。

**核心目的**: 逐层缩小候选集以节省 Agent 上下文 token 消耗。

```
                    用户查询
                      │
              L0: 索引树预过滤（可选）
              --year / --month / --topic
              缩小候选集为布尔集（不产生分数）
                      │
              ┌───────▼───────┐
              │ Pipeline A    │
              │ 关键词+结构化  │
              │ L1 filter     │
              │ L2 filter     │
              │ L3 FTS5       │
              └───────┬───────┘
                      │
                 排序结果返回
```

旧 `--semantic-policy` / `--semantic-weight` 参数仅作为兼容 no-op 接受，不改变上述执行路径。

| 层级 | 数据来源 | 返回内容 | 设计意图 |
|:---:|:---:|:---:|:---|
| **L1 导航层** | `.life-index/index-b/` facet docs + manifest | facet 计数、raw values、entry pointers | 按 topic/project/tag/location/people/weather 快速缩小候选集 |
| **L2 元数据层** | YAML Frontmatter（SQLite 缓存） | 全部元数据（~500字节/篇） | 按日期、心情、人物等多维度过滤 |
| **L3 内容层** | FTS5 全文索引 | 匹配片段+上下文（~300字节/条） | 关键词精确匹配，返回段落而非全文 |
| **Entity Graph 层** | `entity_graph.yaml` 显式 primary/alias/relationship | expansion terms、entity hints、确定性加权 | 用用户登记的稳定别名和关系增强关键词检索，不做同义词猜测 |

**核心原则**：每一层是过滤器，不是数据源。关键词+结构化检索内部执行递进过滤：L1 导航层快速预筛（Index B facet docs + manifest），L2 元数据层多维度过滤（YAML Frontmatter + SQLite 缓存），L3 FTS5 内容层精确匹配，并通过 Entity Graph 使用显式别名/关系增强召回与排序。Paraphrase、概念扩展和综合解释由宿主 agent 通过多次确定性调用完成。

> 以上检索基座是 **S1 确定性检索原语**，零 LLM 依赖。Agent 编排层（query understanding、multi-pass search、result filtering）仅可在 `tools/search_journals/orchestrator.py` 内出现，并属于 S2 智能搜索编排 —— 详见 CHARTER §1.5 与 §3。

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

> **编号说明（2026-05-25）**：本节是历史内联决策记录。历史 ADR/RFC 文件不再作为公开仓的活跃文档面；未来引用应限定为 `ARCHITECTURE.md inline ADR-004 (MCP migration)`。

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

**2026-07-02 解释性补充（thin MCP projection boundary）**:

ADR-004 禁止的是“把 MCP 当作新的产品接口或并行数据路径来迁移”，不是禁止所有 MCP 形态。一个薄 MCP 投影只有同时满足以下条件才是合宪的：

1. It is a **1:1 projection** of existing CLI commands and documented JSON envelopes.
2. It preserves the **CLI JSON contract** exactly: field names, schema-version policy, error behavior, and compatibility fields remain owned by `docs/API.md` and the CLI implementation.
3. It adds **zero new capability**: no new retrieval mode, no ranking change, no hidden planning/orchestration, no LLM/provider/client initialization.
4. It adds **zero new write path**: writes must pass through the same CLI command, lock, validation, audit, and data-boundary logic as direct CLI use.
5. **CLI remains the authority**: MCP may describe or invoke CLI tools, but must not become the contract owner for schemas, behavior, or persistence.

Therefore the existing `tools/mcp_discovery` discovery stub remains constitutional: it is static, read-only, and does not touch user data. It is separate from the implemented optional `tools.mcp_projection` stdio transport. That generic projection derives its exact `health`, `journal.get`, and `search` surface from `CAPABILITY_REGISTRY`, calls the canonical Core application functions, and has no independent schema or semantic authority. `search` is read authority with only the rebuildable `.index` derived-state allowance. No D5 hand-written newline JSON-RPC server is present; the optional official SDK owns stdio lifecycle. Any MCP implementation that diverges from CLI behavior, owns schemas independently, directly reads/writes the journal data directory, or adds in-tool reasoning/orchestration falls under CHARTER §4.1 “parallel interface” risk.

### ADR-005: AGPL-3.0-only distribution

> **Scope**: non-constitutional distribution rationale. This ADR does not amend
> the Charter, assign Core/non-Core ownership, or modify license terms.

**Decision**: Life Index is distributed as `AGPL-3.0-only`. The current
[`LICENSE`](../LICENSE) is legally controlling.

**Rationale**:

1. The local-first architecture keeps user data under user ownership rather
   than making an external service the data authority.
2. AGPL-3.0-only aligns modified network services and distributed versions with
   reciprocal source-availability obligations under the license's actual terms.
3. The same public license designation across the CLI, GUI, and curated GUI
   public export keeps the two-repository product surface aligned.

This is factual engineering and product rationale, not legal advice. It does
not alter, interpret beyond, or replace the license text.

**Authority boundary**: [`CONTRIBUTING.md`](../CONTRIBUTING.md) records that a
contributor grants the project owner a separate right to relicense that
contribution. That provenance reserves any separate-license or relicensing
decision to the Owner and applicable copyright holders; it gives agents and
contributors no relicensing authority.

---

## 4. 目录结构

```
~/Documents/Life-Index/           # 用户数据目录
├── .life-index/index-b/          # canonical deterministic navigation docs
├── INDEX.md                      # legacy generated root index
├── alfred.md                     # 档案馆管理员 Alfred 的档案（C8，待实现）
├── Journals/                     # 日志文件存储
│   └── YYYY/                     # 按年分层
│       ├── index_YYYY.md         # 年度索引
│       └── MM/                   # 按月分层
│           ├── index_YYYY-MM.md  # 月度索引
│           ├── life-index_*.md   # 日志原文
│           └── digest_*.md       # 日/月/年整理稿（待实现；命名以实现为准）
├── by-topic/                     # legacy compatibility indexes
│   ├── 主题_work.md
│   ├── 项目_Life-Index.md
│   └── 标签_重构.md
├── attachments/                  # 附件存储
│   └── YYYY/MM/
└── .index/                       # 机器检索层（FTS5 + 元数据缓存）
```

> 数据隔离（用户数据 vs 项目代码物理隔离）已提升为宪章 §1.1 不变量，见 CHARTER.md。

### 4.1 C8 文档清单（用户拥有的常设文档）

CHARTER §1.10 C8 管辖的文档逐份列在这里；新增一份须经 §5.2 实质门槛。

| 文件 | 内容 | 状态 |
|---|---|---|
| `alfred.md`（用户数据目录根） | 档案馆管理员 Alfred 的档案：人格设定、长期吩咐、待办；每条引用用户原话并指回所在碎片 | 待实现 |

Alfred 是档案馆管理员这个角色的名字。用户可以为它另设人格与称呼，文件名不变。

### 4.2 Journals/ 文件种类判定（journal file kinds）

`Journals/` 树下的每个文件由唯一的共享规则判定种类，实现于
`tools/lib/journal_files.py`（纯路径判定，不打开文件）：

| 种类 | 判定 | 说明 |
|---|---|---|
| `fragment` | `life-index_YYYY-MM-DD_<序号>.md` | 用户本人的日志原文（碎片） |
| `digest` | `digest_*.md` | 整理稿（Host-Agent 撰写并署名；待实现） |
| `derived_index` | `index_` / `monthly_` / `yearly_` 前缀 | 可重建的派生索引（与 backup 的 generated-artifact 规则同源） |
| `unknown` | 其他一切 | 不当作日志处理 |

规则要点：

- 点开头的目录（如 `.revisions/`）内的文件**绝不是**任何种类的 live 文件，
  枚举一律跳过；旧版本只经 `tools/lib/revisions.py` 读取。
- 所有遍历 `Journals/` 的工具**必须**使用 `journal_files.py` 的枚举助手；
  默认只返回 fragment，需要其他种类必须按名请求，顺序稳定。
- `tests/contract/test_journal_file_kinds_contract.py` 以源码扫描守护此规则：
  共享助手之外不允许出现可触及 Journals 树的 `*.md` 通配扫描
  （白名单精确到 文件 + 模式，仅限扫描其他目录的站点）。

### 4.3 Frontmatter 重写边界（frontmatter rewrite boundary）

**规则：任何工具在重写已有 frontmatter 之前，必须先证明它能把它原样写回。** 实现是
`tools/lib/frontmatter.py` 的 `frontmatter_rewrite_blocker(content)`：它用同一个
`parse_frontmatter()` 读出 mapping，再经 `format_frontmatter()` 序列化并重新解析；
只有重新解析得到的值（连同类型）与“序列化器本来就该写出的形态”一致才返回 `None`。
这个形态只允许序列化器有意做的三处规范化，它们都不丢失任何值：总是写出
`schema_version`；已知字段的值为 `null` 时不写这个字段；列表字段里的字符串写成按逗号
拆开的列表。否则返回一个 reason code：

- `unreadable`：带 `---` 区块但读不出 mapping root（list/scalar root、无法恢复的 YAML、
  递归结构）——重写会删掉用户写下的 YAML 文本。
- `not_round_trippable`：区块可读，但序列化器无法复现解析结果（非字符串键、`_` 开头的
  键、`!!set`、`!!pairs` 等）——重写会改写或丢失值。

这个检查偏向拒绝：序列化器与上述形态一旦不一致，结果是拒绝重写，而不是有损重写。

没有 `---` 区块、空区块，以及只是排版会变化的 YAML 都可重写；比较的是解析后的值，不是
文本。重写既有文件的工具（`edit`、`migrate`、`update_frontmatter_fields()`）在计算或
写入前调用这个 guard：被拒绝时文件字节不变，不创建 revision，不更新索引/缓存，不入
pending queue。`edit` 在动手前检查一次，拿到写锁后对锁内读到的内容再检查一次，以
`E0202`（`details.reason` 为上述 reason）拒绝；`migrate` 只在文件确实需要迁移时才问
这个 guard，被拒绝的文件列入 `failed_files`（读不出的文件连版本都不知道，dry-run 计入
`unparseable`）。写新文件的工具（`write`、`import`）不经过这个 guard。

### 4.4 每种类的必需字段（per-kind required fields）

`tools/lib/schema.py` 的 `get_required_fields(kind)` / `validate_metadata(metadata,
kind)` 按文件种类给出必需字段；文件名决定种类（§4.2），frontmatter 里声明的
`kind` 不改变任何读取行为。完整规则只在本节描述，其他文档指向本节：

- **fragment**：唯一必需字段是 `date`。标题、topic 等是解释，不是 fragment 的
  必需字段；`verify` 与 Data Doctor 审计的 frontmatter 检查都取自这一条规则。
- **digest / derived_index / unknown**：本包未定义规则，询问即抛 `ValueError`
  （digest 规则随 digest 命令落地）。
- 不传 kind 时按 fragment 处理（既有调用方的默认）。
- `date` 的形状检查（警告级，不做日历校验）接受：`YYYY-MM-DD`，或其后以 `T`/一个
  空格连接 `HH:MM` 或 `HH:MM:SS`（秒可带小数），可再带 `Z` / `±HH:MM` 时区。

### 4.5 条目标签规则（entry display label）

`tools/lib/journal_files.py` 的 `display_label(title, body, path)` 是唯一的展示
标签规则，确定且纯（无 I/O）。完整规则只在本节描述，其他文档指向本节：

1. `title` 去首尾空白后非空：返回该文本，原样。
2. 否则取 `body` 第一条带文字的行（空行，以及只由 Markdown 结构符号组成的行，如
   `##`、`***`、正文中途的 `---`，都不算），去掉行首 `#` 记号与首尾空白，在第一个
   前面已有文字的 `。！？!?`（终止符保留）或第 30 个字符处截断，以先到者为准；因
   长度截断且该行还有剩余文字时追加 `…`。以终止符开头的行（如 `![图](a.jpg)`）不在
   开头处截断。
3. 否则返回不带扩展名的文件名。`body` 的第一条非空行是 `---` 时也返回文件名：那是
   一个读不出的 frontmatter 区块被当作原文保留，开头几行是 YAML，不是用户说的话。

标签只是呈现辅助：它永不取代 `title`——`title` 保持文件所写（没有即为空）。
宿主 agent 展示结果时，`title` 为空就用 `display_label`，且绝不能把标签写回
文件当标题。结果的 `kind` 字段（文件名种类，如 `"fragment"`）告诉调用方这是
哪一类条目。metadata cache 以 `display_label` 列存标签（写行时计算，读取方
不再为标签打开文件；`CACHE_VERSION_SCHEMA_VERSION` 升至 v2.2.0，存量安装重建
一次）；FTS 表不加列，来自 FTS 的结果按路径查 cache 取标签，无行时用文件名。

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
- 一次 `detect_events` 调用内，Journals 树最多遍历一次：首个需要 fragment stat 的
  detector 通过 `tools/lib/journal_files.py` 的 `scan_journal_files()` 取得扫描结果，
  按调用 context 共享给后续 detector；扫描不进入模块级缓存，调用结束即丢弃。
  `schema_migration_available` 从同一次扫描取最新十个 fragment。

### 5.3 Entity 质量审计（Round 6）

- `life-index entity audit --json` — check/audit/stats 聚合门面，输出灯号和下一步
- 检测：重复实体、待裁候选、频繁共现无关系；零日志引用是 neutral fact，不是归档建议
- Agent 逐项访谈用户决定 merge_as_alias/keep_separate/add_relationship；写入必须有人判

> Entity Graph 的操作规范（别名准入、生产写入铁律、验证清单、回滚策略）见 [`docs/ENTITY_GRAPH.md`](./ENTITY_GRAPH.md)。
>
> **当前状态**：Entity Graph 已达 **Production Usable Baseline**（D5-D8 完成）。
> 覆盖范围：家庭人物关系（8 person + relationship 边）、Life Index 项目实体（含中文名/曾用名/模块属性）、AI 模型实体（3 person，subtype=ai，role=ai_assistant）。
> 生产图规模：13 entities，36 aliases，22 relationships。

### 5.4 操作级可观测性（Round 6）

- 所有 CLI 响应中增加 `_trace` 字段（trace_id + command + total_ms + steps）
- 上下文管理器模式：`with Trace("write") as t: t.step("validate")`

### 5.5 搜索评估与可观测体系（Round 8）

Round 8 在分层搜索架构之上，建立了完整的搜索质量保障闭环：

- **结构化搜索指标落盘**：每次搜索自动写入 `~/.life-index/metrics/YYYY-MM.jsonl`，记录 query、latency、pipeline signal、result count 等关键字段
- **搜索诊断入口**：`life-index search --diagnose` 聚合最近搜索行为，输出退化线索（zero-result queries、degraded searches、latency outliers）
- **Eval 边界**：CI 阻断只依赖可复现的公开合成 Core assertion；本地 / 私有 query、baseline 与质量测量仅作仓库外 operator evidence，不进入控制流
- **中文分词模块**：jieba 集成（index/query 双模式），支持 FTS5 中文精确匹配
- **搜索常量集中管理**：活跃 keyword/entity 搜索参数（min_relevance、score weights 等）通过 `search_constants.py` 集中管理；已退役 semantic/RRF 参数仅作为兼容 no-op 默认值保留

### 5.6 不做什么（本轮实现层约束）

- 不做 WAL/checkpoint、Vector 增量更新、Agent Memory、Multi-Agent、Plugin、除 ADR-004 所述可移除的通用薄投影外的 MCP 扩张

> 更宽泛的"我们不做什么"系统边界已由 CHARTER §1.7 与第四章反模式黑名单承担。
> ADR-026 中的 checkpoint/resume 指 long-running L3 模块的 addressable intermediate artifacts，不等于在 L2 检索/索引基座中引入 WAL/checkpoint。

### 5.7 自动索引重建与新鲜度检查（Round 8 Phase 1 + Round 12）

搜索索引（FTS5 + metadata cache）通过 `tools/build_index/` 模块管理，支持自动新鲜度检测和增量重建：

- **TOKENIZER_VERSION 机制**：`search_constants.py` 中的 `TOKENIZER_VERSION` 整数与 FTS 索引一起存储。当 jieba 分词器配置变更时，bump 版本号触发自动全量重建，确保索引 token 与查询时一致（ADR-011）
- **Index Manifest**：`tools/lib/index_manifest.py` 管理 FTS 索引构建状态（counts + checksums + legacy vector fields fixed at disabled/empty），支持增量更新的原子性和恢复
- **Pending Queue**：`tools/lib/pending_writes.py` 实现待修复队列（ADR-017）。写入/编辑的
  FTS 行写穿失败（含索引锁繁忙短超时）时才把路径标记 pending；搜索前消费队列，增量修复
  索引。每个 path 带 generation：`mark_pending` 从队列级计数器取下一个值（计数器只增不减，
  队列清空后也不回退，离队后再入队的 path 不会拿到旧快照里的值），acknowledgement
  （`ack_pending(snapshot, only=repaired)`）没有宽容模式：只移除“generation 未被提升
  **且** 出现在本次实际修复列表里”的路径，因此同一 path 在构建期间再次入队不会丢事件；
  旧的无 generation 列表格式继续可读（按 generation 0 处理），任何不可用的 generation
  或 counter 值也按 generation 0 读取；JSON 解析器本身拒绝的文件（非法 JSON、超长整数、
  过深嵌套）按空队列读取。两者都不会从搜索或写入中抛出。队列变更
  （mark/ack/remove/clear）经队列锁文件用共享 `FileLock` 串行化，避免 read-modify-write
  交错丢路径
- **FTS 行写穿 + stat 增量扫描**：写入/编辑在提交后即时写穿该日志的 FTS 行
  （`fts_row` / `fts_row_updated`）；增量扫描以 `(mtime, size)` 侧表判定"未变更"，
  不再读取/哈希每个文件（详见下节）

#### Metadata cache freshness（write-time upsert + reconcile）

Metadata cache 的新鲜度不再依赖全库内容哈希：

- **Write/edit 即时 upsert**：`tools/write_journal/core.py` 在 journal 提交后追加
  `metadata_cache_row/post_commit` 非阻塞副作用记录并调用
  `metadata_cache.upsert_journal_cache_row()`（内部即 `parse_and_cache_journal` 的
  INSERT OR REPLACE 单行 upsert）；`tools/edit_journal` 在编辑提交后做同样 upsert
  （结果字段 `metadata_cache_updated`）。失败不影响 journal 本身，恢复手段是
  `life-index index --rebuild` 或下次搜索的 reconcile 自愈。
- **全量重建仅三种触发**（`evaluate_cache_state()`）：(a) 无 version sidecar；
  (b) sidecar 记录的 `schema_version` 或 `tool_version` 与当前不匹配；(c)
  `entity_graph.yaml` 变化（sidecar 的 `source_hash` 现在只是该文件的哈希；write 时的
  entity 候选晋升会改写 graph，因此这类 write 后的首次搜索会做一次全量重建）。
- **Reconcile**（`ensure_cache_version_current()` → `reconcile_cache_with_files()`）：
  非重建情况下，搜索路径以 `tools/lib/journal_files.py` 的 `scan_journal_files()` 对 fragment
  文件做**单次**目录扫描（stat 事实来自 `os.scandir` 的 `DirEntry.stat()`，在 Windows 上
  不产生额外系统调用），逐行比较 `(mtime, size)`——与 `is_cache_valid` 同一判据——只解析
  新增/变更文件（复用 `parse_and_cache_journal`），并删除文件已消失的行。未变更日志的内容
  永不被读取；`_scan_row_file_freshness` 的 dry-run 使用同一次扫描实现。
- **`health --cache-audit` / `run_cache_audit()`**：以同一行级对比的 dry-run 形式输出
  `valid / stale / incompatible / missing` 与行级计数，不写任何文件。
- **可索引元数据与不可解析 frontmatter（两个派生存储共用一条规则）**：FTS 行构建与
  metadata cache 都只经 `tools/lib/frontmatter.py` 的 `normalize_indexable_metadata()`
  读取可索引字段；完整规则只在本节描述，其他文档指向本节。`normalize_indexable_metadata()`
  只在 root 不是 mapping 或为空 mapping 时返回 `None`：没有 `---` 区块、空区块
  （`---\n---`）、list/scalar root（包括 `false`、`0`、`[]`、`""` 这类假值：只有“没有
  文档”才读作空 mapping）、YAML 错误且 legacy `content:` 恢复也无法得到 mapping、
  递归别名（如 `custom: &a [*a]`，藏在 `!!pairs` 的 tuple 里也一样）。此时两个存储得到
  同一种处理——元数据全空，FTS 写入整篇原始文本行，缓存写入空行。只有未知键（含
  `_custom`）的非空 mapping 是可读的。`content` 键只有值是字符串时才按 legacy 形态并入
  正文；其他类型的值留在 metadata 里，重写 frontmatter 的工具会把它写回去。其余
  frontmatter 都可读：标量字段（`title`/`date`/`location`/`weather`/`project`/`abstract`）
  的 `None` 读作空串、字符串保留、数字/布尔转文字，mapping/list 转为扁平文本；列表字段
  （`topic`/`tags`/`mood`/`people`/`links`/`related_entries`）的 `None` 读作空列表、标量转
  单项列表、list 逐项转文字，mapping/list 项以及字段级 mapping 都转为扁平文本；其余键一律
  忽略（键不是字符串也一样，如 `2024: x`）。一个字段坏只损失该字段，不会让其他元数据变成
  原始文本行。扁平文本是确定性的深度优先渲染：mapping 渲染为 `key: value` 对，其他集合
  （list、`!!pairs`/`!!omap` 的 tuple、`!!set` 的 set——set 按类型名与文字排序）渲染为
  各项，以 `", "` 连接，非字符串键转文字。遍历是迭代式的，没有深度上限：任何深度的标量
  叶子都保持可搜索；集合包含自身时，递归引用处渲染为空。输出恒为可按 UTF-8 编码的文字
  （lone surrogate 替换为 U+FFFD，二进制按 UTF-8 解码，过长的整数用十六进制），对任何
  输入都不抛错。
- **统一日期规则**：`date` 一律取 `normalize_indexable_metadata()` 得到的 `date` 文本前
  10 个字符（形状为 `YYYY-MM-DD`，仅数字与连字符，不做日历校验）；不符合（如 `20260311`
  或 `[2026]`）或缺失时，回退到规范 fragment 文件名中的日期，否则 `""`。这条
  `frontmatter.indexable_date()` 规则用于 FTS parsed/raw 行、metadata cache 行、不经
  缓存的 L2 读取、兜底内容扫描、`timeline` 与生成的索引（`generate_index` 月/年/根
  索引与 `index_tree` 的 navigation entries / Index B）。缓存不再过滤 `_` 前缀键来决定“可解析”：它对 `parse_frontmatter()`
  的完整结果调用 `normalize_indexable_metadata(metadata) or empty_indexable_metadata()`，
  再套用同一条日期规则；只有 `_custom: x` 的 frontmatter 因此在两个存储里得到同一个
  文件名日期。
- **展示标签列**：cache 行写入时按*条目标签规则*一节计算 `display_label` 列，读取方
  （含 FTS 结果的按路径取标签）不再为标签打开日志文件；sidecar schema 升到 v2.2.0
  时存量安装重建一次。
- **兜底内容扫描**（`l3_content.py`）：先严格按 UTF-8 读取；遇到 `UnicodeDecodeError`
  时把替换后的整篇文本作为可搜索正文、不带任何元数据（与 FTS raw 行完全一致）。可读文件
  用同一条规则读取，不可解析文件按整篇文本参与匹配。它的相关度门槛与遍历范围不在本规则
  之内。
- **已知边界（接受）**：工具外修改若 mtime 与大小均不变，则要到
  `life-index index --rebuild` 才能被发现；sidecar schema 自 v1.1.x 升到 v2.0.0 时存量
  安装会全量重建一次，v2.1.0 因列表列统一为 JSON 数组再重建一次，v2.2.0 因新增
  `display_label` 列再重建一次。

#### FTS index freshness（signature reconciliation on every search）

FTS 索引的新鲜度**不再由时间戳推断**（`index_meta.last_updated`、数据库文件 mtime、
manifest 行数都不再是判据）。它和 metadata cache 用同一条规则：**逐 fragment 比较
`(mtime, size)` 签名**。

- **搜索 preflight（只读检查）**：pending 队列为空时，搜索先运行
  `index_freshness.check_full_freshness()` → `fts_update.inspect_fts_index()`：做一次
  `scan_journal_files()` 目录扫描，同时读取 `journals` 表的 path 集合与 `fts_file_stats`
  的签名集合。一个 live fragment 只有“有 FTS 行 **且** 有匹配签名行”才算 current；任何
  live fragment 缺行/缺签名/签名不符，或存在指向已消失文件的 FTS 行/签名行，或 pending
  队列非空，都判为 stale。目录 listing 与记录签名不一致时，按 metadata cache
  `_row_is_current` 的同一做法对该文件补一次真实 `stat` 确认后才当作变更。检查本身
  **不打开任何日志文件**；全部 current 时 preflight 不再执行其他步骤，也不写任何东西。
  队列非空时 preflight 直接进入修复；修复后重新运行同一只读比较，L3 fallback 的
  “current” 结论只来自这次比较，从不来自构建的返回值。该结论同时写进搜索结果的
  `index_status.signature_current`（`true`/`false`；没有真正运行签名检查时不出现），
  `retrieval_coverage` 在它为 `false` 时报告 `index_not_fresh`——一次“成功”的修复不等于
  索引已 current（例如某个文件读取一直失败）。字段契约见 `docs/API.md`。
- **只有 stale 才修复**：preflight 在共享 index lock（`<data>/.index/index.lock`，由
  `get_index_lock_path()` 返回；普通构建、source-safe 构建与写穿共用这一把锁）下运行
  增量 archive scan（`build_all(incremental=True)`），只重读新增/变更/缺行/待修复的文件，
  删除已消失文件的 FTS 行与签名行，然后写 manifest。`life-index index` 走同一扫描。
  全量重建在持锁后若发现遗留的 `.rebuilding` marker，说明其创建者已死，会删除该 marker
  并继续，不再等待固定的 300 秒。
- **Write/edit 即时写穿**：`tools/write_journal/core.py` 在 journal 提交后追加
  `fts_row/post_commit` 非阻塞副作用记录并调用 `search_index.upsert_fts_row()`。
  行由**提交后的文件**经与全量重建同一条 "file → FTS row" 路径构建
  （`fts_update.read_journal_document` → `fts_update.insert_fts_doc`）。文件**只读取一次**
  （bytes）：行内容、`file_hash` 与签名都来自这次读取；读取前后各取一次 stat，只有
  `(st_mtime_ns, st_size, st_ino)` 不变才记录 `(mtime, size)` 签名，否则行照常写入但不
  记录签名，下一次扫描会重新读取。`tools/edit_journal` 在编辑提交后做同样写穿（结果字段
  `fts_row_updated` 与结构化的 `fts_row {status, reason, recovery}`）。写穿成功时
  `mark_pending` 记为 `skipped`——它只表示本次操作没有入队，队列里可能仍有更早的条目；
  失败时 `recovery_strategy` 为 `life-index index`，路径照旧入队（`queued`），由下一次
  搜索 preflight 修复。写穿**不修改 `index_meta.last_updated`**，也不改写
  tokenizer/dict/schema 版本键：只有一次完成的 archive scan（增量或全量）才能推进
  `last_updated`。
- **准入规则**：只有 `journal_files.is_live_fragment_path()` 认可的 path（位于该 journals
  树内、相对路径无 dot-directory 分量、文件名分类为 fragment）才允许写入派生存储。FTS
  写穿与 metadata-cache upsert 都使用这一条谓词，因此编辑 `digest_*.md`、派生索引或
  `.revisions/` 内文件不会再写入随后被扫描删除的行；这些编辑返回
  `fts_row.status = "skipped"`。
- **与重建串行化**：写穿持有同一把 index lock（见上；`FILE_LOCK_TIMEOUT_FTS_ROW`
  短超时），因此不会插进一次全量重建的"枚举 → 删除/插入"窗口而被整表覆盖丢失。拿不到锁
  即按写穿失败处理并入队。锁序恒为 journals lock → index lock → queue lock（写入
  `tools/write_journal/core.py`、编辑 `tools/edit_journal/__init__.py` 均在持有 journals
  lock 的提交段内调用写穿；`build_all` 只持有 index lock，在锁内读取/确认 pending 队列；
  队列锁是叶子锁）；无反向持锁路径，故不会死锁。
- **(mtime, size) 侧表**：`journals_fts.db` 内的普通表 `fts_file_stats`
  （`path PRIMARY KEY, mtime, size`）记录每个已索引文件的签名；由全量重建、
  写穿和增量扫描共同维护，可从源文件 100% 重建（§1.2 机器检索层例外）。重建或清空
  `journals` 表时同步清空签名表，避免“签名匹配但行已丢失”。
- **增量扫描**（`life-index index`、pending 修复、staleness 修复；
  `fts_update.update_index`）：经 `tools/lib/journal_files.py` 枚举 fragment 文件，
  stat-only 比对侧表签名——签名未变**且已有 FTS 行**的文件不被读取；只读取签名变化、
  缺行或缺签名的文件；pending 队列中的 path 无论签名是否匹配都强制重读；文件消失则删除
  其 FTS 行与签名行。**每个可读的 live fragment 都有 FTS 行**：frontmatter 读不出
  mapping root（无 `---`、空/非法 YAML、list/scalar root、递归结构、非 UTF-8 字节）时，
  整篇文件文本（含 frontmatter 区块里的文字）分段后写入 `content`，`title` 与元数据列为空，
  `date` 按上文 *Metadata cache freshness* 的统一日期规则（frontmatter 日期，否则文件名）。
  该文件此后与普通行一样 current（不重试、不强制 fallback）。字段里的数字/布尔或
  mapping/list 都按扁平文字入索引，一个坏字段不损失其他元数据，也不算不可解析。这类
  文件在**全量重建**和**每次被重读**时计入 `fts.unparsable`/`fts.unparsable_paths`。
  完全无法读取（`OSError`）的文件不写任何东西并保持 not-current 以便后续重试：增量扫描
  保留其已有行与签名；全量重建先清空再写入，该文件此时没有行。两种模式都把这类文件计入
  `fts.unreadable`/`fts.unreadable_paths`，并在 `fts.total` 中照常计数，因此“重建成功”
  不会掩盖一个没有被索引的文件。FTS 行与 metadata cache 对不可解析 frontmatter 的
  容错是同一条规则（见上文 *Metadata cache freshness* 一节）。
- **其他新鲜度读者**：`check_index_stale`（event detector，含 pending 队列）与 L3
  fallback 的 `fs_consistency.index_is_current()` 都改为调用同一签名检查；旧的
  “newest journal mtime vs `last_updated`”和“manifest 行数 vs 实际行数”规则已删除。
- **版本升级**：`FTS_SCHEMA_VERSION` v2 → v3。存量 v2 安装没有签名行：已记录的
  schema 版本不匹配会经既有 `check_needs_rebuild` 机制在第一次增量更新时自动做
  一次全量重建并填充侧表，无需人工干预。
- **已知边界（接受）**：工具外修改若 mtime 与大小均不变，则要到
  `life-index index --rebuild` 才能被发现（与 metadata cache 同一判据、同一边界）。
  例外：该 path 仍在 pending queue 中时会被强制重读，所以写穿失败且同 mtime/size 的
  编辑仍可由搜索 preflight 修复。

#### Transactional write boundary

`tools/write_journal/core.py` uses one ordered `side_effects` record sequence as
the execution truth for the compatibility summaries `write_outcome`,
`index_status`, and `side_effects_status`.

1. Attachment bytes are copied into a transient same-filesystem staging tree.
   Final publication is atomic and create-only; a transaction never replaces a
   target it did not create, and compensation verifies creation identity before
   deleting a published path. Failed staging cleanup reports its concrete path.
2. The journal is written to a temporary file; staged attachments are then
   published, followed by the journal's atomic rename (`journal_commit`).
3. Any failure before that rename removes the temp journal and compensates only
   attachments published by this transaction. No derived view runs before the
   durable journal commit.
4. Monthly abstract, legacy navigation indexes, metadata relations, the
   metadata cache row upsert (`metadata_cache_row`), the FTS row write-through
   (`fts_row`), pending freshness, Index B, entity candidate capture, and
   confirmation snapshots run after commit. Their failure preserves the journal
   and produces `success_degraded` with a machine-readable recovery strategy.
5. `fts_row: complete` means the journal's FTS row was written through from
   the committed file; `mark_pending` is then recorded `skipped`, which means
   this operation queued nothing (older queue entries may remain).
   `mark_pending: queued` means the write-through failed, the existing atomic
   pending queue is durable, and the next search preflight or
   `life-index index` repairs it. Queue acknowledgement is generation-scoped:
   a path re-queued during the repair scan survives, and a live fragment whose
   frontmatter does not parse is indexed as raw text (complete, not queued).
6. Optional CLI `auto_index` runs only after `journal_commit=complete`, appends a
   nonblocking post-commit record, and re-projects compatibility summaries.

This is a bounded file transaction, not a WAL, background worker, database, or
new queue protocol.

#### Disaster-recovery boundary

A full `backup` creates a self-contained timestamped directory and an atomic
`.life-index-recovery-manifest.json`. Its sorted SHA-256 artifact inventory marks
journals, attachments, and `entity_graph.yaml` as `canonical_source`; discovered
`.index/` files are `rebuildable_derived` with `included: false`. Generated journal
indexes and `by-topic/` compatibility views may be copied for compatibility, but
remain classified as rebuildable rather than source truth.

The recovery manifest is a closed trust boundary: top-level and artifact fields,
normalized unique paths, path-to-classification/inclusion mapping, sizes, hashes,
and source/destination containment are validated. Symlink and Windows reparse-point
paths are rejected. Normalized exact paths are the artifact identity; case-distinct
paths remain valid on case-sensitive filesystems but are rejected before publication
or restore when the target filesystem cannot represent both. A full backup also fails
closed if caller exclusions remove a
canonical source. Timestamp collisions allocate create-only suffixed directories;
the destination catalog retains every resulting recovery point.

Manifest-backed restore validates every included artifact before writing and
accepts only an absent or completely empty destination. A nonempty destination is
rejected before mutation, so restore never has overlay semantics. A mid-copy failure
compensates only files and directories created by that attempt, returning the target
to a retryable empty state. The result distinguishes `manifest_verified` from
`legacy_unverified`; legacy restores carry an explicit unverified warning. After restore,
`.index/` and navigation views are rebuilt from canonical plain files; rebuild
failure remains a visible derived failure and does not authorize source mutation.
The older destination-level backup catalog remains list/incremental metadata, not
the recovery authority for a full backup. Its final publication is a short serialized
transaction after copying: acquire the catalog file lock, reload current history,
merge this backup's file entries and record, then atomically replace through a temporary
file. Interrupted publication leaves prior catalog bytes intact and makes the current
backup result non-successful.

### 5.8 搜索编排器（v1.2.0 smart-search v1 contract）

CHARTER APEX 定义了"确定性 vs 智能"的边界：CLI Core 层执行确定性搜索与 scaffold 生成，智能编排由宿主 agent / Skills 完成。

smart-search 架构：
- **CLI 入口**：`life-index smart-search`（注册于 `tools/__main__.py`，实现于 `tools/smart_search/__main__.py`）
- **默认工具流程**：无 provider/client 注入面，不读取 LLM key，返回确定性检索 scaffold、`agent_instructions`、`answer_scaffold` 与 `query_plan`；自然语言查询复用 SearchPlan 已抽取关键词作为 bounded 子查询。关键词选择、二次检索、过滤与总结由宿主 agent 完成。显式 `--synthesize` 仅发出一次 stderr 弃用警告，不改变 JSON/domain 输出；当前 A3/A4 与 A5 candidate 状态见上方 `SMART-SEARCH-CURRENT-CONTRACT` 命名块
- **宿主流程**：宿主 agent 可基于 scaffold 继续调用 search / smart-search / index navigation / read tools，完成 query 拆解、结果判断与总结
- **Data Minimization**：工具输出 bounded evidence；是否继续读取由宿主 agent 决定并受调用边界约束

### 5.9 常量集中管理（Round 17 Phase 1-A）

`search_constants.py` 作为搜索子系统所有阈值的唯一来源（CHARTER §4.3 合规）：

- **50** 个导出常量（`__all__` 已补齐，Round 19 新增 fuzzy typo 4 个 + structured intent 3 个 = +7），涵盖 legacy 兼容、FTS、评分、置信度、标题加权、L3 回退、关键词管道、编排器、fuzzy typo correction、structured metadata retrieval 等全部参数
- 每个常量带 ADR 编号和决策 rationale
- 散落在 `confidence.py`、`title_promotion.py`、`l3_content.py`、`keyword_pipeline.py` 中的 14 个裸字面量已于 Round 17 Phase 1-A 迁移完毕

### 5.10 Phase 1-D 搜索增强（Round 19 Phase 1-D）

Round 19 Phase 1-D 在搜索子系统中新增以下能力：

- **Eval Anchor 确定性注入**（F1）：显式时间锚使 operator eval 在任意日期产出可复现测量，解决相对时间漂移；私有 baseline 路径与 corpus facts 不进入公开权威。
- **Fuzzy Typo Correction**（C1-a）：`FUZZY_TYPO_*` 常量组在 `query_preprocessor.py` 中做确定性 Levenshtein 模糊匹配；公开契约不引用私有 query ID 或语料样本。
- **Bilingual Alias Expansion**（C1-b）：`query_preprocessor.py` 内置确定性中英别名映射；公开契约不引用私有 query ID、标题或语料样本。
- **Structured Intent Match Bonus**（R1 safe）：`STRUCTURED_*` 常量组在 keyword-only 路径上对同时命中 date_range + topic_hints 的候选结果加分（+50 keyword path），安全实现不做全局排序补丁。
- **Broad/private eval advisory**：Broad/private quality metrics remain observable and advisory; weak or errored broad metrics do not enter blocking failures or override exact Core results. 私有查询数、阈值、指标与语料事实仅存于公开制品之外的 operator evidence。

### 5.11 Import review queue authority（M7 历史照片冷启动）

`media.photo_timeline` 在既有 import ledger / rollback manifest / fingerprint 权威之上
additive 一个可恢复照片审阅队列。其权威架构有三条不变量（实现见 `tools/ingest/review.py`，
权威契约见 `docs/API.md` 「Review queue & batch import」）：

- **Ledger transaction + per-parent single-writer 权威**：所有 import ledger 读改写
  事务先取跨进程 `FileLock`（`.life-index/import-jobs/ledger.lock`），覆盖完整
  read-modify-write；`ledger.json` 只用同目录 temp + fsync + atomic replace 更新，已存在
  但 malformed/torn/unreadable 时 fail closed，绝不重置为空。需要 parent 投影的事务再
  取 `.life-index/import-jobs/<parent_id>/review.lock`，全局固定锁序为 **ledger →
  parent → journals**（journals 仅为 rollback 最终删除段的 innermost lock）；进程内嵌套
  helper 复用外层 ledger transaction，避免重入死锁。`confirm` / `rebind` / `run` /
  `status` / child `rollback` / reconciliation 均遵守该顺序。child rollback 的 parent
  投影由 child 自身精确 `proposal_ids` 驱动，绝不复用 parent 上一次选择。

- **Crash-safe plan↔ledger 更新（intent/reconciliation）**：ledger 是唯一权威（不引入
  第二个 store）。`confirm` 按 **durable intent → atomic plan replace → finalize** 三步
  在锁内更新：先在 parent job 写入 `pending_review_update` intent（含
  `expected_plan_fingerprint` / `expected_plan_revision`、完整 finalize 投影、prior 投影
  快照），再 atomic 替换 review-plan.json，最后从 intent finalize 并清 intent。reconcile
  （confirm/status/run/rollback 共用）收敛三窗口：intent 指纹匹配持久化 plan → 幂等
  finalize；intent 存在但 plan 仍旧/缺失 → abandon intent、恢复 prior 投影（首次 confirm
  空 shell 移除）；**无 intent 但 plan 与 ledger 指纹不一致** → fail closed
  （`recovery_required` + `authority_status = "plan_ledger_mismatch"`），`run` 返回
  `IMPORT_RECOVERY_REQUIRED`，绝不静默二选一。重复 status 收敛。

- **Crash-safe child publication ownership**：M7 child 在既有 job 目录内使用确定性
  staging 名。attachment/journal final path 出现前，既有 rollback manifest 已 durable
  记录 target kind/path、expected hash/size 与 staging filesystem identity；final 只由
  该 staging inode 以 create-only hard link 发布。故 post-publish/pre-manifest crash 可
  在重启后由 identity + checksum 证明并补偿 owned artifact；相同 bytes 但不同 identity
  的 preexisting/racing target 保留。committed manifest validation 与 rollback 都对新
  ownership proof fail closed；rollback 初检后在 shared journals lock 内排队 pending，
  紧邻首次 unlink 前对所有 target / staging 再做 confinement / identity / hash / size
  复检，任一变化则零删除失败；commit/成功 rollback 清除 staging。该证据是
  `import_rollback_manifest.v1` 的 additive 字段，不增加第二权威或 schema break。

- **Immutable provenance 权威**：source facts（adapter/provenance、content SHA-256、size、
  source 相对路径/ref、capture time value/source/timezone authority、GPS）不可变；一个
  selected attachment 必须绑定到同一不可变 source fact（`source_sha256` / `source_rel_path`
  / `source_ref` / `media_type` / `size_bytes` + 确定 `attachment_id`），`confirm` 做绑定
  交叉校验拒绝任何篡改。非 frozen proposal 的 canonical attachment / journal target 由
  effective date + content 在 `confirm` 时重新派生，绝不信任 incoming GUI 编辑。EXIF 日期
  权威绝不来自文件 mtime；offset 只取与所选 capture tag 配对的 offset tag（不借用兄弟
  tag），且必须有显式符号、合法分钟、落在 ±14:00 真实世界范围内，否则按相机本地 naive
  使用、绝不换算。单 proposal edit（`confirm --edit`）与 preview 都从持久化 immutable
  `source_facts` 解析 attachment（非客户端提供），故被取消选择的附件仍可重新选择 /
  预览；全部 `source_facts` 始终保留。

- **两个 revision、各自一个权威（M7-B package-3）**：parent review job 维护
  `plan_revision`（review-plan 内容）与 parent-ledger 拥有的 `queue_revision`（客户端并发
  令牌，初始 1）。每次「parent 可见投影的原子变更」令 `queue_revision` 恰好递增一次
  （stage / edit / legacy reconfirm finalize / run 转移到 batching 或 stale / 改变
  proposal states·active child·recovery 的 child commit-rollback-failure reconciliation /
  identity 变化的 rebind / 可见复合投影变化的 plan-authority reconciliation），而
  state-only 的 run / rollback / reconciliation **永不**改动 `plan_revision`。pending
  intent 携带 finalize 后的精确 `queue_revision`，crash replay 幂等、绝不二次递增；
  `updated_at` 等非权威字段单独变化不递增令牌；收敛后重复读为 no-write。`import stage`
  对重复 `source_root_identity`（actionable job 或 active child）拒绝创建第二个 job/plan
  （`IMPORT_REVIEW_ALREADY_STAGED`，零写入）；全 `skipped`/`imported`/`stale` 且无 active
  child 的 job 视为已完成、不阻塞新 stage。`import review` / `import reviews` 为有界分页 /
  发现的稳定只读投影，绝不暴露 source 文件系统定位或 proposal 正文。

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
tools/                         # Public CLI package; exact Core/non-Core classification is above
├── write_journal/
├── search_journals/
├── edit_journal/
├── entity/                    # 实体图谱 + 质量审计 + review hub + merge/delete
├── generate_abstract/
├── build_index/
├── query_weather/             # Legacy External Adapter (#166)
├── backup/
├── migrate/                   # Schema 链式迁移
├── dev/                       # 开发/验收辅助工具
├── smart_search/              # 确定性智能检索 scaffold；宿主 agent 负责合成
├── eval/                      # 搜索质量评估
└── lib/                       # 共享库（SSOT）
```

### 6.3 日志文件格式

#### 目录结构

```
~/Documents/Life-Index/
├── Journals/                    # 日志主目录
│   └── YYYY/MM/                 # 按年月组织
├── .life-index/index-b/         # canonical navigation indexes
├── by-topic/                    # legacy compatibility indexes
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

> **SSOT**：`tools/lib/topics.py` `VALID_TOPICS`。共 7 个有效值：`work`, `learn`, `health`, `relation`, `think`, `create`, `life`。此处不重复枚举，以代码为准。

---

## 相关文档

- [CHARTER.md](../CHARTER.md) — **项目宪章**（本文档从属于此；不变量与治理规则在此）
- [bootstrap-manifest.json](../bootstrap-manifest.json) - Authority anchor；onboarding 必须先刷新此文件
- [AGENT_ONBOARDING.md](../AGENT_ONBOARDING.md) - 基础版 Agent 安装与初始化流程
- [API.md](./API.md) - 工具接口详细文档
- [SKILL.md](../SKILL.md) — Agent 技能定义
- [README.md](../README.md) — 用户入口与安装提示
- [ENTITY_GRAPH.md](./ENTITY_GRAPH.md) — Entity Graph 操作规范（别名准入、写入铁律、验证清单）
- [VERSIONING.md](./VERSIONING.md) — 公开版本语义与 release artifact contract

---

> **校对日期**: 2026-07-11
> **校对人**: Life Index Developer
> **对应状态**: 闭合 Core 准入域为 `CHARTER.md §1.10` 活跃权威；本文件拥有 route classification SSOT。搜索架构保持 keyword + Entity Graph；`--semantic*` 为兼容 no-op；official eval gate 保持 keyword/default，search_constants.py **50** 常量。
