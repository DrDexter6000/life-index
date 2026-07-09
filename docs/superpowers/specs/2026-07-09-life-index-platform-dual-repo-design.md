# Life Index Platform 双仓与 Addon 架构设计

> 状态：Draft for Chief Advisor Review
>
> 日期：2026-07-09
>
> 范围：`life-index` 主仓、`life-index_gui` GUI 仓及未来高级 Addon
>
> 决策层：Human Owner、CTO / Product Director、Chief Advisor
>
> 执行层：CLI Lead Agent、GUI Lead Agent、未来 Addon Lead Agent

## 0. 文档地位

本文是跨仓设计提案，不是已生效的产品宪章或 API 契约。

在完成 Chief Advisor 红队评审、CTO / Product Director 裁定和 Human Owner 批准前，权威顺序保持不变：

1. CLI `CHARTER.md`；
2. 两仓各自 `AGENTS.md`；
3. CLI `docs/API.md` 与 `docs/ARCHITECTURE.md`；
4. GUI 的公开架构与接口契约；
5. 本设计提案。

若本文与现有权威文档冲突，评审阶段以现有权威文档为准，并把冲突列入后续正式变更，而不是静默覆盖。通过终审后，主控 Agent 应把被接受的决策提升到现有权威 SSOT；本文随后保留为决策背景，不成为并行维护的长期 SSOT。

## 1. Executive Decision

Life Index 的目标形态不是“一个 CLI 产品加一个 GUI 产品”，而是一个本地优先的个人记忆平台：

- CLI Core 保存事实、执行确定性操作并提供长期稳定契约；
- Host Agent 理解自然语言、规划、推理、选择工具和合成；
- Skills 承载 Life Index 及 Addon 的领域流程；
- GUI 是一等的第一方人类体验层，而不是智能所有者；
- 未来 Addon 通过同一 Core Contract 和 Host Agent 生态生长；
- Gateway 与 Host Runtime Layer 复用连接和运行时能力，但不成为新的智能或数据真相源。

关键边界：

> `life-index` 主仓可以发行 Core、Contracts、Skills、Gateway 和共享 Host Runtime 接入资产；但同仓不等于同层。高波动的 Agent / runtime 能力不得进入 CLI Core。

## 2. 设计目标与非目标

### 2.1 目标

1. 同时支持自然语言 Agent 与 GUI 两条一等人类入口。
2. 为 GUI、Host Agent 和未来 Addon 提供可随项目成长、但相对稳定的 Core Interface。
3. 避免每个 Addon 重复实现 CLI 调用、Host runtime 连接、流式、取消、错误与 provenance。
4. 保持用户数据只有一个权威写入路径，不因 Gateway、GUI 或 Addon 产生平行数据语义。
5. 允许经真实复用验证的确定性 Addon 基元回流 CLI Core。
6. 把当前 CLI / GUI 审计发现的可信性与激活问题排在平台扩张之前。

### 2.2 非目标

1. 本设计不批准立即实现 Gateway、Addon SDK 或新 Addon。
2. 本设计不选择具体 Host Agent、模型、provider 或云服务。
3. 本设计不引入 plugin loader、动态 entry-point registry 或自动执行未知 Addon。
4. 本设计不把自然语言规划、语义解释或叙事合成放入 CLI Core。
5. 本设计不要求立即拆出第三个仓库或独立发行所有 runtime adapter。
6. 本设计不把 GUI 降格为次要产品；“逻辑上是 L4 模块”不等于“产品上不重要”。

## 3. 目标架构

```mermaid
flowchart TB
    H["Human User"]

    H --> NL["Natural-language Interface<br/>Codex / Hermes / Claude / other Host Agent"]
    H --> GUI["Life Index GUI"]
    H --> AU["Future Addon Interface<br/>memoir / letters / import / other experiences"]

    NL --> HA["Host Agent<br/>intent, planning, reasoning, tool choice, synthesis"]
    GUI --> BFF["GUI BFF<br/>browser security, SSE, remote access, presentation adapter"]
    GUI --> HH["Host Agent Handoff"]
    AU --> HH
    HH --> HA

    HA --> SK["Life Index Skill + Addon Skills"]
    SK --> IF["Stable Core Interface<br/>CLI JSON / Python API / optional Gateway"]
    BFF --> IF
    AU --> IF

    IF --> CORE["CLI Core<br/>deterministic read, write, search, index, aggregate, entity, transaction"]
    CORE --> DATA["Markdown / YAML / attachments / derived indexes"]

    SK --> ADDON["Addon-owned workflow state,<br/>domain knowledge and deterministic helpers"]
    ADDON --> IF
```

