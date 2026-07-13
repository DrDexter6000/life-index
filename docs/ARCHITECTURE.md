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

**本文档聚焦可演化的实现细节** — 索引树结构、分层搜索参数、ADR-003/004 等可演化决策、目录快照、基础设施增量记录。这些随实现版本迭代，不属于宪章不变量。

<!-- PLATFORM-SSOT:CURRENT-TARGET-STATUS:START -->
### Platform program: current runtime vs ratified target

Current runtime: direct CLI/Core contracts are the implemented public route;
the accepted `--synthesize` flag follows the deterministic no-LLM/no-answer
contract named below, and the current bridge is non-Core and GUI-owned. The
design memo is not an authority or SSOT. The exact closed C1–C7 domains are now
active Charter authority, and the former §1.9 direct provider-fallback direction
is superseded: Host Agent + Skill own provider selection and intelligence.

The following program work remains incomplete; D0 ratification did not itself
implement it:

- #163 — smart-search A3/A4 is implemented, and the A5 candidate makes eval deterministic-only: `--judge llm` fails before provider/configuration import, production eval provider/prompt/client ownership is removed, and the public hard check scans search, smart-search, and eval roots. #163 remains open pending review, so D1-A is not complete.
- #162 — the D1-B candidate implements transactional write side-effect records and honest freshness; the issue remains open pending independent review, so D1 is not complete.
- #165 — the D1-C candidate implements a full-backup recovery manifest, empty-only
  restore, and synthetic rebuild/search/verify proof; the issue remains open pending
  independent review, so D1 is not complete.
- #164 — optional Core Capability Gateway typed 1:1 projection: unimplemented.
<!-- PLATFORM-SSOT:CURRENT-TARGET-STATUS:END -->

<!-- PLATFORM-SSOT:PLATFORM-ROLE-BOUNDARY:START -->
### Platform role boundary

| Role | Authority boundary |
|---|---|
| Core | Deterministic tools; no planning, reasoning, orchestration, interpretation, or synthesis. |
| Host Agent + Skill | Owns planning, multi-hop reasoning, orchestration, interpretation, and synthesis. |
| GUI | Presentation only; no intelligence; strict adapter stays GUI-owned. |
| Current bridge | Non-Core and GUI-owned. |
| Core Capability Gateway | Optional future typed 1:1 projection under #164; unimplemented; not a second semantic API; no intelligence. |

The table above is the sole normative role-assignment surface in this block.
The future Core Capability Gateway, if implemented, is only a contract-equivalent transport of
Core operations. It cannot create a parallel semantic contract, and direct Core
use does not depend on it. The active closed admission-domain catalog belongs
only to `CHARTER.md §1.10`; this document references C1–C7 without duplicating
their domain descriptions.
<!-- PLATFORM-SSOT:PLATFORM-ROLE-BOUNDARY:END -->

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
| Already covered by the closed C1-C7 Core authority | Consume the canonical Core capability; do not duplicate it in the Addon. |
| Satisfies every already-ratified admission constraint and belongs within C1-C7, or receives new Human Owner substantive approval for the required authority expansion | Propose Core admission through the existing RFC/substantive-gate process; determinism and all non-waivable constraints still apply. |
| Does not satisfy those conditions | Keep it Addon-local and non-canonical. |
| Performs semantic understanding, orchestration, interpretation, or synthesis | It is not a deterministic helper; route it through the shared Host Agent Handoff and Host Agent + Skills. |

#### Prohibitions and gateway distinction

- An Addon must not own an LLM, provider selection, API-key handling, or an agent runtime.
- An Addon and its helper must not bypass Core to read or write L1, duplicate a canonical Core capability, or duplicate runtime adapters.
- A Core Capability Gateway, if implemented, is only a typed transport projection of the canonical Core Capability Contract. It is not an Agent Runtime Gateway, Host Agent, Life Index brain, reasoning or session owner, or provider boundary.
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

This table is the exhaustive current 31-route mapping under the Charter-owned
C1–C7 and stable non-Core classification rules in `CHARTER.md §1.10`.
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

