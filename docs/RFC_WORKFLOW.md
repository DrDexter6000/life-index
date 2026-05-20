# RFC Workflow

> **版本**: v1.0
> **创建**: 2026-05-20
> **状态**: 活跃
> **权威**: 本文档是 Life Index 项目 RFC 流程的唯一权威。与 `CHARTER.md` §5、`AGENTS.md` §工作派发纪律、`AGENTS.md` §推送政策 共同构成完整治理框架。

## 流程图

```
┌──── 计划阶段 ───────────────────────┐
│  1. Agent 提案（RFC 起草）          │
│         ↓                          │
│  2. CTO review + 主理人 ack #1     │
└─────────────────────────────────────┘
                 ↓
┌──── 实施阶段 ───────────────────────┐
│  3. Agent 实施                     │
│         ↓                          │
│  4. CTO 审计 + 主理人 ack #2       │
└─────────────────────────────────────┘
                 ↓
               5. 结束
```

## 五步详解

### 第 1 步：Agent 提案（RFC 起草）

**产物**：`docs/rfc/RFC-YYYY-MM-DD-<title>.md`，status: `proposed`。

**必含四件套**（CHARTER §5 substantive gate 的前三项 + 范围）：

- **rationale**：为什么要改、解决什么问题
- **反对意见 addressed**：≥ 2 条反对 + 提案如何回应
- **影响清单**：改哪些文档、哪些 invariants 受影响、是否破坏既有 RFC
- **范围**：在做什么 / 不做什么

### 第 2 步：CTO Review + 主理人 ack #1

**CTO checklist**：

- substantive gate 四件套齐备
- 不触碰 CHARTER §1.1–§1.10 不变量、不弱化 §5.3
- 如含派发：派发纪律 3 门齐备（可证伪退出 / 真实消费者 / 有界自主）
- 反对意见非稻草人，真有对抗性
- 与现有 RFC 兼容（不撞 Foundation Freeze v1 §4 defer 等）

**Ack #1**：主理人对"应该做"负责。书面 ack（会话中明确）。

不过 → 退回第 1 步重提案。

### 第 3 步：Agent 实施

**约束**：

- 在 worktree（非 main 直改）
- 多 commit 可，每 commit 自包含
- 中途发现 scope 扩张 → **不要 silent expand**，停下来回第 1 步起 follow-up RFC（嵌套子循环）
- 触 L2 / schema → 需独立 substantive gate

### 第 4 步：CTO 审计 + 主理人 ack #2

**CTO checklist**：

- 代码 diff 对得上 RFC §2 决策
- Layer invariant 测试过（`tests/contract/test_layer_invariants.py`）
- 若触搜索：Gold Set 回归 ≥ 基线（CHARTER §4.5）
- 退出标准命令/测试 PASS

**Ack #2**：主理人对"做对了"负责。书面 ack。

不过 → 退回第 3 步修复。

### 第 5 步：结束

- Commit（原子优先）+ push（按 `AGENTS.md` §推送政策）
- CHANGELOG `[Unreleased]` 更新（如属 user-facing 改动）
- RFC status：`proposed` → `accepted`（如已实施完成 → `implemented`）
- 如 CHARTER 改动 → `docs/charter-history/` 归档

**派发纪律 closeout 检查**：出了 code commit 但 CHANGELOG `[Unreleased]` 仍空 → 流程失败信号，倒查第 3-4 步。

## 边界情况

| 情况 | 落点 |
|---|---|
| CTO review 不过 | 第 1 步重提案 |
| 实施中 scope 扩张 | 暂停，第 1 步起 follow-up RFC（嵌套子循环）|
| CTO 审计不过 | 第 3 步修复 |
| 治理 commit vs artifact commit 区分 | 第 3-5 步实操，非独立 stage |
| 派发纪律 / substantive gate 检查 | 内嵌在 CTO review，非独立 stage |
| 极简变更（< 10 分钟） | 流程压缩：1-2 合并、3-4 合并、单 ack 覆盖 |

## RFC 类型与流程差异

| 类型 | 示例 | 触发 §5 substantive gate？| 触发派发纪律？ |
|---|---|---|---|
| **CHARTER amendment** | RFC-2026-05-20-governance-scope-correction | ✅ 必须 | ❌ 通常不派发新工作 |
| **Process RFC**（改 AGENTS.md / playbook） | 拟 phase-2-governance | 取决于是否触 CHARTER | ❌ 通常 |
| **Milestone RFC**（定义阶段退出标准） | RFC-2026-05-19-foundation-freeze | ❌ 不动 CHARTER | ✅ 定义后续派发的 gate |
| **Feature/Implementation RFC** | 拟 gbrain-source-tier-boost | 仅当触 L2 contract | ✅ 派发实施 |

## 与其他治理文档的关系

| 文档 | 角色 |
|---|---|
| `CHARTER.md` §5 | substantive gate 4 项定义 + 修订流程框架 |
| `AGENTS.md` §工作派发纪律 | 派发纪律 3 门定义 + 边界（不评价主理人状态）|
| `AGENTS.md` §推送政策 | governance vs artifact commit 推送规则 |
| `AGENTS.md` §审计-代码耦合 | 审计文档与代码 diff 同 commit 要求 |
| **本文档** | 把上述全部串成完整闭环 |

**冲突仲裁**：`CHARTER.md` > `AGENTS.md` > 本文档。

## 压缩版示例

`RFC-2026-05-20-governance-scope-correction` 执行轨迹：

| 步 | 实际发生 |
|---|---|
| 1 | CTO 起草 RFC |
| 2 | CTO 自审 + 主理人 ack（"ack 全文"）|
| 3 | 11 个 edits（实施即 land）|
| 4 | CTO 自审 diff + 主理人 ack（"原子 commit, push"）|
| 5 | commit `8c9028f` 已 push |

从 ack 到 push 完成 < 10 分钟。极简变更的合法压缩形态。
