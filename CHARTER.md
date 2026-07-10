# Life Index Charter | 生命索引宪章

> **版本**：v1.10.0
> **批准日期**：2026-07-10
> **批准人**：Life Index Developer
> **下次评审**：2026-07-23（每季度一次）
> **修订次数**：10
> **最近修订**：2026-07-10 — Owner substantively approved exactly C1–C7, superseded Core provider fallback, and assigned provider selection and intelligence to Host Agent + Skill（D0 ratification）
> **此前修订**：2026-06-19 — 新增 APEX 第 6 点「评估即咨询，非闸门（Evaluation is Advisory, not a Gate）」，收紧 APEX §1/§5（RFC-2026-06-19-evaluation-advisory-not-gate；owner 亲签）；2026-06-18 — 新增「北极星（Agent-Native 最高不变量 · APEX）」最高实质原则，收编旧 §1.9 中"Life Index 自建 L3 智能模块"措辞（RFC-2026-06-18-agent-native-north-star-apex；owner 亲签）；2026-06-14 — 新增 §1.12 运行时/平台可移植性（Runtime & Platform Portability）+ §4.1 镜像反模式（RFC-2026-06-14-runtime-platform-portability）；2026-05-23 — 新增 §1.11 Recall-First Retrieval Truthfulness Model + §3.2 amendment note（RFC-2026-05-23-l2-recall-first-truthfulness-model；§1.11 加入 §5.3 不可弱化清单；起源于 v1.2.0 cycle2 absorption 暴露的 semantic noise / truncation 两个 loophole）；2026-05-20 — §5 修订流程改为 substantive gate（废除 24h cooldown 与三方评审覆盖机制；过程记录已归档到本地私有治理层）

---

## 序言

Life Index 不是一个 side project。它承载着**一位父亲写给女儿的数字家书**，目标是让用户的人生碎片**安全存活 50 年以上**。

任何一个要活 50 年的系统，都不能靠开发者当下的判断力维系。它必须有一份**不随作者情绪、模型迭代、需求变动而动摇**的根本大法 —— 来约束未来所有的设计决策、拒绝未来所有的临时性妥协。

本宪章即是 Life Index 项目的根本大法。它不是文档，是**契约**。

---

## 第零条：本宪章的地位与效力

1. **最高效力**：本宪章是 Life Index 项目的**最高治理文件**。在与任何其他公开项目文档（`docs/ARCHITECTURE.md`、`docs/API.md`、`SKILL.md` 等）冲突时，**以本宪章为准**。

2. **跨越代码**：本宪章高于代码实现。若代码违反本宪章，代码错、宪章对 —— 必须修改代码，不得反向修改宪章以迁就代码。

3. **修订门槛**：本宪章的任何章节变更，必须经由第五章「宪章修订流程」，不得通过普通 commit 直接修改。

4. **对 Agent 的约束**：所有 AI 编码代理在承担本项目任务前**必须通读本宪章**。违反本宪章的变更不得被接受，即使它通过了测试、即使它解决了用户报告的问题。

---

## 北极星（Agent-Native 最高不变量 · APEX）

> **Life Index 提供确定性、可组合的好工具（L1/L2）与领域 Skills；智能——规划、多跳、推理、合成——归宿主 agent；界面（GUI）只做呈现。agent 越聪明，Life Index 的体验自动越好。**

本节为全宪章**最高实质原则**，先于并统辖第一章各项不变量：

1. **工具非智能**：Life Index 的本体是给 agent 生态的**工具 + Skills**，不是 agent 本身。编排 / 多跳 / 推理 / 叙述合成由**宿主 agent**完成；**Life Index 不内建会替 agent 思考的 LLM 编排模块**。

2. **高级功能 = Skills**：复杂能力以 `SKILL.md` 程序化 playbook（+ 确定性 helper + 参考知识）承载，**引导而非强制** agent；不以"Life Index 自建智能模块"的形态实现。

3. **GUI = 呈现**：智能对 CLI / GUI 等同；GUI 的价值在终端做不到的**呈现与交互**，零智能、零编排。

4. **APEX 优先（冲突即以此为准）**：本节为最高不变量。**本宪章任何其他条款（含 §1.x / §2.x，及旧 §1.9 中"自建 L3 智能模块"措辞）与本节冲突时，一律以本节为准**，并须经第五章修订流程消解矛盾。

5. **判尺**：对任何能力 / 改动只问一句——它是"让数据可找 / 可结构化 / 可呈现"的工具·skill·呈现，**还是在替 agent 决策·推理·编排**？后者即违宪。

6. **评估即咨询，非闸门（Evaluation is Advisory, not a Gate）**：对 agent 输出的任何评估机制（grounding 校验、引证核验、质量判定等）仅以旁路咨询形态存在：产出标签与可观测元数据，供用户与宿主 agent 参考；不得作为控制流闸门去阻断、压制、改写、强制重试或以其它方式覆盖 agent 的产出。
   - **依据**：agent 能力为非平稳量（随模型迭代单调增强）。任何以"当下能力"标定的闸门，其判据将随时间系统性失配（误拒率上升），反向劣化产品——与第零条"不随模型迭代而动摇"相悖。旁路标签对能力单调安全：无论 agent 强弱，只增信息、不夺决策权，故长期正确。
   - **推论**：① 评估机制默认非阻断（non-blocking by construction），其输出是元数据而非控制信号。② 为弥补当下模型局限而引入的辅助件（预脚手架、prompt 提示、候选集预筛等）须为 agent 可关闭的可选增益，不得成为产出路径上的承重依赖。
   - **判尺补充（承 APEX §5）**：一个评估 / 辅助机制只问——它是在告知（标签 / 可观测性，agent 与用户自决），还是在替 agent 把关（阻断 / 覆盖）？后者即违宪。

**对旧 §1.9 的收编**：旧文所列"Life Index 自建 L3 智能模块（自传引擎 / 心潮地图 / 数字家书）"——这些体验**保留**，但实现为"**宿主 agent 驱动的 Skills + GUI 呈现**"，非 Life Index 自有的 LLM 代码模块。§1.9 全文对应措辞已于 2026-07-10 D0 ratification 按本节精神收束。

---

## 第一章：不变量（Invariants）

