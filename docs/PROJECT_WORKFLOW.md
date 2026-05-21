# Project Workflow

> **版本**: v1.1
> **创建**: 2026-05-21
> **更新**: 2026-05-21
> **状态**: 活跃
> **权威**: 本文档是 Life Index 项目级工作流的唯一权威。与 `CHARTER.md` §5、`AGENTS.md` §工作派发纪律、`docs/RFC_WORKFLOW.md` 共同构成完整治理框架。

## 适用边界

本工作流适用于**可前期规划的工程交付类项目**——目标可被相对清晰地表达、范围可被相对完整地枚举、"做对了"可被相对客观地验收。

以下 3 类工作**不天然适用本工作流**，需选择其他工作模型：

| 工作类型 | 不适用原因 | 替代建议 |
|---|---|---|
| **Greenfield 探索 / 研究** | M1 无法穷举边界，需通过迭代发现需求 | 探索阶段先跑 ResearchSpike（典型如 `.strategy/cli/` 下的研究笔记），结论收敛后再进 M1 |
| **生产 firefighting / 紧急响应** | 没有 M1 时间窗口，要求亚小时决策 | 走 Incident Response，事后用 4-Milestone 复盘 |
| **创意类（产品定义、文案）** | "做对了"无客观证伪标准 | 用迭代评审模型，ack 改为多轮主观批准 |

强行套用会触发大量假 escalate，把工作推入"为流程而流程"的负反馈。

## 流程图

```
┌──── M1 任务需求（唯一决策窗口）───────────────────┐
│  PRD 起草 → CTO review → 主理人 ack #1            │
│  必含：rationale / 目标&非目标 / 影响清单 /      │
│        Phase 拆分 × 派发纪律 4 门 / worktree 拓扑/│
│        完成定义 / 反对意见门                      │
└───────────────────────────────────────────────────┘
                       ↓
┌──── M2 任务编排（翻译层，无新决策）───────────────┐
│  推依赖图 + Worker-Task Matching + 生成 Phase    │
│  brief（verbatim 退出门）+ 检出 worktree          │
│  主理人不介入                                    │
└───────────────────────────────────────────────────┘
                       ↓
┌──── M3 任务执行（rework loop 主路径）────────────┐
│  并行线 1：主控 Agent 验收 checklist + Rework    │
│            版本管理 + anti-noise + livelock 自检 │
│  并行线 2：subagents 在 worktree 工作 + PR 验收  │
│  主理人不介入                                    │
└───────────────────────────────────────────────────┘
                       ↓
┌──── M4 质量关卡与终审（集成验证）────────────────┐
│  跨 Phase 接口 + 集成测试 + 镜像验收 (a)(b)(c)  │
│  + 认知 offload 报告 + ack #2                    │
└───────────────────────────────────────────────────┘
                       ↓
                  M5 结束
```

## 适用范围

| 类型 | 示例 | 形态 |
|---|---|---|
| 完整项目 | Life Index v2.x 新增模组组合 | 完整 4 Milestone |
| 单模块 | gbrain 借鉴模块 | 完整 4 Milestone |
| 单功能 | 给现有模块加新参数 | 中等压缩（省 M2 显式拆分）|
| Debug | 修单 bug | 极简压缩（M1+M2 合并、M3+M4 合并、单 ack 覆盖）|

## M1 任务需求（唯一决策窗口）

**产物**：`docs/projects/<project-slug>/PRD.md`（或对应 RFC 文件，小型任务）。

**PRD 必含内容**：

1. **rationale**：为什么做、解决什么问题
2. **目标 & 非目标**：明文写"做什么 / 不做什么 / 禁止做"
   - **"禁止做"清单不得为空**——影响为 0 时也要明文写"无新增禁止项"
3. **影响清单**：
   - 改哪些文档、哪些 invariants（CHARTER §1.1–§1.10）受影响
   - 是否破坏既有 RFC
   - 是否触碰 L2 / schema（CHARTER §1.5 / §1.8）
   - **影响为 0 也要明文写"无影响"**——不得省略此栏
4. **Phase 拆分**（每个 Phase 必须现场过派发纪律 **4 门**）：
   - **可证伪退出**：本 Phase PASS/FAIL 是什么命令/测试？
   - **真实消费者**：本 Phase 交付物谁会消费？
   - **执行边界**：本 subagent worktree 边界（哪些目录可写、哪些不能动）
   - **任务能力需求**（v1.1 新增）：本 Phase 任务的客观能力需求分类。按以下维度做明文专业判断：
     - **规模**：小（< 1 天）/ 中（1-3 天）/ 大（> 3 天）
     - **是否触碰 L2**（CHARTER §1.5）：是 / 否
     - **是否需要 CHARTER 改动**：是 / 否
     - **是否涉及 schema 迁移**（CHARTER §1.8）：是 / 否
     - **是否需要 Gold Set / 新 invariant**：是 / 否
     - **是否动 layer_invariants / search_constants**：是 / 否
     供 M2 派发时做 worker-task matching 使用