### 3.1 两条一等人类入口

**自然语言路径**：Human → Host Agent UI → Host Agent → Skill → Core Interface → CLI Core。

**GUI 路径**分两种：

- 确定性动作：Human → GUI → BFF → Core Interface → CLI Core；
- 智能动作：Human → GUI → Handoff → Host Agent → Skill → Core Interface → CLI Core，结果再由 GUI 呈现。

两条路径使用同一数据真相源、同一确定性工具和同一领域 Skill。不得出现“Agent 版传记”和“GUI 版传记”两套智能实现。

## 4. 层与所有权

| 层 / 组件 | 拥有 | 不拥有 | 主要位置 |
|---|---|---|---|
| L1 Data | journal、YAML、附件、机器派生索引 | 解释、叙事、UI 状态 | 用户数据目录，由 CLI 约束 |
| L2 CLI Core | 确定性读写、检索、聚合、entity、事务、schema 语义 | LLM、Host runtime、自然语言规划、GUI | `life-index` 主仓 Core |
| Core Contract | JSON shape、字段语义、错误码、SLO、副作用与版本 | 独立业务逻辑 | `life-index` 主仓 |
| Tool Gateway | Core Contract 的 1:1 transport projection | 新能力、新写入路径、语义修复、智能 | 主仓可选 adapter，不属于 Core |
| Host Runtime Layer | runtime 连接、启动、健康、流式、取消、超时、严格 envelope | 模型选择、意图分类、工具规划、答案合成 | 可由主仓发行；runtime adapter 可独立版本化 |
| Skills | 领域流程、检索策略、证据使用规则、Addon procedure | 数据真相源、隐式 provider | 主仓通用 Skill + Addon Skill |
| Host Agent | 意图、规划、推理、多工具调用、语言合成 | 绕过 Core 写 L1 | 用户选择的 runtime |
| GUI | 写入/搜索/证据/时间线等人类体验，浏览器安全与 presentation | 数据语义、LLM brain、runtime 宽松修复 | `life-index_gui` |
| Addon | 领域知识、工作流状态、专用 helper、可选 renderer | 平行 L1、Core 内部实现假设 | 独立包、目录或仓库 |

## 5. `life-index` 主仓与 CLI Core 的区别

`life-index` 应被视为 Life Index Platform 的主仓；CLI Core 是其中寿命最长、依赖最少的内核。此为产品和架构心智模型，不要求立即修改仓库名称。

主仓长期可以拥有：

- CLI Core；
- API schema 与 capability registry；
- Python client / Addon SDK 的确定性部分；
- `SKILL.md` 与通用领域 Skills；
- Tool Gateway；
- 严格 Host Runtime 接入协议与 conformance；
- evidence、claim、provenance、run-context 等跨 Addon 类型。

依赖方向必须保持：

```text
Core <- Core Contract <- Gateway / SDK <- GUI / Addon / Host Agent

Core must not depend on Gateway.
Core must not depend on Host Runtime.
Core must not depend on GUI or Addon.
```

物理同仓不能成为反向依赖或把 Agent 逻辑放进 Core 的理由。

## 6. Stable Core Interface

### 6.1 稳定承诺

Addon、GUI 和 Host Agent 可以依赖：

1. JSON 顶层 shape 与类型；
2. 字段的精确语义和枚举；
3. 错误码、诚实降级和 `recovery_strategy`；
4. 关键 SLO；
5. side-effect 分类：read-only、proposal、write、maintenance；
6. 写入原子性和幂等语义；
7. capability/schema version 与兼容策略。

消费者不得依赖 SQLite 表、索引文件布局、分词配置、内部 Python 私有函数或历史兼容分支。

### 6.2 Capability Registry

未来 capability registry 应成为机器可读的能力目录，每个能力至少声明：

