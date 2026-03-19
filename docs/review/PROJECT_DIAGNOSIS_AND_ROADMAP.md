# Life Index Project Diagnosis and Roadmap

> **本文档职责**: 保存当前项目诊断结论，并提供未来 3 个阶段的执行路线图
> **目标读者**: 项目 Owner、CTO 视角评审者、后续执行的开发者 / Agent
> **SSOT 引用**: `README.md`、`SKILL.md`、`docs/ARCHITECTURE.md`、`docs/API.md`、`docs/CHANGELOG.md`
> **文档定位**: 本文档属于 review-scoped 开发治理文档，不是运行时 SSOT；正式接口、工作流与 ADR 以上游 SSOT 文档为准
>
> **创建时间**: 2026-03-18
> **创建背景**: 基于一次 CTO 级别项目审视，目标是在不丢失评审结论的前提下，沉淀项目现状、关键问题与未来 3 个阶段的执行路线
> **当前状态**: 以 Agent-first + Local-first 为核心方向，工程基础良好，但 workflow clarity / tool boundary clarity 仍需优先收敛
> **后续状态更新**: 产品边界已在 `docs/PRODUCT_BOUNDARY.md` 中正式收敛；本文档保留 diagnosis / roadmap 视角
> **执行优先级更新**: v1.x 当前主线顺序已在 `docs/EXECUTION_PRIORITIES.md` 中正式收敛

---

## 0. Executive Summary

Life Index 当前最重要的事实不是“项目做坏了”，而是：**它已经具备了相当不错的 agent-first 雏形，但还没有完全从“工具集合”收敛成“工作流清晰、边界明确、体验稳定”的 agent-native 产品。**

从架构与工程视角看，这个项目方向总体正确：

- 坚持 **Local-first + Markdown/YAML**，数据主权和长期可读性极强
- 采用 **Agent-first + atomic tools**，总体边界设计优于常见“单体大工具”模式
- 搜索层已经有 **关键词管道 ∥ 语义管道 + RRF 融合**，明显高于普通 side project 水平
- 工程上具备 **测试、CI、typing、packaging、文档** 等较完整基础设施

但从产品化和 agent-native 落地角度，当前真正的主要矛盾不是“继续扩功能”，而是：

1. **canonical workflow 尚未彻底收敛**：尤其是 write/search/edit 三条黄金路径的职责划分与异常路径
2. **Agent 与 Tool 的职责边界仍有隐性混叠**：部分流程依赖文档约定，而不是代码约束
3. **写入、增强、索引之间的同步/异步语义尚未完全定型**：容易引发后续复杂度上升
4. **分发体验的重要性高于 MCP 化**：当前阶段更应该优先保证一键安装与首轮体验，而不是过早协议化

**结论**：

- 方向保留，不建议推倒重来
- 核心架构保留，不建议现在为了“先进感”而重做 MCP
- 下一阶段优先级应当从“加新能力”切换为“澄清 workflow、固化边界、建立 eval、优化分发”

---

## 1. 项目现状诊断

## 1.1 已经成立的优势判断

### A. 数据层战略正确

项目明确坚持：

- 用户数据存储于 `~/Documents/Life-Index/`
- 项目代码与用户数据物理隔离
- 数据格式采用 Markdown + YAML frontmatter

这使得 Life Index 在以下维度上具备长期优势：

- **用户拥有绝对数据主权**
- **Agent 与人都易于阅读/修复/迁移数据**
- **不会被数据库模式、SaaS 服务或特定供应商锁死**
- **备份、导出、长周期保存非常自然**

这与 `docs/ARCHITECTURE.md` 中的核心原则完全一致：

- `1.1 Agent-First`
- `1.2 数据主权`
- `1.3 单层透明`

这是项目最值得保留的根基之一。

### B. Tool 分层总体健康

当前工具集已具备较合理的功能分拆：

- `write_journal`
- `search_journals`
- `edit_journal`
- `generate_abstract`
- `build_index`
- `query_weather`
- 统一入口 `tools/__main__.py`

这说明项目已经明确尝试将系统拆分成：