L2 仍不得调用 LLM，也不得实现或存储 ADR-026 所列 persona interpretation、emotion interpretation、relationship judgment、narrative synthesis、digital letters、creative emulation、cross-journal LLM reasoning 等解释性能力或结论。L3/L4 模块若消费 L2 输出做解释或创作，必须保留证据、限制与 provenance。

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

Therefore the existing `tools/mcp_discovery` discovery stub is constitutional: it is static, read-only, and does not touch user data. A future stdio JSON-RPC shim can be constitutional only if it remains a CLI passthrough that returns the CLI JSON output unchanged. Any MCP implementation that diverges from CLI behavior, owns schemas independently, directly reads/writes the journal data directory, or adds in-tool reasoning/orchestration falls under CHARTER §4.1 “parallel interface” risk.

---

## 4. 目录结构

```
~/Documents/Life-Index/           # 用户数据目录
├── .life-index/index-b/          # canonical deterministic navigation docs
├── INDEX.md                      # legacy generated root index
├── Journals/                     # 日志文件存储
│   └── YYYY/                     # 按年分层
│       ├── index_YYYY.md         # 年度索引
│       └── MM/                   # 按月分层
│           ├── index_YYYY-MM.md  # 月度索引
│           └── life-index_*.md   # 日志原文
├── by-topic/                     # legacy compatibility indexes
│   ├── 主题_work.md
│   ├── 项目_Life-Index.md
│   └── 标签_重构.md
├── attachments/                  # 附件存储
│   └── YYYY/MM/
└── .index/                       # 机器检索层（FTS5 + 元数据缓存）
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

- 不做 WAL/checkpoint、Vector 增量更新、Agent Memory、Multi-Agent、Plugin、MCP

> 更宽泛的"我们不做什么"系统边界已由 CHARTER §1.7 与第四章反模式黑名单承担。
> ADR-026 中的 checkpoint/resume 指 long-running L3 模块的 addressable intermediate artifacts，不等于在 L2 检索/索引基座中引入 WAL/checkpoint。

### 5.7 自动索引重建与新鲜度检查（Round 8 Phase 1 + Round 12）

搜索索引（FTS5 + metadata cache）通过 `tools/build_index/` 模块管理，支持自动新鲜度检测和增量重建：

- **TOKENIZER_VERSION 机制**：`search_constants.py` 中的 `TOKENIZER_VERSION` 整数与 FTS 索引一起存储。当 jieba 分词器配置变更时，bump 版本号触发自动全量重建，确保索引 token 与查询时一致（ADR-011）
- **Index Manifest**：`tools/lib/index_manifest.py` 管理 FTS 索引构建状态（counts + checksums + legacy vector fields fixed at disabled/empty），支持增量更新的原子性和恢复
- **Pending Queue**：`tools/lib/pending_writes.py` 实现写入穿透缓存，写入/编辑后标记 pending，搜索前消费，确保搜索结果包含最新数据（ADR-017）

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
4. Monthly abstract, legacy navigation indexes, metadata relations, pending
   freshness, Index B, entity candidate capture, and confirmation snapshots
   run after commit. Their
   failure preserves the journal and produces `success_degraded` with a
   machine-readable recovery strategy.
5. `mark_pending: queued` means the existing atomic pending queue is durable;
   search preflight remains the sole consumer and freshness authority.
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

Manifest-backed restore validates every included artifact before writing and
accepts only an absent or completely empty destination. A nonempty destination is
rejected before mutation, so restore never has overlay semantics. After restore,
`.index/` and navigation views are rebuilt from canonical plain files; rebuild
failure remains a visible derived failure and does not authorize source mutation.
The older destination-level backup catalog remains list/incremental metadata, not
the recovery authority for a full backup.

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
> **对应状态**: C1–C7 为 CHARTER v1.11.0 活跃权威；本文件拥有 31-route classification SSOT。搜索架构保持 keyword + Entity Graph；`--semantic*` 为兼容 no-op；official eval gate 保持 keyword/default，search_constants.py **50** 常量。
