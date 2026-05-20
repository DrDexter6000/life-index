---
type: process-rfc
status: implemented
created: 2026-05-19
approved: 2026-05-19
approved-by: Life Index Developer（user full authorization for map/governance changes）
implemented: 2026-05-21
title: Foundation Freeze v1 — CLI 地基封板线与里程碑重排
related:
  - CHARTER.md §1.7 §1.8 §1.10
  - .agent-governance/ROADMAP_MILESTONE_MAP_V0.md
  - docs/rfc/RFC-2026-05-15-advanced-module-developer-contract.md
---

# RFC-2026-05-19: Foundation Freeze v1

## 1. 问题

"地基阶段"缺少一个可证伪的"完成"定义。

一个自主编排循环，面对不可证伪的目标（"把地基弄稳固"），无法返回 done，
只能持续追加。实测后果：v1.0.0（2026-05-06）后 13 天 130 个 commit、
数亿 token 消耗、CHANGELOG `[Unreleased]` 为空 —— 大量工程投入、
零用户可见交付。

根因不在编排执行，在规格：目标不可证伪。

## 2. 目标

为 "CLI 地基" 设定一条 falsifiable 的封板线。

封板线由一组稳定**契约**构成，不是一张**功能**清单。§3 全部达成 →
宣布 **Foundation Freeze v1** → 进入模块阶段。

本 RFC 不修改 CHARTER（不触发 §5 修订流程），不变更任何公开数据格式，
不引入新依赖。

## 3. 退出标准（Foundation Freeze v1）

| # | 标准 | 交付物 | 现状 |
|---|---|---|---|
| 1 | L2 CLI JSON 契约冻结：8 个公开命令（search / smart-search / aggregate / analyze / entity / timeline / health / generate-index）的 JSON shape + 字段语义 + 错误码 + SLO 全部见于 `docs/API.md`，并打 `schema_version` 戳 | 里程碑 M16 | ✅ 已达成 |
| 2 | 高迁移成本 schema 冻结：frontmatter 核心字段、entity schema（ADR-024）、topic taxonomy、evidence-pack schema（M03） | M03 + 既有 | ✅ 基本完成 |
| 3 | 层级不变量 CI 硬门：一个全局测试，断言 L2 默认路径不得 import LLM client、不得跨层 | 并入 M16 | ✅ 已达成 |
| 4 | Eval 回归门：gold set + 冻结 baseline + 回归 gate | M04 | ✅ 完成 |
| 5 | 模块开发者契约 | RFC-2026-05-15 | ✅ 完成 |
| 6 | 一个真实瘦模块端到端跑通，仅消费上述契约 | 里程碑 M24 | ✅ 已达成 |

**判定**：Foundation Freeze v1 达成 **当且仅当** #1–#6 全部 ✅。
所有 6 项已于 2026-05-21 达成（见 §9 closeout 记录）。

## 4. 不在封板线内 —— 显式 defer

以下里程碑**不是**封板必需，一律 defer，不在 Freeze v1 达成前启动：

M06（余下扩张）、M07（语义候选 / supplement）、M08、M09、M11、M12、
M13、M14、M17、M18、M19。

它们是检索 / 证据增强，属 CHARTER §1.8 低迁移成本范畴，应由真实模块
按 §1.10「基元升格」流程拉动：模块本地先实现，经验证再 RFC 升格为
L2 原语。

现有 supplement / planner 代码**不删除，就地冻结，停止追加挂件**
（不再为未接线的 seam 追加测试或探针）。

M10（Event / Episode 层）与 M15（写入期结构化字段）涉及 CHARTER §1.8
高迁移成本 schema：**先做产品决策，不先建功能**；在产品决策前不得让
相关字段渗入 L1 数据格式。

M20 / M21（公开定位、demo 模板）依赖项目推广意愿；当前无限期 defer。

## 5. 里程碑地图变更（已随本 RFC 一并应用）

对 `.agent-governance/ROADMAP_MILESTONE_MAP_V0.md` 的变更（地图 §3.2
material change，经用户授权）：