- **能力层（tool capability）**
- **流程层（skill / agent orchestration）**

这比把所有流程都塞进单个“超级工具”更接近 agent-native 的长期正确方向。

### C. 搜索架构已明显超出普通原型阶段

项目的检索系统不是简单关键词 grep，而是具备：

- `L1` 索引层（topic / project / tag）
- `L2` 元数据层（SQLite cache）
- `L3` 内容层（FTS5）
- 语义层（fastembed）
- RRF 融合排序

这是一个有明确设计意图的 retrieval architecture，而不只是“能搜到一点东西”。

### D. 工程成熟度已进入 disciplined 状态

根据仓库内现有配置与测试资产：

- `pyproject.toml` 完整定义打包、入口点与工具链
- `.github/workflows/ci.yml`、`release.yml` 已存在
- 测试、typing、formatting、linting 配置较完整
- `docs/API.md`、`docs/ARCHITECTURE.md`、`SKILL.md`、`AGENTS.md` 构成较清晰的文档体系

所以问题不是“仓库脏乱差”，而是**系统认知模型还没有被完全压缩成一个稳定产品契约**。

---

## 1.2 当前最关键的问题，不在代码质量，而在产品/系统边界

当前项目最需要解决的不是“再拆多少模块”，而是：

> **谁负责决策、谁负责执行、谁负责确认、谁负责兜底，还没有被系统性地讲清楚。**

这具体表现为几个层面。

### A. Tool 已经拆了，但 canonical workflow 还不够收敛

对于“写日志”这件事，目前存在多层职责：

- 内容写入
- frontmatter 校验
- 天气查询
- metadata / mood / tags / abstract 补全
- 索引更新
- 用户确认

这些动作现在虽然分布在文档和代码里，但**单一真相（single operational truth）仍不够清晰**。

实际风险是：

- 人和 Agent 会对“这一步该谁做”产生分歧
- 后续优化会在 Tool 内不断堆叠“聪明逻辑”
- 你自己都会逐渐看不清系统真正的运行路径

### B. Workflow orchestration 主要存在于文档，不在代码约束中

当前 write / edit / weather 的正确流程，大量依赖：

- `SKILL.md`
- `references/WEATHER_FLOW.md`
- `docs/API.md`

例如：

- `write_journal` 会返回 `needs_confirmation`
- Agent 应当读取该 flag 并继续确认
- `edit_journal` 在修改 location 时，并不会自动补 weather
- 正确流程应由 Agent 先调用 `query_weather` 再调用 `edit_journal`

这些都说明：**workflow correctness 目前主要靠文档约定，而不是代码层约束。**

这不是说当前设计错误，而是说明：

- 如果要长期演进，必须把这些边界显式固化
- 否则系统会持续依赖“知道内情的人”来正确使用

### C. `write_journal` 的职责仍值得再做一次边界审视

从 CTO 视角，`write_journal` 是当前最需要重新审视的工具。

真正需要明确的是三层语义：

#### 必需层（必须成功，否则写失败）

- frontmatter / schema 校验
- journal 文件原子写入

#### 增强层（失败不应阻断主体写入）

- 天气补全
- abstract 补全
- tags / mood 推断（如果由 tool 负责）
- vector index 更新

#### 修复层（允许延后执行）

- rebuild / reconcile / repair index

如果这三层不被显式定义，`write_journal` 很容易在迭代中重新膨胀成高耦合入口。

### D. 当前更像“engine 已成”，但“experience contract 未完全封口”

从 repo 的角度，它已经像一个成熟的 engine；但从用户体验视角，它还没有完全变成一个稳定的 agent product。

换句话说：

- Tool contract 大体清楚
- Product / experience contract 还不够收口

这正是为什么当前优先级应该是 **workflow clarity**，而不是盲目扩功能。

---

## 1.3 明确记录：关于 MCP 的判断

当前阶段，不建议把 MCP 作为主线目标。

原因不是 MCP 不好，而是它**不是当前最主要矛盾**。

对 Life Index 来说，现阶段更重要的是：

