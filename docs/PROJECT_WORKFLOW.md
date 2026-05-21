# Project Workflow

> **版本**: v1.0
> **创建**: 2026-05-21
> **状态**: 活跃
> **权威**: 本文档是 Life Index 项目级工作流的唯一权威。与 `CHARTER.md` §5、`AGENTS.md` §工作派发纪律、`docs/RFC_WORKFLOW.md` 共同构成完整治理框架。

## 流程图

```
┌──── M1 任务需求（唯一决策窗口）───────────────────┐
│  PRD 起草 → CTO review → 主理人 ack #1            │
│  必含：rationale / 目标&非目标 / 影响清单 /      │
│        Phase 拆分 × 派发纪律 3 门 / worktree 拓扑/│
│        完成定义                                   │
└───────────────────────────────────────────────────┘
                       ↓
┌──── M2 任务编排（翻译层，无新决策）───────────────┐
│  推演依赖图 + 生成 Phase brief + 检出 worktree   │
│  主理人不介入                                    │
└───────────────────────────────────────────────────┘
                       ↓
┌──── M3 任务执行（机械执行 PRD）──────────────────┐
│  并行线 1：主控 Agent 轮询 + PR 验收             │
│  并行线 2：Subagents 在 worktree 工作 + PR 合并  │
│  主理人不介入                                    │
└───────────────────────────────────────────────────┘
                       ↓
┌──── M4 质量关卡与终审（集成验证）────────────────┐
│  跨 Phase 接口对齐 + 合并冲突 + 集成测试 + ack #2│
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
3. **影响清单**：
   - 改哪些文档、哪些 invariants（CHARTER §1.1–§1.10）受影响
   - 是否破坏既有 RFC
   - 是否触碰 L2 / schema（CHARTER §1.5 / §1.8）
4. **Phase 拆分**（每个 Phase 必须现场过派发纪律 3 门）：
   - **可证伪退出**：本 Phase PASS/FAIL 是什么命令/测试？
   - **真实消费者**：本 Phase 交付物谁会消费？
   - **有界自主**：本 subagent worktree 边界（哪些目录可写、哪些不能动）
5. **依赖图**：Phase 间串/并行关系
6. **worktree 拓扑**：哪些 Phase 各自独立 worktree
7. **完成定义**（可证伪）：整个项目结束的 boolean 标准
8. **ack #1**：主理人书面 ack（对"应该做"负责）

**CTO checklist**：

- substantive gate 4 项齐备（CHARTER §5）
- 派发纪律 3 门 × 每个 Phase 齐备（AGENTS.md）
- invariant 影响清单 ≠ 空（影响为 0 也要明文写"无影响"）
- 明文"禁止做"清单 ≠ 空

不过 → 退回 M1 重提案。

## M2 任务编排（翻译层，无新决策）

**产物**：`docs/projects/<project-slug>/Phase-Sequence.md` + 各 Phase TDD brief。

**主控 Agent 动作**：

- 按 PRD 依赖图推演 Phase 顺序（并行/串行）
- 按 PRD 各 Phase 拆解生成 subagent brief（含 task 清单、红绿测试、验收标准、自检 checkbox、下一 task 指针、执行总结 placeholder）
- 按 PRD worktree 拓扑机械执行 `git worktree add`

**M2 不引入新决策**。如果发现 PRD 没说"这块归谁"，是 M1 失败信号 → escalate 回 M1（见下"异常 escalate"）。

主理人不介入。

## M3 任务执行（机械执行 PRD）

### 并行线 1（主控 Agent）

- 定时轮询各 subagent 进度
- 验收交付物（Code Review + 自动化 CI + 集成测试）
- 通过 → 勾 Phase Sequence 中的 checkbox
- 不通过 → reject PR，subagent 重做

### 并行线 2（各 subagents）

- 在自己 worktree 内写代码、跑测试
- 按 Phase TDD brief 工作
- 完成 → PR 合并回主分支
- 单 PR 自包含
- subagent 不评价主理人状态、不发起 RFC（必要时通过主控 Agent 提请 escalate）

**约束**：

- 推送政策（`AGENTS.md` §推送政策）
- 审计-代码耦合（`AGENTS.md` §审计-代码耦合：审计文档与代码 diff 同 commit）
- 不动 PRD 未授权的范围

主理人不介入。

## M4 质量关卡与终审（集成验证）

**主控 Agent 动作**：

- 跨 Phase 接口对齐验证
- 合并冲突最终解决
- 整体集成测试（contract + integration 套）
- 对照 PRD 完成定义验收

**ack #2**：主理人对"做对了"负责。书面 ack。

不过 → 回 M3 修复。

## M5 结束

- CHANGELOG `[Unreleased]` 更新（如属 user-facing 改动）
- PRD/RFC status：`accepted` → `implemented`
- 如 CHARTER 改动 → `docs/charter-history/` 归档
- 派发纪律 closeout 检查：出了 code commit 但 CHANGELOG `[Unreleased]` 仍空 → 流程失败信号

## 异常 escalate（不是常规流程，是 M1 失败诊断）

M2/M3 中若发生以下情况，**escalate 回 M1**：

| 情况 | 落点 | 根因 |
|---|---|---|
| 发现需触碰 L2 / schema 但 PRD 没说 | M1 重做影响清单 | PRD 漏写 invariant 触碰 |
| 发现需扩 scope 才能交付 | M1 重做目标 & 非目标 | PRD 边界过窄 |
| Subagent 无法在 worktree 边界内完成 | M1 重做 worktree 拓扑 | PRD 派发纪律不完整 |

**核心原则**：M3 不该有"circuit-breaker"。出现 escalate 不是 M3 流程的常态，是 M1 PRD 质量信号。

每次 escalate 留下 lessons learned，反哺下一份 PRD。**escalate 频率 = PRD 质量度量**。长期目标 escalate → 0。

不要因为出现 escalate 就退回"M3 装 circuit-breaker"的旧范式 —— 那是治标不治本。

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
| `AGENTS.md` §工作派发纪律 | 派发纪律 3 门定义（应用于 M1 的 Phase 拆分）|
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

- v1.0 (2026-05-21)：初版，随 `RFC-2026-05-21-phase-2-governance-architecture` 一并 land