5. **依赖图**：Phase 间串/并行关系
6. **worktree 拓扑**：哪些 Phase 各自独立 worktree
7. **完成定义**（可证伪）：整个项目结束的 boolean 标准
8. **反对意见 ≥ 2 条 + 各自回应**（v1.1 新增）：
   - 自己当 devil's advocate，或问其他 Agent，写出本提案最强的 2 条反对论点
   - 每条明文回应：接受 / 部分接受 / 反驳依据
   - 0 条反对意见 = PRD 质量信号缺失，**不予 ack #1**
   - 此项与 CHARTER §5 substantive gate "回应反对意见"联动，是显式化版本
9. **ack #1**：主理人书面 ack（对"应该做"负责）

**CTO checklist**：

- substantive gate 4 项齐备（CHARTER §5）
- 派发纪律 **4 门** × 每个 Phase 齐备（AGENTS.md）
- invariant 影响清单 ≠ 空（影响为 0 也要明文写"无影响"）
- 明文"禁止做"清单 ≠ 空
- 反对意见 ≥ 2 条 + 回应齐备

不过 → 退回 M1 重提案。

## M2 任务编排（翻译层，无新决策）

**产物**：`docs/projects/<project-slug>/Phase-Sequence.md` + 各 Phase TDD brief。

**主控 Agent 动作**：

- 按 PRD 依赖图推演 Phase 顺序（并行/串行）
- **Worker-Task Matching**（v1.1 新增）：基于 PRD §4 各 Phase 的"任务能力需求" + 当下可用 worker 池，由主编排 Agent 做派发决策
  - 派发逻辑入此；**具体 worker matrix（哪类 worker 擅长哪类任务）见 `AGENTS.md` 或 `.agent-governance/`**——worker 池随时间和模型升级变化，PROJECT_WORKFLOW 不锁死 worker 名
  - 派发决策必须有客观依据：PRD 任务能力需求 ↔ worker 已知特长的匹配，不能基于"哪个 worker 闲着"
  - 因 worker mismatch 导致的初版失败 = **第三类失败**：不是 M1 PRD 错、不是 worker 不努力，是 M2 派发选错人。立即 fallback 重派，**不算 escalate**
- 按 PRD 各 Phase 拆解生成 subagent brief。brief 必须包含：
  - task 清单
  - **Phase 退出门**：**逐字（verbatim）引用** PRD §4 对应 Phase 的"可证伪退出"——M2 不得改写、不得"重新表达"，改写即违反 M2 红线
  - 红绿测试
  - 验收标准
  - 自检 checkbox
  - 下一 task 指针
  - 执行总结 placeholder
- 按 PRD worktree 拓扑机械执行 `git worktree add`

**M2 不引入新决策**。如果发现 PRD 没说"这块归谁"，是 M1 失败信号 → escalate 回 M1（见下"异常 escalate vs Rework Loop"）。

主理人不介入。

## M3 任务执行（rework loop 主路径）

> **核心认知**（v1.1 新增）：M3 是 *"Subagent ↔ 主审"* **循环**而非单程。**rework 是 M3 主路径，不是异常路径**。gbrain absorption 实证：6 个 Phase 中 5 个需要 rework。多 Phase 并行项目中 rework 5/6 是物理常态。把 rework 当异常会把流程压坏。

### 并行线 1（主控 Agent / 主审）

#### 验收循环

- 定时轮询各 subagent 进度
- 按下方 **主审验收 checklist** 验收交付物
- 通过 → 勾 Phase Sequence 中的 checkbox
- 不通过 → reject PR + 明文 reject reason → subagent 进入 **rework v0X**

#### 主审验收 checklist（每个 PR 必跑）

每个 PR 验收前必须独立验证 4 项，缺一不予 accept：