本章所列各项，为 Life Index 在其 50 年生命周期内**不得更改**的根本原则。每一项都经过 v1 ~ v2 两次版本演进与 16 轮 vibe coding 的血泪验证。

### §1.1 数据主权（Data Sovereignty）

用户的人生数据**100% 存储于本地**，具体位置为 `~/Documents/Life-Index/` 及其子目录。

**明确禁止**：
- ❌ 将用户原始日志内容、附件上传至任何云端服务
- ❌ 引入任何"必须联网才能读取用户数据"的依赖
- ❌ 在用户数据目录外创建第二个持久化写入点（数据库服务、在线缓存等）

**明确允许**：
- ✅ 用户自行选择云盘对 `~/Documents/Life-Index/` 做镜像备份
- ✅ 在调用 LLM 服务时传输**必要的、最小化的**上下文片段（非全量上传）
- ✅ 本地机器间通过用户主动操作做迁移

### §1.2 纯文本永久性（Plain Text Forever）

用户数据的**每一字节**必须以**人类可读、工具无关**的格式存储：

- **日志正文**：Markdown
- **结构化元数据**：YAML Frontmatter
- **附件**：原始二进制格式（图片/音频/视频），不得转码到私有格式
- **索引文件**（`INDEX.md`、`index_YYYY-MM.md`、`by-topic/*.md`）：Markdown

**明确禁止**：
- ❌ 将用户内容写入任何二进制/私有格式作为**唯一**存储
- ❌ 依赖特定软件版本才能读取用户数据

**机器检索层例外**：`.index/` 目录下的 SQLite FTS5 数据库、元数据缓存与派生 manifest 属于"机器副产物"，允许为二进制；但**必须可以从 Markdown 源文件 100% 重建**（`life-index index --rebuild`）。用户数据丢失 `.index/` 不损失任何原始信息。

### §1.3 CLI 作为 SSOT（Single Source of Truth）

**所有对用户数据的读写能力必须以 CLI 命令暴露**。不得存在"只能通过 GUI / Agent / Web / API 才能完成"的操作。

**推论**：
- GUI、Agent、Web 都是 CLI 的"消费者"，不是 CLI 的"并行形态"
- 当 GUI 或 Agent 需要一个能力时，先在 CLI 实现，再被消费
- 不得在 GUI/Agent 侧引入独立的数据写入路径

**明确禁止**：
- ❌ 在未来的 GUI 仓库中实现绕过 CLI 的直接文件写入
- ❌ 在 Agent 编排层引入绕过 CLI 的"捷径"
- ❌ 为 MCP 或其他协议创建与 CLI 契约不一致的并行接口

### §1.4 层级隔离（Layer Isolation）

Life Index 有且仅有**四层**，自上而下：

```
┌────────────────────────────────────────┐
│ L4: Interface Layer                    │  ← 生命周期 1-3 年
│     CLI / GUI / 自然语言               │
├────────────────────────────────────────┤
│ L3: Intelligence Layer                 │  ← 生命周期 1-3 年
│     Agent 编排 / LLM 调用 / 语义理解    │
├────────────────────────────────────────┤
│ L2: CLI Core Layer                     │  ← 生命周期 5-10 年
│     确定性原子操作 / 工具实现            │
├────────────────────────────────────────┤
│ L1: Data Layer                         │  ← 生命周期 50+ 年
│     Markdown + YAML + 附件              │
└────────────────────────────────────────┘
```

**权责规则**（每层的"能 / 不能 / 调用方向"详见第二章）：

- 调用方向只能**自上而下**：L4→L3→L2→L1。不得跨层（L4→L2 除外，见 §1.5）、不得反向。
- 下层不得感知上层的存在。L2 工具不得假设自己被 L3 调用。
- 每层的生命周期严格递增，下层变更影响上层，上层变更不得溢出到下层。

### §1.5 确定性与智能的边界（The Deterministic/Intelligent Divide）

Life Index 对"何时用确定性代码、何时用 LLM"有**明确不可混淆的边界**：

| 操作类型 | 必须确定性 | 允许 LLM |
|---|---|---|
| 写入日志、读取日志 | ✅ | ❌ |
| 索引构建、索引读取 | ✅ | ❌ |
| 元数据提取（frontmatter 解析） | ✅ | ❌ |
| 关键词搜索（FTS5） | ✅ | ❌ |
| Entity Graph 解析与关键词排序 | ✅ | ❌ |
| Schema 迁移（字段补齐） | ✅ | 补齐值允许 |
| 年度/月度回顾叙事 | ❌ | ✅ |
| Query 改写、意图拆解 | ❌ | ✅ |
| 搜索结果二次筛选与摘要 | ❌ | ✅ |
| 实体关系推理 | 基础推理必须确定 | 复杂语义允许 |

**核心规则**：
- **L2（CLI Core）内部不得调用 LLM**。所有 LLM 调用必须发生在 L3（Intelligence Layer）。
- L4 可以直通 L2（例如 GUI 时间线浏览 → CLI search），**绕过 L3**。这是为了保证日常高频操作的延迟与离线可用。
- L3 必须通过 L2 访问数据，**不得直接读写 L1 文件**。

### §1.6 向下兼容（Backward Compatibility）

用户**今天写下的日志，20 年后的 Life Index 必须仍能读取**。这是对用户承诺的不可退让部分。

**保证**：
- 用户数据目录结构的**顶层约定**（`Journals/YYYY/MM/`、`by-topic/`、`attachments/`、`INDEX.md`）永不变动
- Frontmatter 的**核心字段**（`title`、`date`、`content`）永远支持读取
- Schema 演进通过 `life-index migrate` 链式迁移实现，不得出现"旧版数据无法读取"的情况

**允许演进**：
- `.index/` 目录下的机器索引格式可以随版本演进（重建即可）
- Frontmatter 可以**新增**字段，但不得**移除或重定义**既有字段的语义
- 工具命令可以新增子命令，但不得删除旧子命令（可标记 deprecated，至少保留两个主版本）

### §1.7 三条设计底线（Three Bottom Lines）

以下三句话摘自 README，提升为宪章不变量：

```
宁可功能简单，不可系统复杂
宁可人工维护，不可自动化陷阱
宁可牺牲性能，不可牺牲可靠性
```

