# Celestial Editorial 迁移 — CE-5 + CE-6 收尾 Prompt

> **用法**：CE-0~4 全部完成后，用本 prompt 开新 session 执行 Dashboard 迁移和全局统一。
> **推荐执行者**：Claude Opus / Sonnet（Dashboard 有 ECharts 配色需要审美判断）。

---

## 你的角色

你正在完成 Celestial Editorial 迁移的最后两个阶段。write / edit / search / journal 四个页面已完成迁移。你要把 Dashboard 迁移到 Celestial，然后做全局一致性审计和收尾。

## 你必须先读的文件

1. `docs/web-gui/UIUX/DESIGN-DIRECTION.md` — 设计方向权威文档（重点看 §4.1 Dashboard 规范）
2. `docs/web-gui/UIUX/plan-celestial-editorial-migration.md` — CE-5 和 CE-6 章节
3. `web/static/css/celestial.css` — design tokens
4. `web/templates/write.html` — 样板页（视觉一致性锚点）
5. `web/templates/dashboard.html` — 当前 Dashboard（你的改造对象）

## CE-5 关键提醒

1. ECharts 图表配色替换为 Celestial 色板——这是审美判断最密集的部分
2. 热力图用深空色阶（#0A0E14 → #1A1E28 → #FFE792 渐变），不用默认绿色
3. 主题分布环形图保持 topic 固定色表
4. 情绪柱状图用 `--color-primary` 系
5. 标签词云用 Celestial 色板随机取色
6. 所有统计卡片用 ghost border + hover glow，不用 `ring-1 ring-black/5`
7. On This Day 面板用 Newsreader 衬线标题

## CE-6 关键提醒

1. grep 所有模板，查找残留的 Tailwind 默认色值（`bg-white`、`text-gray-*`、`border-*`）
2. 确认所有页面字体、间距、圆角一致
3. 运行 Web GUI 测试套件
4. 做 Tailwind CDN 保留/移除决策
5. 更新 CHANGELOG 和 roadmap

## 完成后

填写 CE-5 和 CE-6 的执行总结简报。CE-6 的简报即为整个 Celestial Editorial 迁移的最终报告。

---

*模板生成者：Opus 4.6 · 2026-03-24*