- 把 workflow 讲清楚
- 把 tool / agent 边界讲清楚
- 把安装和首轮使用体验做顺
- 把核心能力的可靠性与评估做扎实

在这些尚未完全稳定之前，过早引入 MCP 往往会：

- 增加协议层复杂度
- 抬高安装/调试门槛
- 分散对真正产品问题的注意力

因此，本路线图采用如下立场：

> **先稳定能力模型，再考虑协议适配层。**

短期策略：

- **Skill-first + CLI-first**
- 优先一键安装、健康检查、首轮 journal flow

中长期：

- 当参数模型、错误模型、workflow 模型稳定后，再评估 MCP adapter 是否值得做

---

## 1.4 当前问题列表（供后续执行时对齐）

| 编号 | 问题 | 影响 | 优先级 |
|:---:|:---|:---|:---:|
| D-01 | write/search/edit 的 canonical workflow 未统一固化 | 导致后续优化与使用认知混乱 | P0 |
| D-02 | Agent vs Tool 的职责边界仍有隐性混叠 | 容易把判断逻辑重新塞回 tool | P0 |
| D-03 | `write_journal` 内部“写入/增强/索引”语义尚未完全分层 | 未来耦合和失败语义不稳定 | P0 |
| D-04 | workflow correctness 主要靠文档约定，缺少更强约束 | 容易因调用方忽略约定而出错 | P1 |
| D-05 | 评估体系尚未作为正式能力建立 | 优化难以形成可验证闭环 | P1 |
| D-06 | 分发/冷启动体验的重要性高于当前实际投入 | 阻碍真实用户使用与反馈 | P1 |
| D-07 | MCP 是否要做容易干扰主线判断 | 可能过早基础设施化 | P2 |

---

## 2. Workflow / Tool Boundary 专项诊断

本节用于专门保存“第二优先级”的判断，避免后续工作时丢失。

## 2.1 现有边界里，哪些是明确的

以下事实在文档和代码中已经比较明确：

### Agent 负责

- 从自然语言抽取结构化元数据候选
- 生成或整理摘要、情绪、标签等高层语义
- 处理确认交互（如 `needs_confirmation`）
- 在某些流程中串联多个工具（如先天气后编辑）

### Tool 负责

- 确定性执行：写入、编辑、搜索、索引、天气查询
- 参数校验和错误返回
- 与文件系统、本地索引、SQLite/FTS/向量层等做可靠交互

### 当前正确边界的大方向

> **Agent 负责理解、判断、追问、确认；Tool 负责确定性执行与结构化返回。**

这条原则后续应当被保留，而不是被更多“智能工具逻辑”稀释。

---

## 2.2 当前最值得警惕的边界风险

### A. `write_journal` 容易重新演变成“超级入口”

如果未来继续将以下能力不断内聚到 `write_journal`：

- 天气决策
- 摘要生成
- 元数据推断
- 全索引维护
- 用户确认逻辑

那么它会逐渐回到高耦合设计。

应当始终追问：

- 这是 deterministic execution 吗？
- 还是应由 Agent 决策？

### B. `edit_journal` 与 weather 流程不够自解释

当前正确做法更偏“隐式约定”：

1. Agent 先调用 `query_weather`
2. Agent 再调用 `edit_journal`

这说明：

- 流程本身合理
- 但接口可用性和自解释性还不够强

后续需要决定：

- 是继续保持纯粹分层，但补强文档/验证
- 还是提供更明确的 workflow helper / warning 机制

### C. 写入成功与索引成功是否必须绑定，尚需定论

这不是实现细节，而是产品语义问题：

- 用户最在乎的是“日志有没有保存”
- 系统其次才需要保证“它能否立刻被所有检索层搜到”

因此后续必须明确：

- 哪些索引是同步必需的
- 哪些索引可以 best-effort
- 哪些索引失败后可以 repair / reconcile

### D. workflow 目前以“知识”存在，而不是以“约束”存在

目前系统的正确运行很依赖熟悉项目的人知道：

- 什么情况下该追问
- 什么情况下必须确认
- 什么情况下要先调天气
- 什么情况下应该调用 rebuild/index