每一次架构决策，若与上述三条冲突，**放弃该决策**。

### §1.8 长期主义原则（Long-Termism）

当架构决策涉及**高迁移成本**（schema、数据格式、ID 体系、entity 分类、存储格式），应**优先付当下成本**，而非等规模放大后被迫迁移。低迁移成本决策（具体实现、参数、UI、呈现层阈值）按当下 ROI 排序。

**判断方法**：问"如果半年后想反转，需要多大代价？"——代价高的决策属于本原则覆盖范围。

**与 §1.6（向下兼容）的关系**：向下兼容保证"旧数据在新系统可读"；长期主义原则保证"新系统不选会锁死未来选项的捷径"。二者互补：前者防断裂，后者防债务。

**违宪示例**：
- ❌ 为赶交付选择"先不用 schema，以后再补"——entity 分类的迁移成本随日志量线性上升
- ❌ 在 L1（Data Layer）引入"临时"字段用于短期需求——临时字段永久化是 50 年系统的最大技术债务来源
- ✅ 先投资 schema 定义与 pilot 验证，再批量标注——当下成本高，但避免了半年后重构 65 篇日志的 frontmatter

### §1.9 Agent-Native 模块原则（Agent-Native Module Principle）

Life Index 是 **agent ecosystem 的 CLI 基元层**，不是独立的 LLM 应用。高级功能可以智能、长程、慢速、需要多轮检索与综合，但其形态必须是：Life Index 提供可审计的证据、索引、测算、骨架与提示脚手架，由 Host Agent + Skill 负责语言合成与解释。

**核心规则**：
- Core 与产品 CLI 路径不得持有、配置或调用任何 LLM，也不得选择 provider
- Core 应输出确定性数据或可审计脚手架（如 search 结果、entity graph、aggregate/analyze 结果、evidence pack、claim envelope、scaffolded prompt、agent instructions）
- 改写、合成、解释、对话、翻译、摘要、情感判断等语言工作由 Host Agent + Skill 完成

Host Agent + Skill own provider selection and all planning, multi-hop reasoning, orchestration, interpretation, and synthesis.

The accepted `--synthesize` flag currently runs with no LLM injection and emits no `answer`.

#163 owns the future deprecation warning, deterministic equivalence proof, and unreachable LLM-path cleanup.

2026-06-03 的旧 sanctioned 解析序列与 Core 直接 provider fallback 许可现已被本条取代；Core 不得为无宿主场景建立 provider/client 路径。该职责处置不声称 #163 已实现，也不改变当前 runtime 或数据契约。

**明确禁止**：
- ❌ Core 或产品 CLI 路径隐含 bundled LLM、provider client、API key 读取或外部 LLM 请求
- ❌ 为每个高级模块维护隐藏的 per-module provider 配置
- ❌ 在未获得用户显式 opt-in 且未说明 provider / 数据暴露范围的情况下，将用户日志片段发往云端 LLM
- ❌ 为高级模块新增只服务该模块、且承担语言/解释工作的专用 L2 工具，以绕过 L3 编排边界

**明确允许**：
- ✅ Core 输出 `evidence_pack`、`claim_envelope`、`scaffolded_prompt`、`agent_instructions` 等，交由 Host Agent + Skill 合成
- ✅ Core 内部使用确定性算法、规则引擎、模板填充、FTS、聚合测算、entity graph 与索引树导航
- ✅ Host Agent 在 Core 之外选择 provider，并按用户授权与数据最小化边界消费 Core 证据

**判断方法**：问"如果 Core 没有配置任何 LLM provider，它是否仍能完成其核心价值？"

- 能输出确定性结果、证据包、候选集、骨架或可执行提示 → 合宪
- 只能在 Core 自己调用 LLM 后才有核心价值 → 违宪

**与 §1.5 的关系**：
- §1.5 划定 "L2 不得调 LLM" 的层级边界
- §1.9 划定 "Core 不得拥有 provider 或智能职责" 的架构边界
- 二者互补：§1.5 防层级泄漏，§1.9 将 provider 选择与智能统一交给 Host Agent + Skill

**违宪示例**：
- ❌ `life-index write` outbound 调用 LLM 做元数据抽取
- ❌ `life-index smart-search` 初始化 OpenAI-compatible client 并合成答案
- ❌ Memoir Engine / Digital Soul / 虚拟家属对话模块各自要求独立 API key 并直接生成最终叙事

**合宪示例**：
- ✅ `life-index write` 只写 Markdown + deterministic frontmatter；语义抽取由 Host Agent + Skill 完成
- ✅ `life-index smart-search` 输出 evidence pack 与 scaffolded prompt；Host Agent 负责最终答案
- ✅ Memoir Engine 以 Skill 组织章节骨架、证据索引、引用边界与写作提示；Host Agent 负责叙事文字

### §1.10 模块-基础层契约边界（Module-Foundation Contract Boundary）

Life Index CLI 的职责是为 Agent 生态提供**确定性、稳定、可组合的基元层（L1/L2）**：读写、索引、检索、聚合、entity、eval、health、index navigation 等基础能力，以稳定 JSON 契约、显式 schema 版本与可观测错误码暴露。高级 L3 / L4 模块（自传引擎、心潮地图、数字家书等）可以**智能、长程、慢速、有自己的工作流状态**，但其默认形态必须围绕 CLI 基元构建，**不修改、不依赖 CLI core 内部实现**，也不在 L1 数据真相源外建立第二个权威写入点。

**核心规则**：

1. **模块消费稳定契约**：模块默认通过稳定 CLI 契约消费基础能力。稳定面 = **JSON shape + 字段语义 + 错误码 + 关键性能 SLO**，四者构成模块可信赖的契约。
2. **模块状态归属分离**：
   - **数据状态**（journal、frontmatter、entity_graph、metrics）仍归 L1/L2，§2.2 不变；
   - **过程状态**（run_id 索引的中间产物：cursor、checkpoint、迭代中间结论、模块本地缓存）允许存放在模块自己的物理目录中，仍受 §1.1 数据主权与 §1.9 Agent-Native 模块原则约束（不外发、可清除、不进入 L1 真相源）。
