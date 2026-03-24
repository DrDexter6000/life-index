# Web GUI Next-Phase Roadmap

> **Status**: next-phase planning draft (post-v1.4 current-state roadmap)
> **Scope**: 用于承接 v1.4.0 之后的功能优先级、MVP 边界与计划拆分建议

## Planning goal

在不打破 v1.4.0 已完成交付闭环的前提下，选出最适合进入下一轮实现周期的 Web GUI 功能，并避免把 post-release polish、产品探索与新实现工作混成一个大批次。

> 当前说明：本路线图描述的是 **closeout 之后** 的下一阶段候选方向；当前阶段仍优先完成文档状态统一、runtime/sandbox 收口与非阻塞 polish。

> **2026-03-25 状态说明**：历史 `upgrade/` 规划文档已归档到 `docs/archives/web_gui_init/upgrade/`。其中 UX-G0 / UI-UX Governance 仍可作为后续视觉治理输入，但它已经不是已经交付能力（如 settings / write confirm / search AI summary）的前置门槛。

## Bridge Phase Before Next-Phase Delivery

### UX-G0 / UI-UX Governance

**定位**：post-v1.4 closeout 与下一轮实现阶段之间的桥接治理层。

**为什么先做这一步**：
- Dashboard visual 线和基础 bugfix 线已完成，但它们解决的是“可交付”和“可用性”问题，不等于已经建立统一的长期 UI/UX 规则。
- 如果直接进入 LLM 或新 feature，现有页面风格、层级、反馈、runtime/operator 提示与未来新增页面之间仍可能继续漂移。
- 因此先做 UX-G0，可以把接下来的 UI 演进从“单点修补”切换到“有宪法的持续开发”。

**包含**：
1. UI/UX principles 与产品气质定义
2. 页面布局 / 卡片 / 表单 / 空状态 / feedback / runtime transparency 模式规范
3. 现有页面审计矩阵（dashboard / search / write / edit / journal / base/nav）
4. 样板页试点迁移顺序与 guardrails

**不包含**：
1. LLM 功能实现
2. 新 feature 扩张
3. 全站一次性重做
4. README 大改

**完成标志**：
- `docs/archives/web_gui_init/upgrade/ui-ux-governance-spec.md` 中的原则被吸收或重新固化
- `docs/archives/web_gui_init/upgrade/plan-ui-ux-governance.md` 中的审计/guardrail 产物被补齐
- 现有页面有审计结果与试点迁移顺序
- 后续 UI/UX 开发具备可执行 guardrails

## Recommended execution order

### Step 1 — 先做 UX-G0 / UI-UX Governance

**Reason:**
- 它是下一轮所有 UI 工作的治理前置层
- 可以先把现有页面与未来页面的设计边界、模式和 guardrails 定下来
- 能避免后续那年今日 / 模板增强 / LLM UI 再次各写各的

**Expected output:**
- `docs/archives/web_gui_init/upgrade/ui-ux-governance-spec.md`
- `docs/archives/web_gui_init/upgrade/plan-ui-ux-governance.md`
- 现有页面 audit matrix
- 样板页迁移顺序与 review checklist

### Step 2 — 再做“那年今日”计划

**Reason:**
- 与 Life Index 的核心叙事最一致
- 风险相对低
- 更接近读取/展示增强，而不是新的复杂编辑系统

**Expected output:**
- 单独 feature spec / implementation plan
- 明确入口（dashboard 或独立页）
- 明确数据来源与空状态

### Step 3 — 再做“写作模板增强”计划

**Reason:**
- 可作为现有 write 功能的增强项继续演进
- 但需要明确只做轻量增强，不要演化成模板管理后台

**Expected output:**
- 轻量模板增强范围说明
- 与现有 write service / template 的衔接方案

### Step 4 — 最后再判断“连续记录里程碑”是否值得进入实现

**Reason:**
- 它最容易改变产品气质
- 需要先澄清“鼓励记录”与“打卡驱动”之间的边界

**Expected output:**
- 产品边界结论
- 只有在结论清晰时才进入 spec / plan 阶段

## What can be batched together

### Batch A — 可以一口气完成

1. UX-G0 principles / patterns / guardrails 冻结
2. 现有页面 audit matrix
3. 样板页迁移顺序与 checklist

### Batch B — 可以一口气完成

1. 那年今日 feature prioritization
2. 那年今日 MVP scope 定义
3. 那年今日 spec / plan 文档起草

### Batch C — 不建议直接并入 A/B

1. 写作模板增强优先级确认
2. 模板增强 MVP / non-MVP 边界
3. 模板增强 spec / plan 文档起草

### Batch D — 不建议直接并入 A/B/C

1. 连续记录里程碑的产品边界讨论
2. 是否引入 streak-style feedback 的价值判断
3. 若确认值得做，再单独立项

## Recommended immediate next move

在当前文档收口完成后，最合理的下一步不是回到历史初始化计划，而是：

1. 判断是否要先执行一轮 **UI/UX 治理 / Celestial Editorial 迁移**
2. 然后再决定是进入某个新 feature（如那年今日 / 模板增强），还是继续做视觉治理

在 UX-G0 完成之后，可选的下一步是：

1. 只针对 **那年今日** 做新一轮 brainstorming / spec / plan
2. 完成后，再决定是否顺势把 **写作模板增强** 作为下一批一口气做完

## Anti-bloat reminder

下一阶段最需要避免的是：

1. 把多个新 feature 混成一个“大版本大杂烩”
2. 在没有产品边界澄清前就实现 streak/gamification
3. 把“写作模板增强”膨胀为复杂模板管理系统