这意味着 workflow 还没有完全产品化。

---

## 2.3 这里明确给出 3 条黄金路径（后续工作基线）

### 黄金路径 A：捕获日志

用户自然语言输入
→ Agent 判断是否需要补充信息 / 确认
→ Agent 生成结构化字段候选
→ 调用 `write_journal`
→ 若返回 `needs_confirmation`，Agent 继续完成确认

### 黄金路径 B：检索日志

用户表达查找意图
→ Agent 判断查询类型（精确 / 模糊 / 概念性）
→ 调用 `search_journals`
→ Agent 结合返回结果做结果组织与摘要呈现

### 黄金路径 C：修订日志

用户指定已有日志或修改意图
→ Agent 定位目标 journal
→ 如涉及 location / weather 等耦合字段，先补足必要上下文
→ 调用 `edit_journal`
→ 必要时触发索引修复 / 一致性检查

后续所有优化，应优先围绕这三条路径做，而不是散点式加功能。

---

## 3. 未来 3 个阶段路线图

## 执行顺序总览

| Phase | 阶段 | 核心目标 | 预期产出 | 优先级 |
|:---:|:---|:---|:---|:---:|
| **P1** | Workflow Boundary Clarification | 澄清黄金路径与职责边界 | 统一 workflow 契约、责任矩阵、失败语义 | P0 |
| **P2** | Reliability & Evaluation Hardening | 稳定核心能力并建立验证闭环 | eval 体系、失败恢复策略、检索/写入可靠性基线 | P1 |
| **P3** | Distribution & Product Readiness | 优化真实使用与分发体验 | 一键安装、冷启动流程、文档收口、是否 MCP 的再评估 | P1 |

---

## Phase 1：Workflow Boundary Clarification

### 目标

把 Life Index 从“工具能力集合”进一步推进为“工作流清晰的 agent product”，优先解决你当前最真实的困惑：

- 到底有哪些 canonical workflows
- 各工具到底负责什么
- Agent 与 Tool 的边界在哪
- 哪些步骤必须同步，哪些可以降级/延后

### 问题根因

当前项目已经拆出了足够多的模块，但**缺少一份收口后的 operational contract**，导致：

- 文档中有流程
- 代码中有能力
- 但系统整体行为还没有被压缩成一致的认知模型

### 具体任务

1. 输出一份 **Tool Responsibility Matrix**
   - 每个工具的职责、输入、输出、不可做的事
   - Agent 负责哪些决策，Tool 负责哪些执行

2. 输出一份 **Canonical Workflow Spec**
   - 写日志 / 搜索日志 / 编辑日志 三条黄金路径
   - 每条路径的正常流、确认流、失败流、恢复流

3. 对 `write_journal` 做一次 **职责分层审计**
   - 必需层 / 增强层 / 修复层
   - 明确哪些失败应该阻断写入，哪些不应阻断

4. 对 weather/edit/search 等耦合点做一次 **边界澄清**
   - location 与 weather 的协同规则
   - edit 与 weather 是否需要 warning / validation
   - search 返回结果的“原始结果 vs Agent 整理结果”边界

5. 把关键结果沉淀到正式文档中
   - 不是只存在于会话中
   - 后续新 Agent 进场也能快速理解

### 验收标准

- [ ] 三条黄金路径被正式写成规范
- [ ] 每个工具的职责与边界清晰可表述
- [ ] `write_journal` 的失败语义与索引语义被明确
- [ ] 关于 MCP 的阶段性判断被正式记录，不再反复摇摆
- [ ] 新接手的 Agent 能仅通过文档理解“该怎么正确用工具”

### 交付物

- tool responsibility matrix
- canonical workflow spec
- write flow failure semantics note
- weather/edit boundary note

### 备注

**本阶段不以新增功能为目标。** 重点是收敛认知模型，而不是继续扩展表面积。

---

## Phase 2：Reliability & Evaluation Hardening

### 目标

在边界清晰之后，建立一套真正支撑演进的可靠性与评估闭环。

### 问题根因

如果没有 eval，后续任何“优化”都容易退化成主观感觉：