3. **模块本地目录**：模块-local 状态应存放在模块自己的安装目录下（例如 `.openclaw/workspace/skills/life-index/models/{module_name}/`，或等价 module-owned 子目录），**不得**写入 `~/Documents/Life-Index` 用户数据目录。
4. **热插拔是契约解耦，不是动态加载**：「热插拔」指模块通过 CLI JSON-in/JSON-out 或 Python import (`tools.*` 公开 API) 调用基础层，物理上可以是独立仓库、独立目录、独立 Python 包；**不引入** plugin loader / dynamic discovery / entry-point 注册机制。
5. **基元升格回流流程**：当**多个模块**在生产路径上重复需要同一项**确定性、跨模块复用、低 LLM 含量、对 50 年数据语义有跨时间稳定性**的基元时，或当开发者/用户**明确判定**某项基元具备跨模块长期价值时，必须通过 RFC 流程将其升格为 L2 CLI 原语。不满足「确定性 ∧ 低 LLM ∧ 长期语义稳定」且未获明确 developer/user determination → 留在模块本地。CLI 的扩张必须以 RFC 与 substantive gate 为代价；模块的扩张以模块自己为代价。

**明确禁止**：
- ❌ 模块绕过 CLI 直接读写 L1 文件（违反 §1.4 跨层调用）
- ❌ 模块在 L2 中实现承担语言/解释职责的专用工具以绕过 Agent-Native 模块原则（违反 §1.5 + §1.9）
- ❌ 在 CLI core 中提前实现尚无真实消费者的工作流原语（违反 §1.7「宁可功能简单」+ §1.8 长期主义）
- ❌ 模块在 `~/Documents/Life-Index` 下创建可写模块路径（违反 §1.1 数据主权）
- ❌ 将 plugin loader / runtime registry 塞进 L2（违反 §1.7 简单底线）

**明确允许**：
- ✅ 模块本地持有 cursor、checkpoint、wiki、router、tree 等工作流状态
- ✅ 模块围绕 CLI 输出做编排、叙事、人格化、创作（保留证据、限制与 provenance）
- ✅ 模块通过稳定 CLI JSON 契约消费 L2 基元
- ✅ 多个模块共同需要的确定性基元通过 RFC 升格为 CLI L2 工具

**与 §2.2 的关系**：
§2.2 的「L3 必须是无状态的编排层」经本条解释为「L3 不得持有长期用户数据真相源」；模块-local 过程状态（非用户数据）允许存在，但不得替代 L1/L2 的数据职责。

**与 §1.9 的关系**：
§1.9 管「Core 不持 LLM，provider 与智能归 Host Agent + Skill」，§1.10 管「模块默认不修改基础层」；二者构成 agent-native 模块的两条不变量。

<!-- PLATFORM-SSOT:CORE-ADMISSION-DOMAINS:START -->
#### Active §1.10 closed Core admission domains

The former §1.9 P0→P1→P2→deterministic-only direct provider-fallback
direction is superseded. Host Agent + Skill own provider selection and all
planning, multi-hop reasoning, orchestration, interpretation, and synthesis;
Core remains deterministic; GUI remains presentation-only; and an optional
Gateway cannot own intelligence or semantics. The accepted `--synthesize`
flag currently runs through the product CLI with no LLM injection and no
`answer`; #163 owns the future deprecation warning, deterministic equivalence
proof, and unreachable LLM-path cleanup.

| ID | Active closed Core admission domain |
|---|---|
| C1 | Canonical journal and attachment mutation |
| C2 | Schema, validation, migration, transaction, locking, and audit |
| C3 | Deterministic indexing, retrieval, freshness, and evidence navigation |
| C4 | Deterministic aggregation and analysis |
| C5 | Entity graph |
| C6 | Integrity, health, backup, restore, and recovery |
| C7 | Deterministic contract and eval verification |

The C1–C7 identifiers are additive labels; they do not rename or weaken the
exact approved domain names. These seven domains are active Charter authority.
CHARTER.md §1.10 is the sole list authority; lower-level documents must reference
C1–C7 and must not duplicate domain descriptions. The enumeration is closed.
Every added Core domain requires new Human Owner substantive approval.

Human Owner approval may replace only second-production-consumer evidence. It
cannot waive determinism, low/zero LLM content, cross-time semantic stability,
RFC/substantive-gate evidence, or any other current Charter admission constraint.

**Stable non-Core classification rules**:

- `Distribution/Host Operations` is the sole bounded non-Core category. It is
  limited to install, version, and host-playbook lifecycle operations.
  Co-packaging or shared command dispatch grants no Core authority. It cannot
  own canonical journal, frontmatter, entity, or search semantics; be a Core
  correctness dependency; or create Core-admission precedent.
- `weather` is the sole named `Legacy External Adapter` compatibility exception.
  It is optional, tracked by #166, cannot decide canonical journal-write
  success, and creates no Core-admission precedent.
- Any new Core domain, non-Core category, or compatibility exception requires
  new Human Owner substantive approval.

`CHARTER.md §1.10` is the sole authority for the stable C1–C7 and non-Core
classification rules and the sole named compatibility exception.
`docs/ARCHITECTURE.md` owns only the exhaustive current 31-route mapping under
those rules; it does not own or duplicate them.

**Substantive-gate ratification record**:

- **Rationale**: align stale §1.9 fallback language with APEX and make Core
  admission reviewable against one closed, long-lived set of domains.
- **Opposition addressed**: (1) removing a standalone provider fallback may
  inconvenience direct CLI users, so #163 retains the already accepted
  no-op/no-answer `--synthesize` flag for at least two major versions and adds
  an explicit deprecation warning; (2) a
  closed list may delay a valuable primitive, so each addition remains possible
  through new Human Owner substantive approval without weakening the other
  admission criteria.
- **Impact**: this ratification affects §1.9 / §1.10 interpretation and the public
  architecture, API, CI, and Skill pointers only. It does not implement #163,
  #162, #165, or #164 and does not change runtime or data contracts.
- **Rollback**: any reversal or weakening requires a new §5.2 substantive
  amendment; no lower-level document can waive this ratification.
- **Gold Set regression**: PASS — observational evidence against the 2026-05-04
  baseline; D0 is docs-only and did not cause the result.
- **Human Owner ack**: COMPLETE — on 2026-07-10 the Human Owner substantively
  approved exactly C1–C7 and no additional domain.

