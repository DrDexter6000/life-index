---
type: process-rfc
status: accepted
created: 2026-05-21
approved: 2026-05-21
approved-by: Life Index Developer
title: Phase-2 治理架构 —— 采用 4-Milestone 项目工作流
related:
  - docs/PROJECT_WORKFLOW.md
  - docs/RFC_WORKFLOW.md
  - CHARTER.md §5
  - AGENTS.md §工作派发纪律
  - docs/rfc/RFC-2026-05-19-foundation-freeze.md (closed out 2026-05-21)
---

# RFC-2026-05-21: Phase-2 治理架构 —— 采用 4-Milestone 项目工作流

## §1 问题

Foundation Freeze v1 退出（2026-05-21, commit `bc16707`）后进入 Phase-2（模块阶段），Life Index CLI 工作模式从"单线追加功能"转向"多模块并发开发"。现行治理体系不足：

**症状 A**：`docs/RFC_WORKFLOW.md`（5 步）只覆盖**治理决策**流程，不覆盖**项目/模块/功能级工作流**。Phase-2 将有多个并行的"模组/功能开发"循环，需要项目级 SSOT。

**症状 B**：现行无明文"主控 Agent + Subagents 并发编排"模式。GG Master 风格（worktree-per-subagent / 异步 review / merge-time audit）需要主架构 anchor。

**症状 C**：现行无明文"M1 前置决策、M2-M4 不打扰主理人"的责任划分。主理人在 Phase-2 应只在两点介入（"应该做" + "做对了"），不被中间细节打扰。

## §2 决策

采用 **4-Milestone 项目工作流**（M1 任务需求 / M2 任务编排 / M3 任务执行 / M4 质量关卡），SSOT 落在 `docs/PROJECT_WORKFLOW.md`。立即生效。

### §2.1 核心原则

- **M1 唯一决策窗口**：派发纪律 3 门 × 每个 Phase、invariant 影响清单、明文"禁止做/必须做"、worktree 拓扑全部在 M1 PRD 写清楚
- **M2 翻译层**：无新决策；如发现 PRD 漏写 → escalate 回 M1（这是 M1 失败诊断，不是 M3 circuit-breaker）
- **M3 机械执行**：subagents 在 worktree 工作，主控 Agent 验 PR；主理人不介入
- **M4 集成验证**：跨 Phase 接口对齐 + ack #2
- **Two-ack**：M1 ack #1（"应该做"）+ M4 ack #2（"做对了"）—— 主理人介入仅此两点

### §2.2 与现行治理文档的关系

| 文档 | Phase-2 中的角色 |
|---|---|
| `CHARTER.md` §1.1–§1.10 invariants | 不动；任何 PRD 不可破坏 |
| `CHARTER.md` §5 substantive gate | 不动；内化为 M1 PRD 必含项 |
| `AGENTS.md` 派发纪律 3 门 | 不动；内化为 M1 Phase 拆分必含项 |
| `AGENTS.md` 边界（v3.3 新增） | 不动；跨 4 Milestone 全程适用 |
| `docs/RFC_WORKFLOW.md` 5 步 | 不动；降为子工具，用于 M1 内部子决策或纯治理改动 |

**仲裁优先级**：CHARTER > AGENTS > PROJECT_WORKFLOW > RFC_WORKFLOW。

### §2.3 切换时机

**立即生效**（2026-05-21）。Foundation Freeze v1 已 closeout（commit `bc16707`），无在飞工作受影响。

之后所有项目/模块/功能/debug 工作走 4-Milestone 框架。

## §3 不在本 RFC 内

- 不修改 CHARTER §1.1–§1.10 invariants
- 不修改 CHARTER §5 substantive gate
- 不修改 AGENTS.md 派发纪律 3 门
- 不修改既有 RFC（`RFC-2026-05-19`、`RFC-2026-05-20-governance-scope-correction`、`RFC-2026-05-20-foundation-module-interface`、`RFC-2026-05-20-inheritor-as-product-object` 均不变）
- 不删除 `docs/RFC_WORKFLOW.md`（继续作为子工具有效）

## §4 反对意见 addressed

