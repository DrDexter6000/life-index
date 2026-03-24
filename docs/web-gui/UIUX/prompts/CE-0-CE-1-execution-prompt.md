# Celestial Editorial 迁移 — CE-0 + CE-1 执行 Prompt

> **用法**：将本文件全文复制到新 session 的第一条消息中发送给 Agent。
> **推荐执行者**：Claude Opus / Sonnet（visual-engineering 能力），**不推荐 GPT 5.4**。
> **预估工作量**：CE-0 约 4-6 小时，CE-1 约 6-8 小时。

---

## 你的角色

你是一位高级前端工程师 + UI/UX 实现专家。你即将把 Life Index Web GUI 从 Tailwind 默认白底主题迁移到 **Celestial Editorial** 设计系统。

**这不是"换个暗色主题"**。Celestial Editorial 是一个有灵魂的设计语言——它把一个私人日志工具包装成"数字遗产容器"，用深空的安静和琥珀的温暖传递"这里保存的东西很珍贵"的感受。你做的每一个微观 CSS 决定（阴影扩散半径、透明度值、过渡曲线）都要服务于这个感受。

## 你必须先读的文件

**按顺序读，不要跳过任何一个**：

1. `docs/web-gui/UIUX/DESIGN-DIRECTION.md` — **设计方向权威文档**，包含完整色板、字体系统、密度分层、页面级规范、差异化武器和明确拒绝清单。这是你的设计圣经。
2. `docs/web-gui/UIUX/plan-celestial-editorial-migration.md` — **执行计划**，包含 CE-0 和 CE-1 的详细 TDD Steps、Acceptance Criteria 和 Governance Checklist。这是你的工程规格。
3. `docs/archives/web_gui_init/upgrade/ui-ux-governance-spec.md` — **治理规范**，审计维度和 guardrails。
4. `web/templates/base.html` — 当前基础布局（83行，Tailwind CDN + Alpine + htmx + ECharts CDN）
5. `web/static/css/app.css` — 当前自定义 CSS（27行，仅 fadeInUp 动画）
6. `web/templates/write.html` — 写作页面当前模板（CE-1 改造对象）

## 设计审美锚点（关键）

这些是你做微观决定时的参照标准。**如果你不确定，偏向"更有仪式感"而非"更安全"**。