This ratification lands D0 Charter authority only. It does not implement #163,
#162, #165, or #164 and does not change current runtime or data contracts.
<!-- PLATFORM-SSOT:CORE-ADMISSION-DOMAINS:END -->

### §1.11 召回优先检索真实模型（Recall-First Retrieval Truthfulness Model）

Life Index L2 检索层对用户的承诺是 **"不遗漏您每一个人生碎片"**。这要求 L2 默认行为必须是 **recall-first 而非 precision-first** —— 漏掉用户能用 token 描述的内容是宪法级违约；返回相关度较低但 token-match 的结果不是。

**L2 retrieval truthfulness model 三条**：

1. **Token-match 完整性**：L2 默认 retrieval 路径必须返回所有 token-match 文档（基于 FTS5 / 关键词 / entity tokenize）的完整 candidate set。不得在 retrieval 层做"相关度阈值截断"。

2. **Ranking 与 truncation 解耦**：
   - L2 search core 返回**完整** ranked result set + `total_matches` count
   - **截断只在 display layer**（CLI、JSON output）发生，且必须可显式解除（`--limit 0` 或等价开关）
   - 用户必须知道"还有多少没显示"（CLI 输出必须包含 total_matches 提示）

3. **Semantic / 向量检索从 L2 原子工具中移除**：
   - L2 retrieval 路径不调用向量检索，不构建向量索引，也不要求 embedding 模型。
   - `--semantic` / `--no-semantic` / `--semantic-policy` / `--semantic-weight` 作为向后兼容旗标保留，但其行为是 deprecated no-op；实际结果等同关键词 + Entity Graph。
   - Paraphrase、概念扩展、多跳解释与语义综合属于 calling agent (L3) 的编排责任，不进入 L2 原子工具。

**Paraphrase / 抽象语义类查询的责任分配**：
- L1（写入层）：通过 frontmatter tags / topics / entity aliases 富化 corpus，使 keyword retrieval 能命中更多语义变体（L1 enrichment 允许 LLM 协助，per §1.5）
- L3（agentic 层）：通过 query rewrite / multi-pass keyword 调用 L2，覆盖 paraphrase 场景（L3 允许 LLM）
- L2（CLI core）：**不承担 paraphrase 责任**，只忠实返回 token-match 结果

**违宪示例**：
- ❌ L2 默认 retrieval 在源头丢弃 candidate 因 BM25 score 低于阈值
- ❌ L2 默认 truncation = 20 且无 `total_matches` 提示
- ❌ L2 开 semantic / vector retrieval 并把结果混进主 result set
- ❌ 通过 "noise gate" 在 L2 默认路径过滤"低相关度"结果

**合宪示例**：
- ✅ L2 返回 137 条 token-match，display 默认显示 top 20 + "still 117 results, use --limit 0"
- ✅ `--semantic` flag 被接受为 deprecated no-op，旧 GUI / Agent 调用不报错但仍走关键词 + Entity Graph
- ✅ L3 agent 把 "想摆烂" rewrite 为 "to-do-list", "overload", "退缩" 多次调 L2 keyword search 后综合

**与其他条款的关系**：
- 与 §1.5：§1.5 划定"L2 不得调 LLM"层级边界；§1.11 进一步划定"L2 retrieval 不得调向量检索"产品承诺边界。二者互补：§1.5 防 LLM 渗透，§1.11 防"概率性 retrieval"渗透 L2 真相承诺。
- 与 §1.6（向下兼容）：本条不修改任何 L1 数据格式；只规约 L2 runtime 行为。旧 `--semantic*` CLI flags 保留为 no-op 兼容层。
- 与 §1.7（三条底线）：reinforced —— L2 keyword-only + Entity Graph 简单可审计；向量阈值/noise gate 调参是自动化陷阱；keyword retrieval 比 hybrid 更快且更 deterministic。
- 与 §1.10（模块-基础层契约）：reinforced —— §1.11 强化 L2 作为基元层 / L3 作为编排层的分工。
- 与 §3.1（搜索三层分离）：§3.1 已规约 retrieval 不得硬截断 + 必须返回 total_available + display 支持 --limit/--offset；§1.11 把这个实现层规约升格为产品承诺级不变量。
- 与 §3.2：见 §3.2 amendment note（搜索地基收紧为关键词 + Entity Graph；旧向量双管道不再是 L2 原语）。
- 与 §4.1（架构违宪）："在 retrieval / ranking 层硬切 top-K" 已是违宪；§1.11 强化此条并扩展到"开启向量检索作为 L2 路径"。

**§5.3 保护**：本条 §1.11 加入 §5.3 不可弱化清单 —— 只允许变得更严，不允许变得更松。未来"为让 paraphrase 数字好看而恢复 in-tool vector / hybrid retrieval"的提案，必须先通过 §5.2 修订本条。

**触发场景与起源**：v1.2.0 cycle2 absorption 跑出 eval baseline 后，CTO 与主理人 surface 两个长期 loophole：(1) semantic 阈值 dilemma（高漏低噪）；(2) hard truncation 20 与"不遗漏"承诺冲突。2026-06-28 的 108-query golden set 对比进一步确认 keyword 与 keyword+semantic 四项指标完全相同且 5 个失败未救回，因此 L2 vector / semantic retrieval 从 opt-in 收紧为 deprecated no-op。本条 §1.11 enshrine 产品承诺为宪法不变量，统一 runtime 方向。详见 RFC-2026-05-23-l2-recall-first-truthfulness-model 与 ADR-028。

### §1.12 运行时/平台可移植性（Runtime & Platform Portability）

Life Index 是 agent 生态的基元层；它与 agent runtime、宿主平台的集成必须可移植：更换 agent runtime（Hermes / Claude Code / Codex 等）或宿主平台（Linux / macOS / Windows+WSL）时，只应改配置，不应改代码。

**核心规则**：
- Agent 集成走标准协议（如 ACP），经配置选择具体 runtime（如 `acp_command`）；不得把某 runtime 私有 API 形状写进代码逻辑。
- Runtime / 平台特异性（启动命令、路径、venv、数据目录、端口、跨边界方式）一律进配置 + runbook，不得成为代码硬编码分支。
- Backing LLM / provider 由 runtime 自持、对 Life Index 不可见（承 §1.9）。