1. **M16 提前**：重写 §5「近期顺序」，M16 列为 Freeze 期下一里程碑；
   层级不变量 CI 门并入 M16 范围。
2. **新增 M24**：第一个真实瘦模块。建议「那年今日」（on-this-day）：
   日期过滤 search + index-tree 导航，所需原语均已存在。M24 是 Freeze
   的验证步 —— 用真实消费者证明地基契约可用。
3. **编号校正**：supplement 工作在执行中被本地标为 M08–M11，与地图
   既有 M08（索引导航）/ M09（日期导航）/ M10（Event）/ M11（chunk）
   冲突。裁定：supplement 工作对应地图 **M07**（语义候选策略）；执行时
   的 M08–M11 标签**作废**；地图 M08–M23 维持原义不变。代码注释中遗留
   的 "M08 / M09" supplement 引用一并更正为 M07（planner 的 M06 正确，
   不动）。
4. **状态更新**：M07 标为 `accepted`（私有未接线切片；公开接线仍由
   用户 gate，见 §4）。

## 6. 完成的定义（可证伪）

- Freeze v1 达成**前**：不启动任何 §4 所列里程碑。Freeze 期只做
  M16、M24 及 M16 内含的 CI 门。
- Freeze v1 达成**后**：进入模块阶段；此后新增 L2 基元一律走 CHARTER
  §1.10 RFC 升格流程，须指明真实消费者。

## 7. 非目标

- 不删除既有 supplement / planner 代码。
- 不修改 CHARTER.md，不触发 CHARTER §5 修订流程。
- 不变更任何公开 CLI / 数据格式（M16 是为既有契约补文档与版本戳，
  不是改契约）。
- 不引入 plugin loader / 动态发现 / runtime registry。

## 8. 仍属用户、不可委托的决策

本 RFC 之后，执行层（RFC、里程碑地图、CI 门、M16、M24 脚手架）可在
授权范围内自主推进。

**唯一保留给用户、不可委托的职能**：任一里程碑派发前，由用户回答一句
「哪个真实消费者现在需要它？」。答案若指向尚不存在的模块 → 该里程碑
等待。

此即 Freeze 之后防止"地基阶段无限延长"复发的唯一闸门。它不是审代码、
不是设计评审 —— 是一句话的方向判断，刻意保持到任何疲惫状态下都能在
30 秒内完成。把它委托出去，定义上就是本 RFC §1 所述问题本身。

## 9. Closeout (2026-05-21)

退出标准 #1–#6 全部达成：

- **#1** L2 CLI JSON 契约：6 个公开命令加 `schema_version` 戳，`docs/API.md` 对齐 (commits `fdb6718`, `18a270b`)；M16 schema_version 契约测试 12/12 + public contract docs 38/38 + pas2 alignment 测试 26/26 通过。
- **#2** 高迁移成本 schema：维持冻结状态（无变更）。
- **#3** 层级不变量 CI 硬门：`planner_types.py` 抽离 + 不变量测试 +65 行 (commit `957b46d`)；`tests/contract/test_layer_invariants.py` 5/5 通过。
- **#4** Eval 回归门：workflow + 测试加强 (commit `50ba6c7`)。
- **#5** 模块开发者契约：维持（RFC-2026-05-15）。
- **#6** 真实瘦模块端到端：`tools/on_this_day/`（3 文件，仅 stdlib，**无 LLM/provider import**，subprocess 调 L2 CLI 模式）；`test_on_this_day_cli_contract.py` 8/8 通过；CHANGELOG `[Unreleased]` 含 user-facing 条目。

**全套 contract + integration 测试**：535 passed / 1 skipped (无关) / 1 xpassed (无关) / 0 failed / 0 errored。

**§1 诊断症状反转**：CHANGELOG `[Unreleased]` 从空 → 454 字符 user-facing 内容（schema_version 公开 + on-this-day 可发现 + API.md 对齐）。

状态：`accepted` → `implemented`。

下一步：进入 Phase-2（模块阶段），按 `RFC-2026-05-21-phase-2-governance-architecture`（待 land）规定的 4-Milestone 工作流执行。
