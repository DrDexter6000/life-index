# Web GUI Next-Phase Roadmap

> **Status**: planning draft after v1.4.0 release
> **Scope**: 用于承接 v1.4.0 之后的功能优先级、MVP 边界与计划拆分建议

## Planning goal

在不打破 v1.4.0 已完成交付闭环的前提下，选出最适合进入下一轮实现周期的 Web GUI 功能，并避免把 post-release polish、产品探索与新实现工作混成一个大批次。

## Recommended execution order

### Step 1 — 先做“那年今日”计划

**Reason:**
- 与 Life Index 的核心叙事最一致
- 风险相对低
- 更接近读取/展示增强，而不是新的复杂编辑系统

**Expected output:**
- 单独 feature spec / implementation plan
- 明确入口（dashboard 或独立页）
- 明确数据来源与空状态

### Step 2 — 再做“写作模板增强”计划

**Reason:**
- 可作为现有 write 功能的增强项继续演进
- 但需要明确只做轻量增强，不要演化成模板管理后台

**Expected output:**
- 轻量模板增强范围说明
- 与现有 write service / template 的衔接方案

### Step 3 — 最后再判断“连续记录里程碑”是否值得进入实现

**Reason:**
- 它最容易改变产品气质
- 需要先澄清“鼓励记录”与“打卡驱动”之间的边界

**Expected output:**
- 产品边界结论
- 只有在结论清晰时才进入 spec / plan 阶段

## What can be batched together

### Batch A — 可以一口气完成

1. 那年今日 feature prioritization
2. 那年今日 MVP scope 定义
3. 那年今日 spec / plan 文档起草

### Batch B — 可以一口气完成

1. 写作模板增强优先级确认
2. 模板增强 MVP / non-MVP 边界
3. 模板增强 spec / plan 文档起草

### Batch C — 不建议直接并入 A/B

1. 连续记录里程碑的产品边界讨论
2. 是否引入 streak-style feedback 的价值判断
3. 若确认值得做，再单独立项

## Recommended immediate next move

如果继续推进，最合理的下一步是：

1. 只针对 **那年今日** 做新一轮 brainstorming / spec / plan
2. 完成后，再决定是否顺势把 **写作模板增强** 作为下一批一口气做完

## Anti-bloat reminder

下一阶段最需要避免的是：

1. 把多个新 feature 混成一个“大版本大杂烩”
2. 在没有产品边界澄清前就实现 streak/gamification
3. 把“写作模板增强”膨胀为复杂模板管理系统