**明确禁止**：
- ❌ 代码中 `if runtime == "<名字>"` 排他特例分支，使其它合规 runtime 失效。
- ❌ 把某 runtime 私有端点/字段形状（如某家 `/v1`、某家私有 JSON）当通用假设硬编码。
- ❌ 把平台特异路径（WSL `/home`、`/mnt`、Windows 盘符）写进代码而非配置。

**明确允许**：
- ✅ 针对流行 runtime 的专门适应，只能藏在 capability 探测或配置接缝之后，不破坏其它合规 runtime。
- ✅ 为不同平台提供不同默认配置 / runbook（非代码分支）。

**判断方法**：问"换 runtime 或换 OS，是只改配置、还是必须改代码？" 只改配置 → 合宪；必须改代码 → 违宪。

**与 §1.9 / §1.10 关系**：§1.9 防 LLM 捆绑；§1.10 定契约边界；§1.12 保 runtime / 平台可移植——三者正交。

---

## 第二章：层级宪章（Layer Charter）

本章详细规定第一章 §1.4 所述四层的权责边界。每层包含三部分：**职责**（MUST）、**禁止**（MUST NOT）、**调用对象**。

### §2.1 L4 · Interface Layer（CLI / GUI / 自然语言）

**职责**
- 接收人类或 Agent 的意图输入
- 将意图翻译为结构化调用
- 向用户呈现结果（呈现层的硬截断规则在此层发生）

**禁止**
- ❌ 在此层实现任何业务逻辑（全部下放 L2 或 L3）
- ❌ 直接读写用户数据文件（必须经 L2）
- ❌ 在此层硬编码任何搜索参数、阈值

**调用对象**：L2（确定性操作）或 L3（智能操作）

### §2.2 L3 · Intelligence Layer（Agent 编排 / LLM 调用）

**职责**
- Query 意图理解与改写
- 多工具编排（多轮 L2 调用）
- 结果筛选、摘要、叙事生成
- 处理语义模糊、需要"判断"的任务

**禁止**
- ❌ 绕过 L2 直接读写 L1 文件
- ❌ 在此层维护**长期用户数据真相源**（L3 不得替代 L1/L2 的数据职责；见 §1.10 对「数据状态 vs 过程状态」的区分）
- ❌ 创建不通过 L2 暴露的"独立能力"

**调用对象**：L2（通过 CLI JSON 接口或 Python import）

### §2.3 L2 · CLI Core Layer（确定性原子操作）

**职责**
- 实现所有确定性的数据读写、索引、检索原子操作
- 通过 CLI 命令和 Python 模块两种方式暴露能力
- 返回结构化 JSON，包含 `success`、`error`，以及工具自定义顶层字段（不得假设统一 `data` wrapper）

**禁止**
- ❌ **在此层调用任何 LLM**（重要：历史上多次 vibe coding 容易在此处越界）
- ❌ 假设自己被哪一层调用（必须对 L3 和 L4 透明等同）
- ❌ 维护独立的长期进程、守护进程、服务
- ❌ 引入第二个持久化存储（数据库服务等）

**调用对象**：L1（文件系统、机器索引）

### §2.4 L1 · Data Layer（纯文本 + 机器索引）

**职责**
- 承载用户所有数据的真相源
- 目录结构规范（见 `docs/ARCHITECTURE.md` §2 实现细节）
- `.index/` 下的机器副产物

**禁止**
- ❌ 用户数据以非人类可读格式存储
- ❌ 机器索引中存储"无法从源文件重建"的信息

**调用对象**：无（最底层）

---

## 第三章：搜索子系统专章

搜索是 Life Index 最复杂、历经最多轮迭代的子系统。本章对其施加额外的宪章级约束，以防止再次出现 Round 1-16 所呈现的"层级泄漏 / 参数蔓延 / 编排缺失"三大病。

### §3.1 三层分离（Retrieval / Ranking / Presentation）

搜索子系统内部必须严格分为三层，三层不得耦合：

```
Retrieval（检索层）：从索引中捞取候选集
  职责：返回 {candidates: [...], total_available: N}
  禁止：任何形式的 top-K 硬截断
  
Ranking（排序层）：为候选集打分 + 排序
  职责：RRF 融合、权重计算、返回完整有序列表 + scores
  禁止：做呈现层的决定（不知道要展示多少条）

Presentation（呈现层）：按调用方需求截断、格式化
  职责：根据 --limit/--offset 返回切片；返回 has_more 信号
  禁止：改动排序结果的相对顺序
```

**宪章级 API 契约**：
- 检索层 API 必须返回 `total_available` 字段
- 呈现层必须支持 `--limit N`（默认 20）与 `--offset N`（默认 0）
- 任何用户或 Agent 可通过增大 `--limit` 获取更多结果

### §3.2 关键词 + Entity Graph 作为确定性原语（Deterministic Primitive）

关键词检索（FTS5 + 元数据过滤 + Entity Graph 确定性扩展/加权）是 Life Index 的**确定性搜索原语**。这是搜索子系统的"地基"。

**地基的宪章级保证**：
- 同一查询、同一数据集、同一参数，**结果必须 100% 可复现**
- 检索执行路径**永不**包含 LLM 调用
- 所有参数集中在 `tools/lib/search_constants.py`，不得散布
- 延迟 p95 ≤ 500ms（关键词 + Entity Graph 路径 SLO）

**这条地基是不可替换的**。即使未来 LLM 能力飞跃、即使有更先进的端到端检索方案，本项目保留这条确定性地基，以保证离线可用、可观测、可回归测试。

> **§3.2 amendment（v1.7.0, 2026-06-28, WP-CLI-SEM-RM）**：本条 §3.2 旧版"双管道"表述已被收紧。向量 pipeline 不再作为 L2 原语存在；`--semantic*` 仅是 compatibility no-op。Agentic paraphrase / synthesis 由 L3 calling agent 通过多次确定性 keyword/entity 调用完成。

### §3.3 Agent 编排层的唯一合法位置

用户原始愿景中的"Agent 参与搜索"—— 包括 query 改写、多轮搜索、结果筛选、摘要生成 —— 以及未来高级模组中的证据组装、长程分析、人格化叙事脚手架，**必须且只能**实现在 L3 层的独立编排模块或 workflow 中。