- **(a) 退出门证据**：PRD §4 "可证伪退出" 命令实际跑过、有 stdout/stderr/exit-code 证据；**不接受 commit message 自述 "PASS"**
- **(b) 边界 enforcement**：
  - git diff 范围是否在 PRD §2 "禁止做" 之外
  - 是否绕开了 PRD §4 要求的 L2 契约 / 接口层
  - 是否动了**项目元数据**：典型清单 `layer_invariants.yaml`、`search_constants.py`、`schema/*.yaml`、`.gitignore`、`pyproject.toml`、`CHARTER.md`、`AGENTS.md`、`docs/PROJECT_WORKFLOW.md`、`docs/RFC_WORKFLOW.md`（governance 文档改动必须先走 RFC_WORKFLOW）
  - **新增模块的 L3 边界类不变量测试统一加在 `tests/contract/test_layer_invariants.py`，不要散到模块 contract 文件**（维持单一边界规则索引；gbrain absorption final closure 实证）
- **(c) 消费者真实可消费**：PRD §4 "真实消费者" 端到端可用，不是"自动化测试通过就算"
- **(d) Push 前置门**：本地 `pytest -m blocker`（或等价 hard-required check）必须**实际跑过且全绿**才允许 push origin。**CI 后补救是 anti-pattern**——CI red 期间历史已被污染，不该靠"再 push 一个"洗白（gbrain absorption final closure push-after-CI 实证）

#### Rework 版本管理（v1.1 新增）

- Rework 必须**显式编号**：`rework v01`、`rework v02`、...
- branch naming 建议：`rework/<phase-slug>/v0X`（如 `rework/phase-f/v02`）
- 每次 reject 必须留下 **reject reason 记录**（commit message 或 PR 描述都行）
- 主审 cherry-pick / merge 前必须**显式确认** *"该 commit 来自最新 accepted 版本"*（多 rework 版本并存时的硬要求；gbrain absorption Phase D 实证过误 cherry-pick）
- 项目可统计 rework 次数作为 PRD 质量度量（**长期目标 rework→0**，类比 escalate→0）

#### 主审操作纪律 anti-noise（v1.1 新增）

主审 = 主控 Agent 也会犯操作错。并行 N 个 Phase × 每 Phase N 个 rework 版本 = 操作复杂度爆炸：

- **Dispatch 前**：确认目标 worker 未在执行该任务（避免重复 loop；gbrain absorption 实证过）
- **Cherry-pick / merge 前**：`git log` 确认 commit 来自最新 accepted 版本（避免误用 rework v01 而非 v02）
- **发现误操作**：立即 `git revert` + 留下 audit note（commit message 含 "operator error" 标签），**不静默修复**

#### 主控 Agent 循环纪律 livelock prevention（v1.1 新增）

编排工具普遍提供**再次触发机制**（auto-resume / cron / webhook 重投 / 定时唤醒等）。主控 Agent 在每次被触发执行任务前，必须做 **livelock 自检**：

- 区分两种情况：
  - **任务 ready 但执行失败** → 可重试（单次 retry 可能解决）
  - **任务 blocked on 未完成依赖** → 必须等待，**不可重试**（重试不会解决依赖）
- 自检方法：检查当前任务的依赖（前置 Phase accept 状态 / 前置 PR merge 状态 / `Phase-Sequence.md` 中 checkbox 状态）较上一轮**是否有变化**：
  - 依赖**有变化** → 正常执行任务
  - 依赖**无变化** → 立即返回 *"still blocked，state unchanged"*，**不进入任务体**，不写 audit trail
- 长期空转 ≥ 3 次 → 显式 escalate 给主理人，附 *"X 长期 blocked on Y，请决策是否调整路径"*

### 并行线 2（各 subagents）

- 在自己 worktree 内写代码、跑测试
- 按 Phase TDD brief 工作
- 完成 → PR 提交，等待主审验收
- 单 PR 自包含
- 被 reject → 进入 **rework v0X**，针对 reject reason 修复后重新 PR
- subagent 不评价主理人状态、不发起 RFC（必要时通过主控 Agent 提请 escalate）

**约束**：

- 推送政策（`AGENTS.md` §推送政策）
- 审计-代码耦合（`AGENTS.md` §审计-代码耦合：审计文档与代码 diff 同 commit）
- 不动 PRD 未授权的范围

主理人不介入。

## M4 质量关卡与终审（集成验证）

**主控 Agent 动作（机械验收）**：

- 跨 Phase 接口对齐验证
- 合并冲突最终解决
- 整体集成测试（contract + integration 套）
- **逐 Phase 镜像验收**（v1.1 新增；对应 PRD §4 三问）：
  - (a) **可证伪退出**：独立运行该 Phase 的退出命令，确认实际 PASS（不是看 commit message 写了 PASS 就信）
  - (b) **真实消费者**：端到端验证消费者能消费交付物（不是 "PR 通过 CI" 就算）
  - (c) **执行边界**：审查 git diff，确认无越界改动