- 看起来更聪明了
- 好像更顺了
- 搜索似乎更准了

但没有数据和样例集，就很难知道系统是否真的变好。

### 具体任务

1. 建立 **workflow eval**
   - 准备一批真实写日志输入样本
   - 验证 Agent 是否能稳定选择正确流程与确认策略

2. 建立 **retrieval eval**
   - 查询 → 目标 journal 样本集
   - 分别测试 keyword / semantic / fusion 的质量
   - 明确哪些场景 semantic 真有增益

3. 建立 **reliability / failure injection eval**
   - 天气 API 失败
   - 向量索引损坏
   - FTS / metadata cache 不一致
   - 手工改文件后的 rebuild / reconcile 行为

4. 明确 **index consistency strategy**
   - 哪些 index 必须同步成功
   - 哪些 index 可以 best-effort
   - 是否需要 repair / reconcile 命令或流程

5. 审查关键 silent failure 点
   - 用户是否能区分“没有结果”与“能力不可用”
   - Tool 是否应返回更明确的 structured signal

### 验收标准

- [ ] 至少一套最小可重复的 workflow eval 样本集存在
- [ ] 至少一套 retrieval eval 样本集存在
- [ ] 关键失败路径被测试且有预期行为
- [ ] index consistency 策略被明确记录
- [ ] 后续任何优化都能以样本集做回归验证

### 交付物

- workflow eval cases
- retrieval eval cases
- failure injection checklist
- index consistency policy note

### 备注

本阶段的目标不是“让系统更复杂”，而是**让未来每一次改动都更可验证**。

---

## Phase 3：Distribution & Product Readiness

### 目标

把 Life Index 从“对熟悉项目的人很好用”，推进到“对普通安装者和未来用户也足够顺滑”。

### 问题根因

对于这类项目，**分发体验本身就是产品的一部分**。如果安装、初始化、健康检查、第一篇日志体验不顺，前面很多架构优势都无法转化成真实使用。

### 具体任务

1. 打磨 **cold start experience**
   - 安装
   - 初始化
   - health check
   - first write
   - first search

2. 优化 **一键安装与新手文档**
   - 普通用户路径
   - 开发者路径
   - 常见故障与恢复路径

3. 明确 **distribution strategy**
   - `pip install` / `uv tool install` / installer script 的主路径
   - 让用户不需要理解内部架构也能用起来

4. 再评估 **MCP 是否值得做成 adapter**
   - 前提：能力模型稳定、错误模型稳定、workflow 稳定
   - 结论可能是“继续不做”，也可能是“仅做适配层，不改内核”

5. 收口文档体系
   - 让 README / SKILL / API / 架构文档之间的边界更清晰
   - 让后续 agent 或开发者不必反复追问“从哪里开始”

### 验收标准

- [ ] 新用户可在短时间内完成安装与首次使用
- [ ] 安装/初始化/health/first-write/first-search 路径清晰可重复
- [ ] 文档对不同读者（用户/开发者/Agent）分层明确
- [ ] MCP 是否需要进入路线图，有明确阶段性结论

### 交付物

- distribution strategy note
- installation/onboarding checklist
- docs boundary cleanup plan
- MCP re-evaluation note

### 备注

只有当 P1、P2 基本稳定后，P3 的收益才会最大化。

---

## 4. 决策日志（本次评审结论归档）

| 日期 | 决策 | 理由 | 状态 |
|:---:|:---|:---|:---:|
| 2026-03-18 | 保留 Local-first + Markdown/YAML 路线 | 这是项目长期价值与差异化根基 | 已确认 |
| 2026-03-18 | 保留 Agent-first + atomic tools 路线 | 当前方向正确，不应回退为单体工具 | 已确认 |
| 2026-03-18 | 暂不以 MCP 作为主线 | 当前主要问题不在协议层，而在 workflow / boundary / distribution | 已确认 |
| 2026-03-18 | 将“workflow / tool boundary clarification”列为最高优先级之一 | 这是当前最大认知摩擦点，也是后续工作的基线 | 已确认 |
| 2026-03-18 | 暂不以“继续扩功能”为第一目标 | 先收敛认知模型，再谈功能扩展 | 已确认 |