**宪章级约束**：
- 编排器**调用**关键词 / Entity Graph 检索和其他 L2 工具，**不得修改**这些确定性工具的内部实现
- 编排器暴露为独立命令（如 `life-index smart-search`）或独立模块
- `life-index search` 保持纯关键词 / Entity Graph 行为，永不加载 LLM
- 编排器必须遵守 §1.9：Core 路径不得持有、配置或调用 LLM；provider 选择与 synthesis 由 Host Agent + Skill 完成
- 编排器延迟 p95 ≤ 8s（默认 deterministic/scaffold 路径不应依赖远程 LLM）

**高级模组（那年今日、心潮地图、自传引擎、数字灵魂等）的实现方式**：
- 每个模组是**编排器的一个 workflow**，或**独立的 L3 模块调用 L2 工具**
- **禁止**为每个模组开发承担语言/解释职责的专用 L2 工具（违反 §1.5 + §1.9）
- 允许为模组开发专用的 prompt 模板、编排逻辑、证据组装规则与确定性测算流程
- 模组默认输出 deterministic 产物（evidence pack、claim envelope、scaffolded prompt、结构化数据），由 calling agent 完成语言合成

---

## 第四章：反模式黑名单（Anti-Patterns）

以下行为在任何情况下均为**违宪行为**。CI、PR review、Agent 均应主动拦截。

### §4.1 架构违宪

- ❌ 在 L2（CLI Core）代码中调用任何 LLM API
- ❌ 在 L4 或 L3 实现绕过 L2 的数据读写路径
- ❌ 跨层调用（例如 L4 直接调 L1、L3 直接改 `.index/` 文件）
- ❌ 在 retrieval / ranking 层硬切 top-K
- ❌ 将 Agent 编排逻辑写进 L2 search/index code
- ❌ 模块默认路径隐含 bundled LLM 或 provider client（违反 §1.9）
- ❌ 模块维护隐藏的 per-module provider 配置（违反 §1.9）
- ❌ 为高级模块开发承担语言/解释职责的专用 L2 工具以绕过 Agent-Native 模块原则（违反 §1.5 + §1.9）
- ❌ 为未来可能有用的需求提前设计（违反 YAGNI）
- ❌ 新增与 CLI 契约不一致的并行接口（MCP server、独立 HTTP API 等）
- ❌ 代码中以 runtime 名称做排他分支（`if runtime == "X"`），使其它合规 runtime 功能断裂（违反 §1.12）
- ❌ 把某 runtime 私有端点 / 字段形状当通用假设硬编码，破坏跨 runtime 可移植性（违反 §1.12）
- ❌ 将平台特异路径（WSL `/home`、`/mnt`、Windows 盘符等）写进代码而非配置（违反 §1.12）

### §4.2 数据违宪

- ❌ 用户日志内容以非 Markdown 格式存储
- ❌ Frontmatter 核心字段（`title`、`date`、`content`）语义变更
- ❌ `~/Documents/Life-Index/` 目录顶层结构变更
- ❌ 引入"无法从源文件重建"的机器索引
- ❌ 在用户数据目录外创建第二个持久化写入点

### §4.3 治理违宪

- ❌ 让 `docs/ARCHITECTURE.md` 与代码脱节超过一个 Round
- ❌ 新增不在 `search_constants.py` 管辖的搜索阈值
- ❌ 在没有 Gold Set 回归通过的情况下合入搜索相关 PR
- ❌ 在宪章级决策上使用 ADR（应使用 RFC + CHARTER 修订）
- ❌ 在单个 Round 内同时做"功能新增"和"治理重构"
- ❌ 绕过本宪章第五章「修订流程」直接修改本宪章

### §4.4 测试违宪

- ❌ 向真实用户数据目录 `~/Documents/Life-Index/` 写入测试数据
- ❌ 测试不使用临时目录或 `LIFE_INDEX_DATA_DIR` override
- ❌ 删除失败的测试而不是修复根因

### §4.5 搜索性能 SLO（Service Level Objectives）

搜索是 Life Index 的核心能力。以下性能指标为**硬性契约**，任何 PR 导致指标下降 ≥3% 必须在 PR 描述中说明原因并附 RFC。

| 指标 | 目标 | 实测基线（Round 17, 2026-05-01） | 备注 |
|------|------|------|------|
| `search` 命令 p95 延迟 | ≤ 500ms | ~20ms (FTS+L2, 无语义) | 索引新鲜状态下，不含首次构建 |
| `smart-search` 命令 p95 延迟 | ≤ 8s | 待测（依赖 LLM API） | 降级模式 ≤ 500ms |
| Gold Set Recall@5 | ≥ 基线值 | **0.3836**（keyword-only, 85 queries） | 每次索引变更后回归 |
| Gold Set P@5 | ≥ 基线值 | **0.3565**（keyword-only, 85 queries） | 每次索引变更后回归 |
| Gold Set MRR@5 | ≥ 基线值 | **0.2716**（keyword-only, 85 queries） | 每次索引变更后回归 |

**PR 合规规则**：
- 指标下降 ≥3% → PR 描述中必须附 RFC 说明
- 指标下降 ≥10% → PR 不得合并，必须修复或发起宪章修订

**实测环境**：Windows 11, Python 3.12, SSD, 本地数据 68 篇日志, commit 53428b1

> **注意（2026-06-28）**：上表为 Round 17 冻结基线，用作**历史地板**而非当前实测。WP-CLI-SEM-RM 当前 108-query gate 以 keyword/default 指标为准（MRR@5 0.6259 / Recall@5 0.9231 / P@5 0.5351 / nDCG@5 0.6602）。正式 SLO 基线更新需走 §5.2 宪章修订流程。当前回归门控应以 `tests/eval/baselines/` 中最新冻结 baseline 为准。

---

## 第五章：宪章修订流程

本宪章**不是刻在石头上的**。但修订门槛必须足够高，以防止临时需求稀释不变量。

### §5.1 触发条件

以下情况可发起宪章修订：
- 发现当前条款在某个**真实场景**下产生反效果（非假想场景）
- 外部强制因素（操作系统 API 变更、核心依赖停止维护等）
- 完成一个里程碑后，基于新能力的有意识演进