### 色彩感觉
- 画布是 **深邃的青黑色** (#0A0E14)，不是纯黑 #000000。它像午夜的天空，有微微的蓝调。
- 容器层级通过 **微妙的色阶差异** 区分（#12161E → #1A1E28 → #1E2330 → #232836），像水面下的不同深度。
- 琥珀金 (#FFE792) 是 **温暖的光源**——台灯、烛光的感觉，不是霓虹灯或舞台灯光。它出现在：按钮、高亮、hover glow、光标呼吸、活跃标签。用法克制但坚定。
- 所有"灰色"都带有色调倾向——青色（surface 系列）或暖色（text 系列）。**禁止纯灰 #808080**。

### 边界与形状
- **No-Line 规则**：绝不用 1px 实线边框做分区。结构通过色阶差异自然呈现。
- 如果容器确实需要定义，用 Ghost Border：`outline: 1px solid rgba(68, 72, 79, 0.15)`
- 所有交互元素（按钮、chip、toggle）使用 `rounded-full` (9999px)——药丸形状。
- 所有卡片和容器使用 `rounded-xl` (1.5rem) 到 `rounded-2xl` (2rem)。
- **禁止 `rounded-none` 和 `rounded-sm`**。一切保持柔和有机。

### 字体节奏
- **标题用衬线领叙事**：Newsreader（Google Fonts）— 给人信纸、日记本的手写温度。
- **正文用无衬线做功能**：Manrope（Google Fonts）— 清晰、现代、技术感。
- 这个节奏不可打破：Display/Headlines = Newsreader，Body/Labels/UI = Manrope。
- 标题和正文之间保持高对比度字号差（display: 2.5-3.5rem vs body: 1rem）。

### 动效纪律
- 所有动画只用 `transform` 和 `opacity`（GPU 加速），绝不动画 `width`/`height`/`margin`。
- `backdrop-blur` 不超过 16px。
- 过渡时长 0.2-0.3s，缓动 `ease` 或 `ease-out`。
- 仪式时刻动画总时长不超过 1.5s。
- 提供 `prefers-reduced-motion` 降级。

### hover / glow 的正确做法
```css
/* ✅ 正确：柔和的琥珀微光扩散 */
.card:hover {
  box-shadow: 0 0 20px rgba(255, 231, 146, 0.08), 0 0 40px rgba(255, 231, 146, 0.04);
  transition: box-shadow 0.3s ease;
}

/* ❌ 错误：粗暴的边框或弹跳 */
.card:hover {
  border: 2px solid #FFE792;
  transform: scale(1.05);
}
```

### Glassmorphism 的正确做法
```css
/* ✅ 正确：半透明 surface + 适度模糊 */
.glass-nav {
  background: rgba(18, 22, 30, 0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

/* ❌ 错误：极端模糊或完全透明 */
.glass-nav {
  background: transparent;
  backdrop-filter: blur(40px);
}
```

## 执行步骤

### Phase CE-0：设计基建

严格按照 `plan-celestial-editorial-migration.md` 的 CE-0 章节执行 Task 0A 和 Task 0B。

**关键提醒**：
1. 创建 `web/static/css/celestial.css`，不要修改 `app.css`（后者保留）
2. 在 `base.html` 的 `<head>` 中引入 celestial.css 和 Google Fonts CDN（Newsreader + Manrope）
3. **Tailwind CDN 不删除**——两套并存。Celestial CSS 通过 custom properties 和实用类逐步替代 Tailwind 类
4. `<body>` 背景从 `bg-gray-50 dark:bg-gray-900` 改为 `--color-background`
5. 导航栏改为 Glassmorphism（半透明 surface + backdrop-blur: 12px）
6. 导航 active state 从 indigo 改为 `--color-primary` 琥珀金
7. Dark mode toggle 行为需要重新考虑——Celestial 本身就是深色系，toggle 可以先隐藏或改为"原始模式/Celestial 模式"切换
8. runtime banner 统一为一种样式：`--color-surface-container` 底色 + ghost border，不再分 amber/slate
9. 完成后验证：**所有 6 个页面在新 base.html 下不崩溃**

### Phase CE-1：Write 页面 Celestial 迁移

严格按照 `plan-celestial-editorial-migration.md` 的 CE-1 章节执行 Task 1A 和 Task 1B。

**关键提醒**：
1. 这是**样板页**——所有后续页面迁移都以此为参照，所以要做到最好
2. 标题输入区：Newsreader 衬线，巨大字号（2rem+），placeholder "给这篇记录起个名字..."
3. 正文 textarea：Manrope，行高 1.8，充足侧边距（左右 padding 2-3rem），创造"纸张"感
4. 元数据区：用 `surface-container-low` 背景色与正文区区分，AI hint 灰字统一用 `--color-on-surface-variant`
5. 所有 input/select：`rounded-full` pill 形状
6. 提交按钮：`--color-primary` 琥珀金背景，hover 用 `--color-primary-container`
7. Zen Typing 沉浸模式：光标聚焦 textarea 时，nav + 元数据区 + 附件区 fade out (0.3s ease)，仅留标题+正文+光标+保存状态
8. **不要隐藏 runtime banner**（安全透明性优先于沉浸感）
9. **不修改 write.py 后端逻辑**，只改 HTML/CSS/JS

## 验收标准

每个 Phase 完成后，对照 `plan-celestial-editorial-migration.md` 中的 Completion Checklist 和 Governance Checklist 逐项验证。

最终效果应该让人感受到：
> **"这不是一个暗色主题的日记工具，这是一个在深空中用琥珀光保存人生的档案馆。"**

如果你做出来的效果让人想到"GitHub Dark Mode"或"VS Code Dark Theme"，那就做错了。Celestial Editorial 的正确联想是：午夜的图书馆、烛光下的信纸、星空下的安静时刻。

## 完成后

填写 `plan-celestial-editorial-migration.md` 中 CE-0 和 CE-1 的"执行总结简报"模板。列出所有变更文件、验证结果和遗留问题。

---

*生成者：Opus 4.6 (Product Director session) · 2026-03-24*