---

## 5. 推荐的下一步动作（最小正确前进路径）

如果只允许选择一个最优先行动，应当是：

### Next Action

**产出一份更细的 Tool Responsibility Matrix + Canonical Workflow Spec。**

推荐最小范围：

1. 先只覆盖 `write_journal`、`edit_journal`、`query_weather`、`search_journals`
2. 对每个工具写清楚：
   - 它负责什么
   - 不负责什么
   - 哪些字段由 Agent 决策
   - 哪些失败阻断，哪些失败降级
3. 把“写日志 / 搜索 / 编辑”三条路径各自写出：
   - 正常流
   - 追问流
   - 确认流
   - 错误流

完成这一步之后，后续无论是做 reliability、eval，还是做安装体验与 MCP 再评估，都会清晰得多。

---

## 6. Execution Baseline (English)

This section is the **execution-grade layer** of the roadmap. It exists so that future humans or agents can execute the plan without relying on interpretation of the Chinese strategy sections above.

### 6.1 Execution Rule

Use the Chinese sections above for strategic intent.
Use this English section for:

- execution order
- artifact paths
- review gates
- TDD-oriented work sequence
- atomic commit slicing

If there is a conflict, this rule applies:

1. **Strategic intent** comes from Sections 0-5
2. **Execution procedure** comes from Section 6
3. **Tool/API truth** remains in `SKILL.md`, `docs/API.md`, and code

---

### 6.2 Phase 1 — Workflow Boundary Clarification

#### Objective

Define the canonical workflows and explicit responsibility boundaries between Agent and Tools.

#### Required artifacts

| Artifact | File path | Purpose | SSOT status |
|:---|:---|:---|:---:|
| Tool responsibility matrix | `docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md` | Define what each tool does and must not do | Yes |
| Canonical workflow spec | `docs/review/execution/CANONICAL_WORKFLOWS.md` | Define write/search/edit happy path, clarification path, confirmation path, failure path | Yes |
| Write failure semantics note | `docs/review/execution/WRITE_FAILURE_SEMANTICS.md` | Define blocking vs non-blocking behavior for write-related steps | Yes |
| Weather/edit boundary note | `docs/review/execution/WEATHER_EDIT_BOUNDARY.md` | Define location-weather coordination rules | Yes |

#### Test-first artifacts (must exist before implementation/refactor)

Create these scenario docs before changing workflow-related code or docs:

| Scenario set | File path | Minimum cases |
|:---|:---|:---:|
| Workflow scenarios | `docs/review/evals/WORKFLOW_SCENARIOS.md` | 10 |
| Boundary review checklist | `docs/review/evals/BOUNDARY_REVIEW_CHECKLIST.md` | 1 checklist |

Minimum workflow scenarios must include:

1. Write journal with complete metadata
2. Write journal with missing weather
3. Write journal requiring confirmation
4. Edit location without weather refresh
5. Edit location with pre-fetched weather
6. Search exact keyword
7. Search conceptually similar content
8. Search with no results
9. Weather API unavailable during write
10. Rebuild/index recovery after manual file change

#### Ordered execution steps

1. Create `docs/review/execution/` and `docs/review/evals/`
2. Write `docs/review/evals/WORKFLOW_SCENARIOS.md`
3. Write `docs/review/evals/BOUNDARY_REVIEW_CHECKLIST.md`
4. Write `docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md`
5. Write `docs/review/execution/CANONICAL_WORKFLOWS.md`
6. Write `docs/review/execution/WRITE_FAILURE_SEMANTICS.md`
7. Write `docs/review/execution/WEATHER_EDIT_BOUNDARY.md`
8. Review all four execution docs against the scenario set
9. Only then consider code or API adjustments

#### Parallelizable items

- `TOOL_RESPONSIBILITY_MATRIX.md` and `WORKFLOW_SCENARIOS.md` can be drafted in parallel
- `WRITE_FAILURE_SEMANTICS.md` and `WEATHER_EDIT_BOUNDARY.md` can be drafted in parallel after the canonical workflow skeleton exists