### §5.2 修订流程

1. **起草修订案**：起草一份明确的宪章修订案
   - 说明当前条款
   - 说明目标条款
   - 说明触发场景与证据
   - 说明潜在影响与回滚方案
2. **Gold Set 回归**：运行完整的 Gold Set 测试，确认修订不导致退化
3. **Substantive gate（4 项齐备方可 land）**：
   - **rationale**：为什么要改、解决什么问题（在 RFC §1 写明）
   - **反对意见 addressed**：CTO 列出至少 2 条反对意见、提案如何回应（在 RFC §4 或同等位置写明）
   - **影响清单**：改哪些文档、哪些 invariants 受影响、是否破坏既有 RFC（在 RFC §5 或同等位置写明）
   - **主理人 ack 签字**：作者本人书面 ack（不可委托）

   四项齐备 → 立即 land。**起草到 land 无强制最短时间间隔**（替代旧版「24 小时冷静期」与「三方评审覆盖」机制）。
4. **版本递增**：CHARTER.md 头部版本号递增，`修订次数` +1
5. **联动更新**：
   - 更新 `docs/ARCHITECTURE.md` 对应实现章节
   - 将公开安全的 rationale 留在 `CHARTER.md` / public ADR / public RFC；过程性修订记录归档到本地私有治理层

### §5.3 不可修订的章节

**本条（§5.3）本身、§1.1（数据主权）、§1.2（纯文本永久性）、§1.6（向下兼容）、§1.11（召回优先检索真实模型）** 不得被修订为更弱的约束。**只允许变得更严、不允许变得更松**。

这是对用户数据承诺的终极保护。

---

## 附录 A：术语定义

| 术语 | 定义 |
|---|---|
| SSOT | Single Source of Truth，单一权威来源 |
| Agent | 基于 LLM 的自主编排代理（Claude、GPT、OpenClaw 等） |
| Agent-Native | 系统从第一行代码起就为 Agent 设计（≠ Agent-First） |
| 检索原语 | FTS5 关键词管道 + 元数据过滤 + Entity Graph 确定性扩展/加权 |
| 编排器 | L3 层调用多个 L2 工具完成复合任务的模块 |
| Gold Set | 用于持续回归搜索质量的标注 query/relevant 数据集 |
| 不变量 | Invariant，本宪章中不随版本演进的原则 |
| RFC | Request For Comments，宪章修订提案文档 |

## 附录 B：文档层级关系

```
CHARTER.md（本文件，最高权威）
    │
    ├── docs/ARCHITECTURE.md（当前实现如何满足宪章）
    ├── docs/API.md（CLI 接口契约）
    │
    ├── SKILL.md（Agent 技能入口）
    │       └── AGENT_ONBOARDING.md（Agent 安装流程）
    │
```

**冲突仲裁**：上层文档覆盖下层。CHARTER 是最高。

## 附录 D：工程纪律与仓库卫生

### D.1 设计底线

```
宁可功能简单，不可系统复杂
宁可人工维护，不可自动化陷阱
宁可牺牲性能，不可牺牲可靠性
```

### D.2 仓库卫生规则（强制）

1. **`.gitignore` 不是后悔药**：新增 `.gitignore` 条目后，必须同步检查并清理已被 git 追踪的历史文件。
   ```bash
   # Push 前必做检查：输出应为空
   git ls-files | git check-ignore --stdin
   ```
2. **禁止提交过程性/会话性文件**：`.handoff.md`、recovery patch、调试标记、临时日志等不得进入 git。
3. **禁止提交测试运行时产物**：`.pytest_tmp/`、`.pytest_cache/`、`.mypy_cache/`、锁文件、pickle、模型缓存等。CI 运行产物由 CI 环境自行清理，不得带回仓库。
4. **禁止提交个人环境配置**：虚拟环境目录、IDE 配置、本地部署脚本中的用户名/路径等。
5. **Commit 前自查**：`git status` 中出现 `.pytest_tmp`、`.recovery`、`.handoff.md` 等条目时，禁止直接 `git add -A`。

---

## 附录 C：签署

> Life Index 是一位父亲写给女儿的数字家书。这份宪章是这份家书的**架构承诺**。
>
> 我承诺：在此宪章约束下开发这个项目，至少 50 年。
> 如果某一天我不在了，希望下一个接手的人也能尊重这份宪章。
>
> —— Life Index Developer，2026-04-23

---

*本宪章首次批准于 Round 17 · Task 1*
*修订 1：Round 17 Phase 6-B — §4.5 搜索性能 SLO（2026-05-01）*
*修订 2：Round 19 Phase 1-C — §1.8 长期主义原则（2026-05-02）*
*修订 3：Round 20 — §1.9 Agent-Native 模块原则（2026-05-14，作者授权跳过 §5.2 24h cooldown）*
*修订 4：Round 20 — §1.10 模块-基础层契约边界（2026-05-14，记录的三方评审覆盖 §5.2 24h cooldown，详见 RFC）*
*修订 5：2026-05-20 — §5 修订流程改为 substantive gate（废除 24h cooldown 与三方评审覆盖机制；过程记录已归档到本地私有治理层）*
*修订 6：2026-05-23 — §1.11 召回优先检索真实模型（RFC-2026-05-23-l2-recall-first-truthfulness-model；§1.11 加入 §5.3 不可弱化清单）*
*修订 7：2026-06-14 — §1.12 运行时/平台可移植性（RFC-2026-06-14-runtime-platform-portability；§4.1 追加 3 条镜像反模式）*
*修订 8：2026-06-18 — 新增「北极星（Agent-Native 最高不变量 · APEX）」最高实质原则（RFC-2026-06-18-agent-native-north-star-apex；owner 亲签）*
*修订 9：2026-06-19 — 新增 APEX 第 6 点「评估即咨询，非闸门（Evaluation is Advisory, not a Gate）」（RFC-2026-06-19-evaluation-advisory-not-gate；owner 亲签）*
*修订 10：2026-07-10 — Owner 批准 C1–C7 闭合 Core 准入域，取代 §1.9 Core provider fallback，并完成 §5.2 D0 ratification record*
*下一次强制性评审：2026-07-23*