| 反对 | Response |
|---|---|
| 「`RFC_WORKFLOW.md` 刚 land（commit `19bad8d`，2026-05-20），又改？」 | 不是改 RFC_WORKFLOW，是加一个**上层** SSOT。RFC_WORKFLOW 在新框架里继续作为 M1 内子工具有效，自身规则不变。两者关系类比：PROJECT_WORKFLOW 之于 RFC_WORKFLOW = 工作流框架之于决策子流程。 |
| 「4 个 Milestone 太重，debug 都要走？」 | 压缩形态明文写在 `PROJECT_WORKFLOW.md`：极简变更（< 10 min）允许 M1+M2 合并、M3+M4 合并、单 ack 覆盖。`RFC-2026-05-20-governance-scope-correction` 的压缩形态（ack→push < 10 min）已演示合法性。 |
| 「M2 翻译层听起来空，会不会形式化？」 | M2 是计算密集（Phase 依赖图推演 + worktree 拓扑生成 + brief 生成）但**决策稀疏**（无新约束）。M2 出 escalate 直接定位到 M1 PRD 缺陷 —— 这本身就是 escalate 的价值。M2 不空，只是不引入新决策。 |
| 「立即切换会不会破坏 in-flight 工作？」 | Foundation Freeze v1 已 closeout（commit `bc16707`，2026-05-21），无在飞工作。所有未来 Phase-2 工作起步即用新框架。切换边界干净。 |
| 「为何不等真正开始 Phase-2 工作再 land？」 | "立即切换"是主理人立场（见 2026-05-21 governance 讨论），不为 Phase-2 启动留模糊地带。文档 land 在前，工作启动在后，主理人审 PRD 时已有框架可对照。 |
| 「circuit-breaker 不要了，万一 agent silent-expand scope 怎么办？」 | M3 不装 circuit-breaker，是把质量压力放回 M1（"前期策划推演好，后期执行别有争议"）。Agent silent-expand 在 M3 中由主控 Agent 在 PR 验收时捕捉（PR 越界 PRD = reject），不需要 agent 自我中断。 |

## §5 影响清单

| 文件 | 改动 |
|---|---|
| `docs/PROJECT_WORKFLOW.md` | **新建**（4-Milestone 框架 SSOT，~210 行）|
| `docs/rfc/RFC-2026-05-21-phase-2-governance-architecture.md` | **新建**（本 RFC）|
| `AGENTS.md` 必读导航表 + 文档层级表 | 加 `docs/PROJECT_WORKFLOW.md` 行；版本 v3.4 → v3.5 |
| `CHARTER.md` | **不动** |
| `docs/RFC_WORKFLOW.md` | **不动**（继续作为 M1 内子工具）|

### invariant 影响检查

| invariant | 是否受影响 |
|---|---|
| §1.1 数据主权 | 无 |
| §1.5 L2 不持 LLM | 无 |
| §1.7 三条底线 | 无 |
| §1.8 高迁移成本 schema | 无 |
| §1.9 Agent-Native Module | 无 |
| §1.10 Module-Foundation 边界 | 无 |
| §5 修订流程 | 无（substantive gate 4 项继续适用于 M1 PRD）|

**本 RFC 不破坏任何 invariant**。

## §6 完成定义（可证伪）

- `docs/PROJECT_WORKFLOW.md` 创建，含 4-Milestone 详解 + Two-ack + 压缩形态 + 异常 escalate
- `docs/PROJECT_WORKFLOW.md` 状态从"草案"转为"活跃"
- `AGENTS.md` 升级到 v3.5，含 PROJECT_WORKFLOW 引用行
- 本 RFC frontmatter `status: accepted`、含 `approved-by: Life Index Developer`
- atomic governance commit pushed 到 origin/main

## §7 后续动作锚点

- **Phase-2 第一个工作 = Item 2**（gbrain 借鉴模块）按 4-Milestone 走，作为新框架的首次实战验证
- **Item 3（GUI v1）** 若并行启动，亦按 4-Milestone 走
- **每次 escalate**（M2/M3 中发现 PRD 漏写）作为 PRD 质量改进样本，反哺下一份 PRD
- **6 个月后 retrospective**（2026-11-21 前后）：评估 escalate 频率与项目周期，决定是否需要 RFC 升级框架
