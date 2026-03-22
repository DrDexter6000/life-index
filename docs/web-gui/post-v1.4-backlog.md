# Post-v1.4 Backlog

> **Status**: post-release planning note
> **Scope**: v1.4.0 发布后的文档收尾、product polish 与下一阶段候选功能

## Purpose

本文件用于承接 v1.4.0 发布后的剩余工作，避免继续在 release closeout 文档中混杂新的实现目标。

## Priority buckets

### P1 — Documentation closeout

1. 统一 Web GUI 文档中的 release / handoff / delivered wording
2. 明确哪些设计项已发布、哪些只是后续候选功能
3. 在后续 release 时保持 `CHANGELOG.md` 与 Web GUI 文档的状态同步

### P2 — Post-MVP product polish

1. 更细粒度的 visual refinement（信息密度、视觉节奏、空状态层级）
2. 更细粒度的 write / edit 交互 polish（helper text、progress/status、移动端细节）
3. attachment / weather 相关 UX 继续细化，但仅在真实使用反馈支持时推进

### P3 — Next feature candidates

以下项目更适合作为新一轮产品规划的输入，而不是 v1.4.0 收尾的一部分：

1. 那年今日
2. 写作模板增强 / 模板管理能力
3. 连续记录里程碑 / streak-style feedback

> 注意：这些候选项在进入实现前，应先重新确认其是否已被部分交付、是否仍符合当前产品边界、以及是否值得作为新的版本目标独立立项。

## Recommended feature priority

### Priority 1 — 那年今日

**Why first:**
- 与 Life Index 的“人生档案馆 / 时间回望”定位最贴合
- 主要是读取 / 聚合 / 展示能力增强，风险低于引入大量新写入交互
- 更容易作为独立增量交付，不必重构当前 write / edit 主链路

**Suggested MVP:**
- 在 dashboard 或独立入口展示“历史上的今天”日志条目
- 支持按月日匹配历史 journal
- 若无结果，给出清晰 empty state

**Non-MVP:**
- 多年对比视图
- 富时间线可视化
- 自动生成回顾摘要

### Priority 2 — 写作模板增强 / 模板管理能力

**Why second:**
- 已有写作模板基础，增强成本比全新功能更可控
- 直接服务 write 页面高频使用场景
- 但如果引入“模板管理”，很容易从轻量增强膨胀成配置系统

**Suggested MVP:**
- 明确现有模板的组织方式与入口
- 增加少量高价值模板或模板分类
- 保持“选择模板 → 写入表单预填”这一轻量路径

**Non-MVP:**
- 完整模板 CRUD 管理后台
- 模板导入导出
- 用户级复杂模板元数据系统

### Priority 3 — 连续记录里程碑 / streak-style feedback

**Why third:**
- 具备激励价值，但最容易把产品往 habit-tracker 方向拉偏
- 需要先明确 Life Index 是否真的要强化“打卡感”而非“档案感”
- 文案与产品边界最需要谨慎处理

**Suggested MVP:**
- 只做轻量 streak / milestone 提示
- 避免侵入主流程
- 强调鼓励性而非惩罚性反馈

**Non-MVP:**
- 排行榜/徽章系统
- 强提醒机制
- 复杂 gamification 体系

## MVP boundary recommendation

### Recommended next version MVP

建议下一版本只纳入：

1. **那年今日**（完整 MVP）
2. **写作模板增强**（仅轻量增强，不引入模板管理系统）

### Recommended non-MVP / defer

建议暂缓：

1. **连续记录里程碑**，除非先完成产品边界澄清
2. 任何会引入“独立配置中心 / 模板后台 / 激励体系”的扩张性实现

## Decision summary

- **最适合立即进入计划阶段的功能**：那年今日
- **最适合打包一起评估、但不应膨胀的增强项**：写作模板增强
- **最适合延后、先做产品边界讨论的项**：连续记录里程碑

## Recommended batching

### Batch 1 — 可一口气完成

1. 文档状态统一
2. wording consistency closeout
3. backlog 明确归档

### Batch 2 — 可一口气完成

1. 对 P3 候选功能做价值排序
2. 为下一版本确定 MVP / non-MVP 边界
3. 形成新的实施计划或子计划文档

## Not recommended as one big batch

不建议把零散 UI polish、未来 feature 设计、以及新的实现工作混成一个大批次推进。更合理的方式是：

1. 先做文档与范围收口
2. 再做 feature prioritization
3. 最后再进入单独版本的实现周期