#### Blocking dependencies

- `CANONICAL_WORKFLOWS.md` must not be finalized before `WORKFLOW_SCENARIOS.md` exists
- No code refactor may start until all Phase 1 execution docs exist and pass review

#### Verifiable acceptance criteria

- [ ] `docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md` exists and each tool section includes: responsibilities, non-responsibilities, inputs, outputs, caller obligations, failure semantics, sync/async behavior
- [ ] `docs/review/execution/CANONICAL_WORKFLOWS.md` exists and includes write/search/edit workflows with happy path, clarification path, confirmation path, failure path
- [ ] `docs/review/execution/WRITE_FAILURE_SEMANTICS.md` explicitly classifies each write-related step as blocking, non-blocking, or repairable
- [ ] `docs/review/execution/WEATHER_EDIT_BOUNDARY.md` explicitly states what happens when location changes without weather refresh
- [ ] `docs/review/evals/WORKFLOW_SCENARIOS.md` contains at least 10 concrete scenarios
- [ ] All artifacts pass `docs/review/evals/BOUNDARY_REVIEW_CHECKLIST.md`

#### Review gate

Phase 2 cannot start until all Phase 1 artifacts exist and a reviewer can answer “yes” to every checklist item in `docs/review/evals/BOUNDARY_REVIEW_CHECKLIST.md`.

#### Allowed scope

- Documentation, specs, scenario cases, review checklists
- Small API clarifications only after docs are complete

#### Not in scope

- Major feature additions
- MCP migration
- Search algorithm changes

---

### 6.3 Phase 2 — Reliability & Evaluation Hardening

#### Objective

Turn the clarified workflows into a verifiable quality system.

#### Required artifacts

| Artifact | File path | Purpose | SSOT status |
|:---|:---|:---|:---:|
| Workflow eval cases | `docs/review/evals/WORKFLOW_EVAL_CASES.md` | Validate routing, clarification, confirmation behavior | Yes |
| Retrieval eval cases | `docs/review/evals/RETRIEVAL_EVAL_CASES.md` | Validate keyword vs semantic vs fusion behavior | Yes |
| Failure injection checklist | `docs/review/evals/FAILURE_INJECTION_CHECKLIST.md` | Validate degraded and recovery behavior | Yes |
| Index consistency policy | `docs/review/execution/INDEX_CONSISTENCY_POLICY.md` | Define sync, best-effort, and repair expectations | Yes |

#### Test-first rule

No reliability-related code change should begin before the corresponding eval case or failure case is written.

#### Ordered execution steps

1. Write `docs/review/evals/WORKFLOW_EVAL_CASES.md`
2. Write `docs/review/evals/RETRIEVAL_EVAL_CASES.md`
3. Write `docs/review/evals/FAILURE_INJECTION_CHECKLIST.md`
4. Write `docs/review/execution/INDEX_CONSISTENCY_POLICY.md`
5. Validate current system behavior against the new eval artifacts
6. Record gaps between expected vs actual behavior
7. Only then start targeted fixes/refactors

#### Verifiable acceptance criteria

- [ ] Workflow eval file contains at least 10 cases with expected agent/tool behavior
- [ ] Retrieval eval file contains at least 15 query-target cases across exact, fuzzy, and semantic retrieval
- [ ] Failure injection checklist includes weather failure, vector failure, metadata/FTS inconsistency, and manual file edit recovery
- [ ] Index consistency policy explicitly labels each index layer as synchronous-required, best-effort, or repairable
- [ ] At least one baseline evaluation pass is recorded against the current system

#### Review gate

Phase 3 cannot start until the eval corpus exists and at least one documented baseline run has been completed.

#### Allowed scope

- Eval definitions
- Baseline assessment
- Targeted reliability fixes tied to explicit cases

#### Not in scope

- Broad product redesign
- UI or protocol expansion

---

### 6.4 Phase 3 — Distribution & Product Readiness

#### Objective

Make the project easier to install, understand, and use without needing hidden project context.

#### Required artifacts

