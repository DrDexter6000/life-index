---
type: process-rfc
status: accepted
created: 2026-05-20
approved: 2026-05-20
approved-by: Life Index Developer
title: 地基-模块接口稳态模型
related:
  - CHARTER.md §1.5 §1.8 §1.9 §1.10
  - RFC-2026-05-19 Foundation Freeze v1（私有治理 RFC）
  - 里程碑 M16（L2 CLI 契约冻结 + 层级 CI 门）
---

# RFC-2026-05-20: 地基-模块接口稳态模型

## §1 问题

几十年尺度上，地基（L2）与模块（L3）如何共存、相互升格、避免互相破坏。CHARTER §1.10 给了"pull not push"的种子但未展开稳态。本 RFC 把它显性化。

## §2 4 层稳态模型

| 层级 | 是什么 | 怎么演化 |
|---|---|---|
| L2 原语 | 原子、确定性、可组合；不懂工作流 | RFC 升格；≥2 模块需要或清晰架构理由才进 |
| L3 模块 | 工作流编排；组合 L2 + opt-in LLM；含工作流知识 | 自由生长；RFC-2026-05-19 §8 闸门通过 = 新模块出生 |
| 接口契约 | L2 公开 JSON shape + schema_version 戳 | major 才允许 break；minor 只许 additive |
| 数据 schema | frontmatter / entity / topic | 高迁移成本（§1.8）；RFC + 迁移路径；旧日记永远可读 |

## §3 6 类演化事件

**模块出生** —— §8 闸门通过 → 模块本地代码，不动 L2。

**模块死亡** —— 没人用就删，L2 不变。

**原语升格** —— 多模块共用本地代码 → RFC → 进 L2，带 schema_version。

**原语弃用** —— L2 原语没消费者 → deprecation → 版本号过渡 → 删。

**Schema 加字段** —— 高迁移成本，RFC + 默认值 / 可选 / 迁移脚本；旧日记永远可读。

**Schema 改字段语义** —— 极少发生；§1.8 RFC + major-version + 自动迁移。

## §4 永远不进 L2 的清单

- 默认路径 LLM 调用（§1.5 / §1.9）
- provider-specific 代码（§1.9）
- 工作流知识（归属模块）

## §5 与 M16 的关系

M16（L2 CLI 契约冻结 + 层级 CI 门）将按本框架实现 CI 门 —— 检测 L2 是否引入 LLM 调用 / provider 代码 / 工作流知识。本 RFC 是 M16 的设计 anchor。

## §6 后续动作锚点

Freeze v1 完成后，本 RFC 内容并入 CHARTER §1.10 扩展节。