- canonical name；
- input/output schema version；
- side-effect class；
- required confirmation / lock / audit 行为；
- minimum CLI version；
- availability / feature negotiation；
- recovery semantics；
- direct CLI invocation mapping。

Registry 必须从 CLI 权威定义产生，不能成为第二个手工维护的 API SSOT。

### 6.3 Gateway

Gateway 只允许是 Core Contract 的精确投影：

- 返回 CLI 原始 JSON 语义；
- 所有写入经过同一 validation、lock、transaction 和 audit；
- 不直接读写用户数据；
- 不拥有 schema；
- 不做 query rewrite、tool choice、semantic coercion 或 synthesis；
- 不成为 CLI 的强制常驻依赖。

初始技术顺序是 capability registry → transport-neutral dispatcher → stdio/JSON-RPC pilot。HTTP 或 MCP 只有在第二个真实消费者、连接复用、流式或宿主约束证明需要时才进入实现评估。

## 7. Shared Host Runtime Layer

### 7.1 应复用的轮子

共享层可以统一：

- runtime 的显式配置与健康检查；
- 启动、停止、timeout、cancel；
- status/delta/final/error 流式事件；
- strict envelope validation；
- request/run/conversation correlation；
- 诊断、可观测性和敏感内容脱敏；
- conformance kit 与兼容支持矩阵。

### 7.2 禁止成为“Life Index 大脑”

共享层不得：

- 判断用户要运行哪个 Addon；
- 选择模型或 provider；
- 改写 query；
- 决定工具调用序列；
- 修复或重写 Agent 的语义结论；
- 生成传记、家书、诊断或人格表达；
- 为了兼容任意 stdout 而无限添加通用 heuristic。

Domain Skill 提供 procedure；Host Agent 执行 reasoning；Host Runtime Layer 只承担连接与传输。

### 7.3 当前 bridge 的处置

当前 GUI reference bridge 在 P2 前保持可用，但立即冻结新的通用宽松 heuristic。后续按真实变更拆成：

1. strict reference adapter；
2. 具名 runtime adapter；
3. GUI-owned handoff relay 与 renderer。

不把现有 bridge 整体搬入 CLI Core，也不为减少进程数而合入 GUI backend。

## 8. Addon 模型

### 8.1 标准组成

一个高级 Addon 可以包含：

```text
addon/
├── SKILL.md             # 领域 procedure
├── references/          # 领域知识
├── helpers/             # 确定性 helper
├── schemas/             # Addon 产物与过程状态
├── renderer/            # 可选 GUI 呈现
└── state/               # 可重建的 module-local checkpoint/cursor
```

Addon 不要求同时拥有全部部分。简单体验可以只有 Skill；导入器可以主要由 deterministic adapter 构成；富体验可以增加 renderer 与 checkpoint。

### 8.2 基元升格规则

Addon 能力进入 Core 必须满足全部条件：

1. **确定性**：相同输入和明确环境产生可验证结果；
2. **低 LLM 含量**：不依赖自然语言判断才能成立；
3. **跨模块复用**：至少两个真实生产消费者，或 Human Owner 明确判定有长期基础价值；
4. **长期语义稳定**：面向 10–50 年数据仍有相同含义；
5. **Core-owned truth**：能力与数据完整性、检索、事务、provenance 或通用测算密切相关；
6. **RFC 成本已支付**：schema、迁移、SLO、错误和回归证据完整。

不满足任一条件的能力留在 Addon。Whole-feature promotion 不是默认路径；通常只有确定性基元回流 Core。

### 8.3 示例裁定

| Addon | Core 候选 | 留在 Addon / Skill |
|---|---|---|
| 数字传记 | timeline、evidence pack、batch/cursor、素材分桶 | 章节立意、人生解释、叙事文风 |
| 数字家书 | 人物关系、时间范围、引用与素材包 | 情感表达、语气与价值判断 |
| 心理分析 | typed observation、量表计算、来源引用 | 诊断、心理解释和建议 |
| 模拟人格 | 语料检索、引用、风格统计 | 人格模拟、角色表达、身份声明 |
| 相册/社媒导入 | canonical import transaction、hash/dedup、时间归一化、provenance | 平台登录、抓取、API 方言和格式 adapter |

