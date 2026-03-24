# Celestial Editorial 迁移 — CE-2/3/4 执行 Prompt 模板

> **用法**：CE-0 + CE-1 完成后，用本 prompt 开新 session 执行后续批次。
> **推荐执行者**：Claude Opus / Sonnet，也可用 GPT 5.4（此时已有 CE-1 样板页作为视觉锚点）。

---

## 你的角色

你正在继续 Celestial Editorial 迁移。CE-0（设计基建）和 CE-1（write 样板页）已完成。你要把剩余页面迁移到 Celestial 设计系统。

## 你必须先读的文件

1. `docs/web-gui/UIUX/DESIGN-DIRECTION.md` — 设计方向权威文档
2. `docs/web-gui/UIUX/plan-celestial-editorial-migration.md` — 执行计划（找到你要执行的 Phase）
3. `web/static/css/celestial.css` — CE-0 已建立的 design tokens（**这是你的视觉锚点**）
4. `web/templates/base.html` — CE-0 已改造的基础布局
5. `web/templates/write.html` — **CE-1 样板页**（你的所有视觉决定必须与此页面一致）

## 核心规则

1. **视觉一致性**：你的每一个 CSS 决定都必须与 `write.html`（样板页）保持一致。有疑问时，打开 write 页面对照。
2. **No-Line 规则**：不用 1px 实线边框。用色阶差异或 ghost border。
3. **字体节奏**：标题 = Newsreader 衬线，正文/UI = Manrope 无衬线。
4. **圆角**：交互元素 `rounded-full`，容器 `rounded-xl` 到 `rounded-2xl`。
5. **后端不动**：只改 HTML/CSS/JS，不改 Python 文件。
6. **Tailwind 共存**：逐步替换 Tailwind 类，不删除 CDN。

## 执行

按 `plan-celestial-editorial-migration.md` 中对应 Phase 的 TDD Steps 逐步执行。完成后填写该 Phase 的执行总结简报。

## 你要执行的 Phase

> **[在此填写要执行的 Phase 编号，例如：CE-2 + CE-3]**

---

*模板生成者：Opus 4.6 · 2026-03-24*