**主控 Agent 动作（认知 offload）**（v1.1 新增）：

为了让主理人在合理时间内完成 ack #2，主控 Agent 必须在请求 ack 时同步产出 **M4 验收报告**（路径建议：`.agent-reports/<project-slug>/M4_INTEGRATION_<date>.md`），至少含：

1. **验收摘要**：一段话说清"做了什么 / 偏离 PRD 哪些 / 是否建议 ack"
2. **关键证据**：每个 Phase 退出门的实际运行证据（命令 + 输出节选 + commit 链接）
3. **已知 caveats**：知道但选择不修的事项 + 理由 + 影响评估
4. **主理人决策点列表**：本次 ack 中需要主理人**专门判断**的几个点（其余默认照报告通过）

不出报告就请求 ack #2 = 把主理人拖回 M3 当工头，违反 "主理人 M2/M3 不介入"。

**ack #2**：主理人对"做对了"负责。书面 ack。

- 不过 → 回 M3 修复
- 严重偏离 PRD（不是补充而是方向错） → escalate 回 M1

## M5 结束

- CHANGELOG `[Unreleased]` 更新（如属 user-facing 改动）
- PRD/RFC status：`accepted` → `implemented`
- 如 CHARTER 改动 → `docs/charter-history/` 归档
- 派发纪律 closeout 检查：出了 code commit 但 CHANGELOG `[Unreleased]` 仍空 → 流程失败信号

## 异常 escalate vs Rework Loop（v1.1 重要区分）

两者**不是同一回事**，但容易混淆：

| 维度 | Rework Loop | Escalate |
|---|---|---|
| 频率 | M3 **主路径**（gbrain 实证 5/6） | M3 **异常**（PRD 失败信号）|
| 触发 | PR 不达 checklist 标准 | PRD 没说或边界已破 |
| 处理 | reject + reject reason → subagent 改后再 PR | 流程回到 M1，主理人重启决策 |
| 责任 | subagent 实现质量 | 主理人 PRD 质量 |
| 长期目标 | rework→0（同义于 PR 一次过）| escalate→0（同义于 PRD 一次过）|

### Escalate 触发清单

M2/M3/M4 中若发生以下情况，**escalate 回 M1**：

| 情况 | 落点 | 根因 |
|---|---|---|
| 发现需触碰 L2 / schema 但 PRD 没说 | M1 重做影响清单 | PRD 漏写 invariant 触碰 |
| 发现需扩 scope 才能交付 | M1 重做目标 & 非目标 | PRD 边界过窄 |
| Subagent 无法在 worktree 边界内完成 | M1 重做 worktree 拓扑 | PRD 派发纪律不完整 |
| M4 验收发现 PRD 方向就错（不是补充而是路线错） | M1 重启决策 | PRD 根本错 |

**核心原则**：

- M3 不该有 "circuit-breaker"。出现 escalate 不是 M3 流程的常态，是 M1 PRD 质量信号
- 每次 escalate 留下 lessons learned，反哺下一份 PRD
- **escalate 频率 = PRD 质量度量**。长期目标 escalate → 0
- 不要因为出现 escalate 就退回 "M3 装 circuit-breaker" 的旧范式 —— 那是治标不治本

## 压缩形态（合法的简化）

不是所有任务都跑全 4 Milestone：

| 改动规模 | 形态 |
|---|---|
| 极简（< 10 min，单文件，不动 invariant） | M1+M2 合并、M3+M4 合并、单 ack 覆盖 |
| 中等（单 Phase 内可完成） | M1 PRD + 直接进 M3，省略显式 M2 拆分 |
| 大型（多 Phase 并行） | 完整 4 Milestone |

参考 `RFC-2026-05-20-governance-scope-correction` 的压缩形态：从 ack 到 push < 10 min。

## Two-ack 模型

| 位置 | ack | 主理人负责什么 |
|---|---|---|
| M1 通过 | ack #1 | 对"应该做"负责（plan accountability）|
| M4 通过 | ack #2 | 对"做对了"负责（delivery accountability）|

- M2/M3 中**没有 ack** —— 主理人不被打扰
- 唯一例外：M3 触发 escalate → 回到 M1 → 重启 ack #1

**角色合并模式**（v1.1 新增）：Life Index 默认就是 *"主理人 = 主控 Agent 提示词来源 + 部分时间直接担任主控 Agent"* 的一人 + N Subagent 协作模式。ack #1 / ack #2 仍需**书面留痕**（写入 PRD 末尾 / M4 报告末尾），但无须等待异步审批。留痕是为了未来回溯与自我审计，不是仪式。