## 9. 数据、错误与安全边界

1. 所有 durable 用户数据写入必须由 CLI Core 执行。
2. GUI、Gateway、Host Runtime 和 Addon 不直接写 journal/frontmatter/索引文件。
3. Addon checkpoint/cursor 属于 module-local、可清除、可重建过程状态，不得成为第二真相源。
4. Host Agent 不可用时，确定性写入、搜索和浏览继续可用；智能入口诚实显示 unavailable。
5. Runtime adapter 不得静默选择 provider 或外发用户数据。
6. 需要云模型时，由用户选择的 Host Agent 负责 provider、凭据、授权和数据暴露说明。
7. Agent 输出评价是 advisory metadata，不作为阻断或改写闸门。
8. 所有跨边界请求携带 version、request/run id 和可诊断错误；未知 additive 字段应前向兼容。

## 10. 方案比较

| Option | 优化目标 | 代价 | 裁定 |
|---|---|---|---|
| Conservative path：每个 Addon 自带 Agent/bridge | 局部自治、最少平台设计 | runtime、错误、流式、schema 重复；协议漂移 | 拒绝作为长期模型 |
| Core orchestrator：统一自然语言大脑进入 CLI Core | Addon 表面最简单 | Core 绑定模型、隐私、runtime 和高波动语义；破坏寿命分层 | 拒绝 |
| Clean target：立即拆分 Core/Gateway/Runtime/Addon 多发行物 | 边界最整洁 | 当前激活和版本协调成本过高 | 终局参考，不一次性执行 |
| **Staged clean path：同仓不同层，先修 Core/激活/契约，再由真实消费者触发 Gateway 与 Runtime 抽取** | 长期边界与当前节奏 | 需要阶段纪律，短期保留过渡结构 | **推荐** |

## 11. Red-Team / Blue-Team

### 11.1 共享 Runtime Layer 偷偷变成智能层

- **Red**：未来开发者为方便在 runtime 层加入 intent router、prompt policy 和 tool planner。
- **Blue**：接口只允许调用方提供 task/context/tools；增加依赖边界测试，禁止 Core 和 transport 层导入 provider/LLM client；语义策略只能存在于 Skill/Host Agent。
- **Residual**：runtime-specific adapter 仍可能需要方言处理，因此必须具名和独立支持，而不是伪装成通用协议。

### 11.2 Gateway 成为第二 API

- **Red**：HTTP/MCP 逐步新增 CLI 没有的字段、错误和写入快捷路径。
- **Blue**：registry 由 CLI 权威定义生成；建立 direct CLI vs Gateway contract-equivalence tests；Gateway 不拥有 schema 文件。
- **Residual**：transport-specific framing 与连接错误仍存在，但不能改变领域语义。

### 11.3 Core 为未来 Addon 过度膨胀

- **Red**：以“将来多个模块也许需要”为由提前加入 workflow primitives。
- **Blue**：执行六项升格规则；缺少第二消费者或 Owner 明确判定时，默认留在 Addon。
- **Residual**：可能短期出现两份相似 helper；这比长期污染 Core 更容易回收。

### 11.4 拆分增加用户安装负担

- **Red**：Gateway、runtime adapter、GUI、Addon 形成多进程和多版本拓扑。
- **Blue**：默认核心路径保持 CLI + Skill；AI+ 和 Gateway 都是可选；激活 Skill 隐藏拓扑并运行版本协商/conformance。
- **Residual**：高级体验仍有本地运行时复杂度，必须用真实冷启动数据决定是否进一步打包。

## 12. 双仓统一优先级

### P0 — Core Truth and Safety

在任何 Gateway、bridge 搬迁或新 Addon 前完成：

1. 修复 recall-first 违约：默认搜索不得因预设 OOD/noise 主题或 ranking threshold 删除真实 token match。
2. 建立可公开复现的 synthetic/sandbox retrieval baseline；私有真实数据 eval 继续作为 advisory evidence。
3. 修复写入事务：journal、附件、topic/project/tag index 与关键派生状态必须有明确 commit/rollback 语义。
4. 删除或隔离生产 smart-search 模块中的 shadow LLM orchestrator、prompt parser、trust gate 和 legacy synthesis，仅保留必要的确定性 scaffold。

