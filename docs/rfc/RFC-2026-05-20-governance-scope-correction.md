---
type: process-rfc
status: accepted
created: 2026-05-20
approved: 2026-05-20
approved-by: Life Index Developer
title: 治理范围矫正 —— §5 时钟门改 substantive 门 + AGENTS.md 剥离状态判断
related:
  - CHARTER.md §5
  - AGENTS.md v3.2 §工作派发纪律
  - docs/rfc/RFC-2026-05-19-foundation-freeze.md
---

# RFC-2026-05-20: 治理范围矫正

## §1 问题

本 RFC 合并解决两个症状同源的问题。

**问题 A（时钟门）**：CHARTER §5 规定 amendment 提案到 land 需 24h cooldown。该机制原型来自多 stakeholder 组织治理 —— 给异步审阅留时间。Life Index 是 1 主理人 + LLM 协作项目（2026 Agentic 时代），单一 stakeholder + 7×24 可对话 LLM，cooldown 的现实前提不成立。强制 24h 是把 *time* 当作 *reflection quality* 的 proxy，是 Goodhart 误用：让决策变好的是反思过程，不是时钟。

**问题 B（状态门）**：AGENTS.md v3.2 §工作派发纪律 缺乏明文边界声明 —— 未明确指出 CTO 工具的评价对象是「工作内容」而非「主理人状态」。这一沉默给了 CTO agent 默认越界许可：从消息模式读情绪、把状态读作为 governance 依据。这是从「工程/代码治理」（CTO 本职）越界到「主理人行为治理」（人类学/心理学范畴）。

（land 时 audit 确认：现有「红旗」表 5 行全部关于工作内容，无状态判断行需删除；本 RFC 的实际修订是 add-only —— 新增「边界」段明文声明范围。）

事故案例：2026-05-20 CTO 把「主理人连发 4 条相同消息」读成情绪激动，并作为拒绝当晚 amendment 的依据；实际是 API Error 529 retry。一次误读暴露整条推理链不稳健。

两个问题的共同根因：**governance 工具的合法作用域是决策和代码，不是时钟、也不是人的状态**。

## §2 决策

### §2.1 CHARTER §5：时钟门 → substantive 门

废除「24h cooldown」。替换为 **substantive gate**：任何 CHARTER 修订提案必须满足下列 4 项才能 land：

| # | 内容 | 评价方 |
|---|---|---|
| 1 | **rationale** —— 为什么要改、解决什么问题 | CTO 起草，主理人审 |
| 2 | **反对意见 addressed** —— CTO 列出至少 2 条反对、提案如何回应 | CTO 列，主理人判 satisfied |
| 3 | **影响清单** —— 改哪些文档、哪些 invariants 受影响、是否破坏既有 RFC | CTO 列 |
| 4 | **主理人 ack 签字** —— 显式书面 ack（不可委托） | 主理人 |

四项齐备 → 立即 land。**起草到 land 无强制最短时间间隔**。

### §2.2 AGENTS.md：剥离状态判断 mandate（v3.2 → v3.3）

修订 §工作派发纪律 段：

- **保留**：派发纪律核心三门 —— 可证伪退出 / 真实消费者 / 有界自主（这三门评价工作内容，不评价人的状态）
- **保留**：现有「红旗」表 5 行（land 时 audit 确认全部关于工作内容，无状态判断行需删除）
- **新增**：在「适用范围」段后新增「**边界**」段：

  > **边界**：本纪律针对*派发的工作*（决策内容、代码改动、模块边界），不针对*主理人的状态*（情绪、节奏、表达方式、消息频率）。CTO agent 不基于主理人状态做 governance 决定。

- **版本号**：v3.2 → v3.3
- **最后更新日期**：2026-05-19 → 2026-05-20

## §3 不在本 RFC 内

- 不修改派发纪律核心三门（可证伪退出 / 真实消费者 / 有界自主）
- 不修改 Foundation Freeze v1（RFC-2026-05-19）
- 不修改两份 2026-05-20 RFC（继承者 / 4 层模型）
- 不预先设计模块阶段治理（Phase-2 Governance RFC 后续单独处理）

## §4 反对意见 addressed（兼作 §2.1 #2 的范本应用）

| 反对 | Response |
|---|---|
| 「去掉 cooldown 后，热度下决策会变多」 | substantive gate 的 4 项中 rationale + 反对意见 addressed 都需要书面写出来；写不出来的提案过不了关。书写本身就是 forcing function，不需要时钟。 |
| 「1 人项目缺少 stakeholder 互审」 | LLM 作为 CTO agent 履行互审职责（列反对、addressed 检查），且响应延迟低于人类 stakeholder。等同于有 1 个 7×24 的 reviewer。 |
| 「AGENTS.md 删除状态判断会让 CTO 失去早期预警」 | CTO 的早期预警职责是**工作内容偏移**预警（派发缺消费者、超出 worktree），不是**主理人状态**预警。后者本来就不在 CTO 职责内。 |
| 「本 RFC 自身是 amendment，按旧 §5 应等 24h」 | 本 RFC 的 substantive 内容（§1 诊断 + §2 决策 + §3 边界 + §4 反对 addressed + §5 影响清单）已齐备；主理人通过本会话 ack 即满足新 §2.1 的 4 项。新规则一旦 land 即追认本 RFC 的 land 流程（chicken-and-egg 由内容质量化解，不由时钟化解）。 |

## §5 影响清单

| 文件 | 改动 |
|---|---|
| `CHARTER.md` §5 | 「24h cooldown」条文 → 「substantive gate (4 项)」条文 |
| `AGENTS.md` §工作派发纪律 | (a) 开头新增「作用域」句；(b)「红旗」表删除状态判断行；版本号 v3.2 → v3.3 |
| `docs/rfc/RFC-2026-05-20-governance-scope-correction.md` | 本 RFC 新建 |

invariants 影响检查：

| invariant | 是否受影响 |
|---|---|
| §1.1 数据主权 | 无 |
| §1.5 L2 不持 LLM | 无 |
| §1.7 三条底线 | 无 |
| §1.8 高迁移成本 schema | 无 |
| §1.9 Agent-Native Module | 无 |
| §1.10 Module-Foundation 边界 | 无 |
| §5 修订流程 | **本 RFC 即修订本条**（时钟门 → substantive 门） |

无 invariant 破坏；唯一受影响的就是 §5 自身。

## §6 完成定义（可证伪）

- `CHARTER.md` §5 改为 substantive gate 条文（含 4 项 + 「无强制最短时间间隔」明文）
- `AGENTS.md` 升级到 v3.3，含「作用域」句 + 红旗表已清理 + 版本号 bump
- 本 RFC 文件 landed 到 `docs/rfc/`
- 本 RFC frontmatter `approved-by` 含主理人签字记录

## §7 后续动作锚点

- 本 RFC 通过即生效，**无需等待 Foundation Freeze v1**
- Phase-2 Governance RFC（M24 ship 后的模块阶段治理：异步 review / worktree-per-module / merge-time-audit）由后续 RFC 单独处理