## 全程边界（CTO 评价范围）

继承 `AGENTS.md` §工作派发纪律 §边界：

> CTO agent 评价 *工作内容*（决策内容、代码改动、模块边界），不评价 *主理人状态*（情绪、节奏、表达方式、消息频率）。CTO agent 不基于主理人状态做 governance 决定。

跨 4 Milestone 全程适用。

## PRD vs RFC 关系

| 文档 | 角色 |
|---|---|
| **PRD** | 项目/模块级"做什么 + 为什么"（覆盖完整 M1-M4 周期）|
| **RFC** | 治理决策级"如何决定 + 边界"（可独立、可嵌套）|

三种合法配对：

- **小型任务**：单个 RFC = PRD（合二为一），M1 输出一份
- **大型任务**：PRD = M1 主交付；M2/M3 中遇到 substantive 决策时**派生子 RFC**（每个子 RFC 自己走 `RFC_WORKFLOW.md` 5 步迷你循环）
- **纯治理改动**：没有 PRD，纯 RFC，全程 RFC_WORKFLOW 即可

子 RFC 嵌套递归 —— RFC_WORKFLOW step 3 已写明"嵌套子循环"。

## 与其他治理文档的关系

| 文档 | 角色 |
|---|---|
| `CHARTER.md` §1.1–§1.10 | 不变量（任何 PRD/RFC 不可破坏）|
| `CHARTER.md` §5 | substantive gate 4 项定义（应用于 M1 的 PRD/RFC）|
| `AGENTS.md` §工作派发纪律 | 派发纪律 4 门定义（应用于 M1 的 Phase 拆分）|
| `AGENTS.md` §推送政策 | governance vs artifact commit 推送规则（应用于 M3）|
| `AGENTS.md` §审计-代码耦合 | 审计文档与代码 diff 同 commit 要求（应用于 M3）|
| `docs/RFC_WORKFLOW.md` | 5 步治理决策流程（应用于 M1 内子决策、纯治理改动）|
| **本文档** | 项目级工作流 SSOT |

**冲突仲裁**：`CHARTER.md` > `AGENTS.md` > 本文档 > `docs/RFC_WORKFLOW.md`。

## 术语澄清

本文档的 "Milestone 1-4" 是 **4-Milestone 工作流的工作阶段**，与 `.agent-governance/ROADMAP_MILESTONE_MAP_V0.md` 中的 **roadmap milestone (M16, M24, ...)** 是不同概念：

- 4-Milestone（M1-M4）：工作流阶段，每个项目都跑一次
- Roadmap milestone（M16, M24, ...）：产品/技术路线图的具体目标节点

需要区分时，写 "4-Milestone M1"（工作流）或 "roadmap M24"（路线图）。

## 版本历史

- **v1.1 (2026-05-21)**：从通用版 v1.4 全量 backport + Life Index 适配
  - 新增「适用边界」章节（3 类不适用工作类型）
  - PRD 必含从 8 项扩展到 9 项（加 §8 反对意见门）
  - 派发纪律从 3 门扩展到 4 门（加 §4(d) 任务能力需求，含 Life Index 具体维度）
  - M2 加 Worker-Task Matching（第三类失败定义）+ brief verbatim 退出门规则
  - M3 大重构：rework loop 主路径显性化 / 主审验收 checklist (a)(b)(c)(d) 含 Life Index 元数据清单 + L3 边界测试归档 hint + push 前置门 / Rework 版本管理（`rework/<phase>/v0X` 命名）/ 主审操作纪律 anti-noise / 主控 Agent 循环纪律 livelock prevention
  - M4 加镜像验收清单 + 认知 offload 报告（`.agent-reports/<project-slug>/M4_INTEGRATION_<date>.md` 产出物）
  - 异常 escalate 章节重构为 "escalate vs rework loop" 区分（含触发频率/责任主体对照）
  - Two-ack 模型加角色合并模式
  - *(2026-05-21 late revision，同 v1.1 内增补)*：M3 主审验收从 3 项扩为 4 项，(b) 加 L3 边界测试归档 hint（要求集中在 `test_layer_invariants.py`），新增 (d) push 前置门（blocker gate 必须 push 前实际跑过且全绿）。实证：gbrain absorption final closure
- v1.0 (2026-05-21)：初版，随 `RFC-2026-05-21-phase-2-governance-architecture` 一并 land