P0 的验收标准是行为正确、契约诚实、回归可复现，不是只让 CI 变绿。

### P1 — Product Activation and Contract Truth

1. 新机器在 Host Agent 协助下，10 分钟内安装、验证、打开 GUI、写入第一条日志并搜索到它。
2. AI+ unavailable 不阻塞确定性核心循环。
3. 修正 GUI attachment contract 与真实 CLI feature negotiation 漂移。
4. 清理过期 SSOT、无退出条件的兼容分支和未实现未来 UI 卡片。
5. release gate 增加真实 CLI + backend + browser smoke，覆盖最高风险跨进程链路。
6. 建立 capability registry 的权威生成设计，收束散落能力表。

### P2 — Platform Interface

1. 定义 Addon Contract 与 deterministic Addon SDK 最小面。
2. 定义 Shared Host Runtime Layer 的 strict contract。
3. 冻结并分型当前 reference bridge；不再把 runtime 方言修复称为通用 adapter。
4. 以 `health`、`read`、`search` 做 stdio/JSON-RPC Gateway pilot。
5. 验证 direct CLI 与 Gateway 的输出、错误、权限和 side-effect 语义等价。
6. frontend 仅在真实 feature change 触及时按 vertical slice 深化，不为拆文件而拆文件。

### P3 — First Architecture-Proving Addon

首个建议候选是只读、带逐条引用、可暂停恢复的“个人传记单章节”MVP。它用于验证长程检索、evidence、batch/cursor、Addon Skill、Host Agent 调度、GUI 富呈现和双入口一致性。

心理诊断和模拟人格不作为第一个平台验证 Addon：二者的高风险解释、身份、安全和产品责任会掩盖基础架构问题。

## 13. Verification Gates

任何阶段的“完成”必须由与风险相称的证据支持：

1. **Core boundary**：L2 不导入或初始化 LLM/provider/runtime client。
2. **Data boundary**：GUI、Gateway、Addon 不直接写 L1。
3. **Contract equivalence**：同一输入经 direct CLI 和 Gateway 具有等价领域结果与错误语义。
4. **Transaction**：故障注入证明失败后不存在孤儿附件、半更新索引或虚假 success。
5. **Recall**：真实 token match 不被默认 gate/threshold 删除。
6. **Activation**：至少三个独立冷启动样本完成 10 分钟首条日志闭环，并记录失败原因。
7. **Host-agent outcome**：Agent-facing 变更按当前 `SKILL.md` 在 owner-authorized 数据上完成真实任务，而非只跑单元测试。
8. **Addon proof**：同一个 Addon Skill 可从自然语言入口和 GUI 入口产生同源 evidence 与兼容产物。

## 14. 决策与执行 Operating Model

### 14.1 角色

| 角色 | 职责 | 不负责 |
|---|---|---|
| Human Owner | 最终产品意图、风险接受、重大方向批准 | 日常代码细节 |
| CTO / Product Director | 目标模型、产品优先级、架构边界、跨仓裁定、执行验收标准 | 日常实现和主控 Agent 的具体编码 |
| Chief Advisor | 平级战略伙伴；获取完整上下文，独立判断，提出创意、红队挑战和参考审计意见 | 迎合既有方案、代替主控 Agent 写实现方案或代码 |
| CLI Lead Agent | CLI 任务分解、TDD/实现、验证、提交与证据报告 | 自行改变高维产品/架构方向 |
| GUI Lead Agent | GUI 任务分解、实现、浏览器验收、契约协同与证据报告 | 自行改变高维产品/架构方向 |
| Addon Lead Agent | 被批准 Addon 的具体设计与实现 | 修改 Core 边界或绕过升格流程 |

### 14.2 决策流程

1. CTO / Product Director 形成高维提案与验收边界。
2. Chief Advisor 获取必要上下文并进行独立 red-team；不默认同意 Owner 或 CTO。
3. CTO / Product Director 对建议逐项 adjudicate：接受、修改或有理由拒绝。
4. Human Owner 批准方向和优先级。
5. CTO / Product Director 为对应主控 Agent 提供复制用执行 prompt；长程任务附经批准的 spec、goal 或 TDD 要求。
6. 主控 Agent负责具体方案、代码、测试、提交和证据，不扩大授权范围。
7. CTO / Product Director 与 Chief Advisor 根据证据复核产品结果和边界；Human Owner决定是否进入下一阶段。