| Artifact | File path | Purpose | SSOT status |
|:---|:---|:---|:---:|
| Distribution strategy note | `docs/review/execution/DISTRIBUTION_STRATEGY.md` | Define preferred install/distribution path | Yes |
| Onboarding checklist | `docs/review/execution/ONBOARDING_CHECKLIST.md` | Define first-run path from install to first successful usage | Yes |
| Documentation boundary plan | `docs/review/execution/DOCS_BOUNDARY_PLAN.md` | Clarify roles of README, SKILL, API, ARCHITECTURE, roadmap docs | Yes |
| MCP re-evaluation note | `docs/review/execution/MCP_REEVALUATION.md` | Reassess whether MCP adapter is justified after P1/P2 | Yes |

#### Ordered execution steps

1. Write `docs/review/execution/DISTRIBUTION_STRATEGY.md`
2. Write `docs/review/execution/ONBOARDING_CHECKLIST.md`
3. Write `docs/review/execution/DOCS_BOUNDARY_PLAN.md`
4. Run one fresh-install onboarding rehearsal
5. Record friction points
6. Write `docs/review/execution/MCP_REEVALUATION.md`

#### Verifiable acceptance criteria

- [ ] A preferred distribution path is explicitly chosen and documented
- [ ] Onboarding checklist covers install, init, health check, first write, first search
- [ ] At least one fresh-install rehearsal has been documented
- [ ] Documentation boundary plan states what each top-level doc is responsible for and what it must not duplicate
- [ ] MCP re-evaluation states go / no-go / defer with explicit criteria

#### Review gate

Phase 3 is complete only after a reviewer can follow the onboarding checklist end-to-end without needing undocumented project knowledge.

---

### 6.5 Atomic Commit Strategy

Use small, reviewable commits. Each commit must map to one artifact family or one narrowly scoped implementation change.

Recommended commit sequence:

1. `docs: add workflow scenarios and boundary review checklist`
2. `docs: add tool responsibility matrix`
3. `docs: add canonical workflows spec`
4. `docs: define write failure semantics and weather-edit boundary`
5. `docs: add workflow and retrieval eval cases`
6. `docs: add failure injection checklist and index consistency policy`
7. `docs: define distribution strategy and onboarding checklist`
8. `docs: clarify documentation boundaries and MCP re-evaluation`
9. `fix: align code or API behavior with approved workflow boundary docs` (only after prior docs are approved)

Commit rules:

- Do not mix roadmap docs with unrelated code changes
- Do not mix evaluation scaffolding with implementation fixes in the same commit
- Each implementation commit must cite the artifact or eval case it satisfies

---

### 6.6 Ownership Model

For every artifact in this roadmap, define these roles during execution:

- **Owner**: the person or agent writing the artifact
- **Reviewer**: the person or agent validating clarity and completeness
- **Approval check**: the checklist or eval artifact used to approve it
- **Allowed scope**: what can be changed while producing this artifact
- **Out-of-scope**: what must not be changed in the same work item

Default ownership model if none is assigned:

- Owner: active implementer
- Reviewer: separate reviewer agent or human maintainer
- Approval check: corresponding phase checklist / eval file

---

### 6.7 Phase Transition Rules

Hard rules:

- **P2 must not begin** until all P1 execution artifacts exist and pass review
- **P3 must not begin** until the P2 eval corpus exists and at least one baseline run is documented
- **MCP re-evaluation must not become active implementation work** unless P1 and P2 are both substantially complete

Soft rules:

- Small clarifying edits are allowed across phases
- Large refactors should wait until the relevant phase artifacts and tests exist

---

## 7. 使用说明

本文档的用途不是展示观点，而是作为后续工作的**执行基线**：

- 任何新规划，优先检查是否与本文件冲突
- 任何新功能，优先判断它属于哪个 phase
- 任何重构提案，优先说明它是否有助于 workflow clarity / boundary clarity / reliability / distribution

如果未来阶段完成，可以：

- 将阶段结果归档到 `docs/archive/`
- 在 `docs/CHANGELOG.md` 中记录关键状态变化
- 视需要拆分出更细的 playbook 文档