未经第 4 步批准，不进入实施计划和代码阶段。

## 15. Deferred Decisions With Explicit Triggers

以下事项不是遗漏项，而是带有明确触发条件的有意延后决策：

1. **Gateway transport**：第二个真实消费者或已证明的连接/流式需求出现后，才在 stdio、MCP、HTTP 中选择。
2. **Runtime package/repo 位置**：strict adapter 与首个 runtime-specific adapter 边界通过 conformance 后，再决定同仓 package 还是独立发行。
3. **通用 `life_index.agent_handoff.v2`**：第二个非 GUI 消费者需要相同 handoff 语义后才设计；当前 `gui.host_agent.*` v1 不原地泛化。
4. **首个 Addon 立项**：P0、P1 达标且 Core Contract 足够支持只读长程任务后，再批准 Memoir MVP。
5. **桌面安装器**：三个冷启动样本表明 Skill + deterministic preflight 无法满足激活目标后再评估。

## 16. Falsifiers

以下证据会要求调整本设计：

1. 产品被明确限定为单一 owner、单一 GUI、无第三方或未来 Addon，此时 Gateway/Addon SDK 的投资应缩减。
2. 两个真实 Addon 无法共享任何 Host Runtime envelope，说明统一 runtime 层应退化为更小的协议和独立 adapters。
3. direct CLI 已足够满足所有消费者，且 Gateway 没有显著降低集成成本，则 registry/SDK 可以保留而 Gateway 不实现。
4. 某项“语义能力”被证明可完全确定、跨模块复用且长期稳定，则可按升格流程进入 Core，而不是因名称含“语义”永久排除。
5. 产品转向多用户云 SaaS，身份、授权、租户隔离和远程数据边界将要求重新设计 Gateway 与 runtime 模型。

## 17. Payoff Ledger

| Move | 现在支付的代价 | 消除的具体痛点或解锁能力 | 收益出现时点 |
|---|---|---|---|
| 区分 Platform Repo 与 CLI Core | 更新心智模型与治理文档 | 主仓可发行 Skills/Gateway/SDK，而 Core 不被高波动 runtime 污染 | 首次加入非 Core 共享组件时 |
| 建立稳定 Core Contract/registry | 契约盘点与生成机制 | GUI、Agent、Addon 不再各自维护命令和版本能力表 | 第二个消费者接入时 |
| 共享 strict Host Runtime Layer | adapter/conformance 设计成本 | Addon 不再重复实现启动、流式、取消、错误和诊断 | 第二个 Addon 或 runtime 接入时 |
| 先修 recall 与事务 | 延后平台新功能 | 防止错误检索与半提交写入被所有未来接口放大 | Gateway/Addon 之前立即体现 |
| GUI 聚焦体验而非 runtime 方言 | 放弃万能兼容器幻想 | GUI 版本不再因新增 Agent stdout 方言联动修改 | 支持第二种 runtime 时 |
| 用 Memoir 单章节验证架构 | 延后高风险心理/人格功能 | 一次验证长程检索、Skill、checkpoint、双入口和富呈现 | P3 端到端验收时 |

## 18. Chief Advisor Review Questions

Chief Advisor 应重点挑战：

1. Platform Repo 与 CLI Core 的划分是否仍有隐藏反向依赖？
2. Shared Host Runtime Layer 是否只是给当前 bridge 换了更好听的名字？
3. 哪些所谓“稳定接口”其实仍暴露当前实现细节？
4. P0/P1 是否遗漏了比 Gateway 更致命的可信性或激活问题？
5. Addon 升格门槛是过严、过松，还是可被主观绕过？
6. Memoir 是否真是最佳架构验证 Addon，还是被既有愿景绑架？
7. 哪些反对意见如果成立，应直接推翻而不是局部修补本设计？

Advisor 的目标不是润色，而是寻找错误模型、遗漏约束、不可执行边界和被低估的成本。
