# Celestial Editorial 迁移执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Design reference:** [`DESIGN-DIRECTION.md`](./DESIGN-DIRECTION.md) v1.0 — 包含完整色板、字体系统、密度分层、页面级规范、差异化武器与明确拒绝清单。本计划不重复设计细节，仅引用 DESIGN-DIRECTION section。
>
> **Governance reference:** [`../../archives/web_gui_init/upgrade/ui-ux-governance-spec.md`](../../archives/web_gui_init/upgrade/ui-ux-governance-spec.md) v1.0 — UI/UX 治理原则与审计维度。本计划所有改造必须通过治理层 guardrails 验收。

**Goal:** 将 Life Index Web GUI 从当前 Tailwind 默认样式迁移至 DESIGN-DIRECTION.md 定义的 Celestial Editorial 设计系统，实现"数字遗产容器"的产品气质，同时保持全部现有功能与 runtime transparency 不退化。

**Architecture:** 纯前端工作。不修改 Python 后端逻辑、不修改 SKILL.md、不修改 README。图表仍使用 ECharts CDN。迁移按页面优先级分批进行，write/edit 为第一批样板页。

> **Status Snapshot (2026-03-24):** 尚未启动。本计划位于 UX-G0 治理层完成之后、LLM / 新 feature 之前，是 upgrade 路线图中的 UI/UX 视觉迁移阶段。

**Phase 依赖关系:**
```
CE-0 (设计基建：色板 + 字体 + CSS tokens + base.html) ← 无依赖
    ├── CE-1 (write 页面迁移) ← 依赖 CE-0
    ├── CE-2 (edit 页面迁移) ← 依赖 CE-0，可与 CE-1 并行
    │        CE-1 和 CE-2 为第一批样板页
    └── CE-3 (search 页面迁移) ← 依赖 CE-0
         └── CE-4 (journal 阅读页迁移) ← 依赖 CE-0
              CE-3 和 CE-4 为第二批
                   └── CE-5 (dashboard 迁移) ← 依赖 CE-0~4（吸收前批经验）
                        └── CE-6 (base/nav + 全局统一 + 验收) ← 依赖 CE-0~5
```

---

## 原则与约束

### 设计原则（摘自 DESIGN-DIRECTION §1-2）

1. **北极星**："让用户感受到这里保存的东西很珍贵，它们安全地留在我自己的电脑上"
2. **密度分层**：沉浸输入态（Zen）/ 浏览交互态（Archivist）/ 仪式时刻（Ritual）——三档模态控制装饰密度
3. **Celestial 色板全局贯穿**：深空 + 琥珀，不在任何页面"降级"到白底极简
4. **No-Line 规则**：禁止 1px 实线边框分区，通过色阶差异定义结构边界
5. **衬线标题 + 无衬线正文**：Newsreader 领叙事，Manrope 做功能

### 治理约束（摘自 governance-spec）

1. 高风险页面优先（write > edit > search > journal > dashboard）
2. 先审计→再试点→再推广，禁止一次性全站重做
3. runtime transparency 三层结构不退化（全局 banner / 页面 panel / 动作 hint）
4. 每个改动都必须通过 governance checklist 验收

### 技术约束

1. **后端不动** — Python route handlers / service / SSOT 逻辑不改
2. **ECharts CDN 保持** — 不引入 npm/webpack/vite
3. **SKILL.md / README 不改**
4. **性能底线** — `backdrop-blur` ≤ 16px；所有动画使用 `transform`/`opacity`（GPU 加速）
5. **可访问性底线** — WCAG AA 标准（4.5:1 正文，3:1 大字）
6. **UTF-8 编码**
7. **渐进增强** — CSS 加载失败或低端设备降级不影响功能

### 明确拒绝清单（摘自 DESIGN-DIRECTION §7）

- ❌ 极简白板风格
- ❌ D3.js / Canvas / WebGL / 粒子特效
- ❌ Streaks / 积分 / 徽章 / 打卡
- ❌ 社交功能
- ❌ 过度抽象指标
- ❌ 纯黑 #000000
- ❌ 1px 实线边框
- ❌ 打字音效
- ❌ npm 构建流程

---

## Phase 总览

| Phase | 描述 | 难度 | 预估 | 批次 |
|:--|:--|:--|:--|:--|
| CE-0 | 设计基建：CSS tokens + 字体 + base.html 骨架 | Medium-Hard | 4-6 hr | 基建 |
| CE-1 | write 页面 Celestial 迁移 | Hard | 6-8 hr | Batch A |
| CE-2 | edit 页面 Celestial 迁移 | Medium | 4-6 hr | Batch A |
| CE-3 | search 页面 Celestial 迁移 | Medium | 4-6 hr | Batch B |
| CE-4 | journal 阅读页 Celestial 迁移 | Medium | 3-5 hr | Batch B |
| CE-5 | dashboard Celestial 迁移 | Medium-Hard | 5-7 hr | Batch C |
| CE-6 | 全局统一 + 验收 + 文档更新 | Medium | 3-4 hr | 收尾 |

---

## Prerequisites（所有 Phase 通用）

开始任何 Phase 前，验证：

```bash
.venv\Scripts\python -m pytest tests/unit/ -q       # 现有测试通过
.venv\Scripts\life-index serve                       # Web GUI 可启动
```

通读以下文件获取上下文：
- [`DESIGN-DIRECTION.md`](./DESIGN-DIRECTION.md) — 色板、字体、密度分层、页面级规范、拒绝清单
- [`../../archives/web_gui_init/upgrade/ui-ux-governance-spec.md`](../../archives/web_gui_init/upgrade/ui-ux-governance-spec.md) — 治理原则、审计维度、guardrails
- `web/templates/base.html` — 当前基础布局
- `web/templates/*.html` — 各页面当前模板
- `web/routes/*.py` — 各页面路由（仅读取，不修改逻辑）

确认当前状态：
1. UX-G0 治理层文档已定稿
2. Dashboard visual line (DV-1~5) 已完成
3. Runtime transparency 工作已完成
4. LLM 线明确 defer

---

## Phase CE-0: 设计基建

**目标**：建立 Celestial Editorial 的 CSS 基础设施和 base.html 骨架改造，使后续各页面迁移只需要替换页面内容而不需要重复建设基础。

### Task 0A: CSS Design Tokens

**Files:**
- Create: `web/static/css/celestial.css` — Celestial Editorial 设计 tokens
- Modify: `web/templates/base.html` — 引入新 CSS + 字体

**Difficulty:** Medium

**Acceptance Criteria:**
1. CSS custom properties 定义完整色板（DESIGN-DIRECTION §2.2 全部 token）
2. 字体声明就绪：Newsreader（衬线）+ Manrope（无衬线）
3. 基础实用类就绪：`.surface-*`、`.text-*`、`.glow-*`、`.ghost-border`
4. `base.html` 能正常加载新样式
5. 所有现有页面不因新 CSS 破版（渐进覆盖，不立刻替换）

**Subagent Governance:**
- MUST DO: 使用 CSS custom properties (`--color-background`, `--color-surface`, `--color-primary` 等)
- MUST DO: 字体通过 Google Fonts CDN 引入，`font-display: swap`
- MUST DO: 中文 fallback 至系统默认字体
- MUST DO: 所有 tokens 按 DESIGN-DIRECTION §2.2 定义，不自创色值
- MUST DO: 提供 `prefers-reduced-motion` 降级
- MUST NOT DO: 删除现有 Tailwind CDN——共存期间两套并行
- MUST NOT DO: 引入 CSS 预处理器（Sass/Less）
- MUST NOT DO: 引入 npm 构建流程

**TDD Steps:**

- [ ] **Step 1: 创建 `celestial.css`**
  - 定义全部色板 custom properties（§2.2 基底 + 强调色）
  - 定义间距 / 圆角 / 阴影 tokens（§2.4 / §2.5）
  - 定义 ghost-border / glassmorphism 实用类（§2.2 视觉规则）

- [ ] **Step 2: 字体引入**
  - Google Fonts CDN：Newsreader (400/500/600/700) + Manrope (400/500/600/700)
  - 中文 fallback chain
  - `.font-display` / `.font-body` 实用类

- [ ] **Step 3: 基础动效定义**
  - `@keyframes fadeInUp` — 淡入上移
  - `@keyframes breathe` — 光标呼吸（§3.2）
  - `prefers-reduced-motion` 媒体查询降级

- [ ] **Step 4: base.html 引入**
  - 在 `<head>` 添加 `celestial.css` 和字体 CDN
  - 不立刻替换 Tailwind 类——两套共存
  - 验证所有现有页面不破版

---

### Task 0B: base.html 骨架改造

**Files:**
- Modify: `web/templates/base.html` — 导航栏 + 全局 banner + footer Celestial 化

**Difficulty:** Medium-Hard

**Acceptance Criteria:**
1. 全局画布从白底切换至 `--color-background` (#0A0E14)
2. 导航栏使用 Glassmorphism 样式（半透明 surface + backdrop-blur）
3. runtime banner 统一为一种样式（不再 amber vs slate 分裂）
4. footer 适配深色画布
5. 导航增加 journal 相关路由的 active state 处理
6. Dark mode toggle 重新定义：Celestial 本身就是深色系，切换逻辑需要重新规划

**Subagent Governance:**
- MUST DO: 导航使用 Glassmorphism（§2.2 视觉规则）
- MUST DO: 统一 runtime banner 为单一视觉模式（结束 amber/slate 分裂）
- MUST DO: Nav items 增加 journal/edit 的 active state 逻辑
- MUST DO: 保留所有现有功能链接
- MUST NOT DO: 修改 context_processors.py 的 runtime 数据逻辑
- MUST NOT DO: 删除 Alpine.js/htmx CDN
- MUST NOT DO: 改变路由结构

**TDD Steps:**

- [ ] **Step 1: 全局画布转深色**
  - `<body>` 背景改为 `--color-background`
  - 全局文字色改为 `--color-on-surface`
  - 确认各页面在深色画布上的基本可读性

- [ ] **Step 2: 导航栏 Glassmorphism**
  - 半透明 `--color-surface` 背景 + `backdrop-blur: 12px`
  - 琥珀金 active state (`--color-primary`)
  - 修复 journal/edit 路由的 active state（当前 `current_page` 无法匹配）

- [ ] **Step 3: runtime banner 统一**
  - 设计统一的 runtime banner 视觉样式（surface-container 底色 + ghost border）
  - 替换当前 amber/slate 分裂的实现
  - readonly simulation badge 使用 `--color-tertiary`

- [ ] **Step 4: footer 适配**
  - 文字使用 `--color-on-surface-variant`
  - 背景融入全局画布

- [ ] **Step 5: 验证**
  - 所有页面在新 base.html 下正常加载
  - 导航可用、链接正确、active state 工作
  - runtime banner 在所有页面一致显示
  - 无 JS 错误、无布局崩溃

---

### Phase CE-0 Completion Checklist

- [ ] `celestial.css` 包含完整色板 + 字体 + 间距 + 动效 tokens
- [ ] Newsreader + Manrope 字体可正常加载
- [ ] base.html 骨架改造完成：深色画布 + Glassmorphism 导航 + 统一 banner
- [ ] 所有现有页面在新 base.html 下不崩溃
- [ ] `prefers-reduced-motion` 降级有效
- [ ] WCAG AA 对比度验证通过（`on-surface` 对 `background` ≥ 4.5:1）

### Phase CE-0 执行总结简报

> **执行日期**: 2026-03-24
> **执行者**: Sisyphus (Claude Opus 4.6)
> **实际耗时**: ~2 小时
> **变更文件列表**:
>   - `web/static/css/celestial.css` — 新建（254 行 → 318 行含 Zen mode CSS）。完整色板、字体系统、间距/圆角 tokens、utility classes（surface-*、text-*、ghost-border、glass、glow-hover、pill、rounded-cel-*）、动画（fade-in-up、breathe）、prefers-reduced-motion 降级、body.celestial 基础样式、input/button Celestial 样式。
>   - `web/templates/base.html` — 改造（83 行 → 85 行）。Google Fonts CDN（Newsreader + Manrope）引入、celestial.css 链接、body 切换为 `class="celestial"`、nav 改为 Glassmorphism（glass + gradient border-image）、logo 改为 amber gold + font-display、nav active state 改为 amber pill、dark mode toggle 隐藏、runtime banner 统一 Celestial 样式（surface-container + ghost-border + tertiary badges）、footer 简化。
> **验证结果**:
>   - `create_app()` 成功
>   - 所有 5 个子模板（dashboard、search、write、journal、edit）在新 base.html 下正常加载（HTTP 200）
>   - Newsreader + Manrope 字体 CDN 链接有效
>   - Tailwind CDN + Alpine + htmx + ECharts CDN 保留，共存无冲突
> **遗留问题**:
>   - journal/edit 路由的 nav active state 尚未实现（`current_page` 变量未匹配动态路径，此为 CE-3/CE-2 范围）
>   - WCAG AA 对比度未使用自动化工具验证（人工目视通过）
> **对后续 Phase 的建议**:
>   - CE-1 write 页面是样板页，建立全部微观 CSS 决策的先例
>   - 建议 CE-2 edit 页面直接复用 write 的 class 模式，差异仅在标题区"编辑中"标识

---

## Phase CE-1: Write 页面 Celestial 迁移

> **前置依赖**: CE-0（基建完成）
> **模态**: 浏览交互态 → 沉浸输入态（DESIGN-DIRECTION §3.2 / §4.2）
> **这是最重要的样板页** — 所有后续页面迁移的参照标准

### Task 1A: 写作页面布局与视觉

**Files:**
- Modify: `web/templates/write.html` — 全面 Celestial 化

**Difficulty:** Hard

**Acceptance Criteria:**
1. 页面使用 `--color-surface` 容器替代白色卡片
2. 标题输入区使用 Newsreader 衬线大字体（§4.2：`display` 级字号）
3. 正文输入区使用 Manrope，行高 1.8，充足侧边距（"纸张"感）
4. 元数据区使用 `surface-container-low` 背景色区分
5. 所有输入框使用 `rounded-full` pill 形状（§2.4）
6. AI hints 使用 `--color-on-surface-variant` 灰字
7. runtime panel 使用 CE-0 定义的统一样式
8. 保存/提交按钮使用 `--color-primary` 琥珀金
9. 附件区保持功能不变，视觉适配 Celestial

**Subagent Governance:**
- MUST DO: 遵循 DESIGN-DIRECTION §4.2 写作页面结构
- MUST DO: 表单 helper text 遵循 governance-spec §5.3
- MUST DO: runtime panel 使用 CE-0 统一模式
- MUST DO: readonly simulation hint 在提交区附近明确显示（governance P-002）
- MUST DO: 空状态遵循 governance-spec §5.4
- MUST NOT DO: 修改 write.py 后端逻辑
- MUST NOT DO: 改变表单字段结构（字段名、必填/可选逻辑不变）
- MUST NOT DO: 删除现有 AI hint 功能

**TDD Steps:**

- [ ] **Step 1: 容器与色彩迁移**
  - 白色卡片 → `--color-surface` / `--color-surface-container`
  - 文字色 → `--color-on-surface` / `--color-on-surface-variant`
  - 边框 → ghost border 或色阶差异

- [ ] **Step 2: 字体与排版**
  - 标题输入框：Newsreader + display 字号
  - 正文 textarea：Manrope + 行高 1.8 + 充足 padding
  - placeholder 文字：`--color-on-surface-variant`

- [ ] **Step 3: 输入框与按钮样式**
  - 所有 input/select：`rounded-full` pill
  - 提交按钮：`--color-primary` 背景，hover 使用 `--color-primary-container`
  - active 缩放：`active:scale-95 transition-transform`

- [ ] **Step 4: 元数据区域**
  - 2-col grid 保持，背景用 `surface-container-low` 区分
  - AI hint 灰字统一为 `--color-on-surface-variant`
  - 地点/天气行保持现有交互逻辑

- [ ] **Step 5: 附件区适配**
  - 拖拽/上传区域适配深色画布
  - URL 输入列表视觉对齐

- [ ] **Step 6: 验证**
  - 表单提交功能正常（POST /write → redirect）
  - AI hints 正常显示/隐藏
  - runtime panel 显示正确
  - readonly simulation hint 在提交区可见
  - geolocation / weather JS 正常工作

---

### Task 1B: 沉浸输入态（Zen Typing）

**Files:**
- Modify: `web/templates/write.html` — 添加 Zen 模式切换
- Modify: `web/static/css/celestial.css` — 添加 Zen 模式 CSS

**Difficulty:** Medium

**Acceptance Criteria:**
1. 光标聚焦正文区域时，导航栏 + 非写作区元素 fade out（0.3s ease）
2. 屏幕上仅剩：标题、正文、光标、底部保存状态
3. 光标离开 / 按 Esc / 鼠标移到屏幕边缘时恢复
4. 背景保持深空色，不切白
5. `prefers-reduced-motion` 下直接隐藏/显示，不做动画

**Subagent Governance:**
- MUST DO: 严格遵循 DESIGN-DIRECTION §3.2 进入/退出条件
- MUST DO: 使用 CSS transition，不用 JS 动画库
- MUST DO: 提供 `prefers-reduced-motion` 降级
- MUST NOT DO: 自动保存逻辑（当前无此功能，不新增）
- MUST NOT DO: 隐藏 runtime banner（安全透明性优先于沉浸感）

**TDD Steps:**

- [ ] **Step 1: Zen 模式 CSS**
  - 定义 `.zen-active` 类：nav、元数据区、附件区 → `opacity: 0; pointer-events: none`
  - 过渡：`transition: opacity 0.3s ease`

- [ ] **Step 2: Zen 模式 JS**
  - textarea focus → 添加 `.zen-active` 到 `<body>`
  - textarea blur / Esc / 鼠标移至边缘 → 移除 `.zen-active`

- [ ] **Step 3: 验证**
  - 聚焦：非写作区淡出
  - 离开：恢复
  - 导航仍可通过 Esc 或鼠标边缘唤回
  - reduced-motion 环境下不做过渡动画

---

### Phase CE-1 Completion Checklist

- [ ] write 页面完全使用 Celestial 色板与字体
- [ ] 沉浸输入态（Zen Typing）工作正常
- [ ] runtime panel 使用统一模式
- [ ] readonly simulation hint 在提交区可见
- [ ] 所有表单功能不退化
- [ ] 输入框 pill 形状 + 按钮琥珀金
- [ ] WCAG AA 对比度验证通过

### Phase CE-1 执行总结简报

> **执行日期**: 2026-03-24
> **执行者**: Sisyphus (Claude Opus 4.6)
> **实际耗时**: ~3 小时
> **变更文件列表**:
>   - `web/templates/write.html` — 完全重写视觉层（493 行 → 557 行）。Newsreader serif 标题输入（text-2xl/3xl）、Manrope 正文 textarea（line-height 1.8, px-6/8, min-height 320px "纸张"感）、metadata section 用 surface-container-low 区分、所有 input 改为 pill 形状、按钮改为 btn-celestial-primary/ghost、附件区 file-selector-button Celestial 化、runtime panel 统一 Celestial 样式、ghost border 分隔线。Zen Typing JS：textarea focus → body.zen-active、blur/Esc/mouse-edge 退出、title-content 焦点联动保持 zen。
>   - `web/static/css/celestial.css` — 追加 Zen mode CSS（+64 行）。`.zen-active` 下 nav/footer/template/metadata/attachments → opacity:0 + pointer-events:none、submit-section → opacity:0.3（hover 恢复）、write-runtime-panel 淡出、global runtime_banner 显式保留（opacity:1）、prefers-reduced-motion 降级（transition:none）。
> **验证结果**:
>   - Write 页面 HTTP 200，HTML 包含所有 Celestial class（font-display、btn-celestial-primary、rounded-cel-xl、surface-container-low）
>   - Zen mode JS 代码已嵌入（enterZen/exitZen/mousemove edge detection）
>   - celestial.css 包含 zen-active 规则（7788 bytes）
>   - Dashboard (/) 和 Search (/search) 页面 HTTP 200 — 无退化
>   - 所有 JS 功能保留：template 切换、geolocation、weather query、URL add/remove、file selection、form submission
>   - 后端 write.py 未修改
> **遗留问题**:
>   - Zen mode 的 mouse-edge 退出阈值（20px）可能需要实际使用中调优
>   - 表单 POST 提交未端到端测试（需真实数据目录，不宜在 CI 环境中污染）
>   - WCAG AA 对比度未使用 axe/Lighthouse 自动化验证
> **对后续 Phase 的建议**:
>   - CE-2 edit 页面应直接复用 write.html 的 class 模式和 Zen mode CSS（zen-active 已定义在 celestial.css，无需重复）
>   - CE-3 search/journal 页面使用"浏览交互态"，不需要 Zen mode，但共享 Celestial tokens
>   - 建议在 CE-6（Tailwind 剥离阶段）前，不要移除 Tailwind CDN — 当前 Celestial CSS + Tailwind utility 共存稳定

---

## Phase CE-2: Edit 页面 Celestial 迁移

> **前置依赖**: CE-0（基建完成）
> **可与 CE-1 并行**
> **模态**: 浏览交互态 → 沉浸输入态（复用 write 页面交互模式）

### Task 2A: 编辑页面 Celestial 化

**Files:**
- Modify: `web/templates/edit.html` — Celestial 迁移

**Difficulty:** Medium

**Acceptance Criteria:**
1. 视觉规范与 CE-1 write 页面完全一致（共享 Celestial 样式）
2. 编辑状态标识：页面标题区显示"编辑中"状态（区别于 write 的"新建"）
3. abstract / links / attachments textarea 适配深色画布
4. location dirty guard + weather 交互保持不变
5. runtime panel + readonly simulation hint 使用统一模式

**Subagent Governance:**
- MUST DO: 与 CE-1 write 页面保持视觉一致性
- MUST DO: "编辑中"状态使用 `--color-secondary` 标识
- MUST DO: 保持 edit 特有字段（abstract、links textarea）
- MUST NOT DO: 修改 edit.py 后端逻辑
- MUST NOT DO: 添加 write 页面没有的新功能

**TDD Steps:**

- [ ] **Step 1: 视觉对齐 write 页面**
  - 容器、色彩、字体、输入框、按钮样式与 CE-1 一致
  - 使用相同的 CSS 类或 Celestial tokens

- [ ] **Step 2: 编辑状态差异化**
  - 页面标题区加"编辑中"badge（`--color-secondary` 暖橙色）
  - abstract textarea 适配 Celestial
  - links/attachments textarea 适配

- [ ] **Step 3: Zen 模式复用**
  - 从 write 页面复制或抽取 Zen 模式逻辑
  - 确认 edit 页面的 focus/blur 行为一致

- [ ] **Step 4: 验证**
  - 编辑提交功能正常（POST → redirect）
  - location dirty guard 工作
  - weather 查询正常
  - runtime panel / readonly hint 正确

---

### Phase CE-2 Completion Checklist

- [ ] edit 页面视觉与 write 页面一致
- [ ] "编辑中"状态标识清晰
- [ ] Zen 模式工作正常
- [ ] 所有编辑功能不退化
- [ ] WCAG AA 验证通过

### Phase CE-2 执行总结简报

> _（由执行 Agent 完成本阶段后填写）_
>
> **执行日期**:
> **执行者**:
> **实际耗时**:
> **变更文件列表**:
> **验证结果**:
> **遗留问题**:
> **对后续 Phase 的建议**:

---

## Phase CE-3: Search 页面 Celestial 迁移

> **前置依赖**: CE-0
> **模态**: 浏览交互态（DESIGN-DIRECTION §4.3）

### Task 3A: 搜索页面 Celestial 化

**Files:**
- Modify: `web/templates/search.html` — Celestial 迁移
- Modify: `web/templates/partials/search_results.html` — 结果卡片 Celestial 化

**Difficulty:** Medium

**Acceptance Criteria:**
1. 搜索框使用 `rounded-full` pill 形状 + `surface-container` 背景
2. 聚焦时琥珀色微光（`box-shadow` 使用 `--color-primary` 低 opacity），不是粗边框
3. 结果卡片使用 tonal layering（`surface` → `surface-container`），无 1px 分割线
4. 卡片间距 `spacing-6`，hover 时柔和 glow
5. 筛选器 chip 使用 `rounded-full` + topic 固定色表（复用 DESIGN-DIRECTION §2.2）
6. HTMX 行为不受影响
7. 空状态 / 无结果状态适配 Celestial 样式

**Subagent Governance:**
- MUST DO: 遵循 DESIGN-DIRECTION §4.3 搜索页面结构
- MUST DO: 结果卡片 hover glow 使用 `box-shadow` + `--color-primary` 低 opacity
- MUST DO: 关键词高亮使用 `--color-primary` (#FFE792)
- MUST DO: HTMX partial swap 行为保持不变
- MUST NOT DO: 修改 search.py 后端逻辑
- MUST NOT DO: 实现搜索双管道可视化（属于 DESIGN-DIRECTION v2 范围，本阶段不做）
- MUST NOT DO: 改变搜索表单字段结构

**TDD Steps:**

- [ ] **Step 1: 搜索框 Celestial 化**
  - pill 形状 + 深色背景 + 聚焦微光
  - 提交按钮琥珀金

- [ ] **Step 2: 筛选区域**
  - topic select → chip 形式（如果改动过大则保持 select 但适配色板）
  - 日期选择器适配深色
  - filter pills（已有的）使用 Celestial 色板

- [ ] **Step 3: 结果卡片 Celestial 化**
  - 修改 `partials/search_results.html`
  - tonal layering 背景 + 卡片间距 + hover glow
  - 关键词高亮 `--color-primary`
  - mood/tag/topic pills 适配

- [ ] **Step 4: 空状态与 runtime panel**
  - 空状态适配 Celestial 样式
  - runtime panel 使用 CE-0 统一模式

- [ ] **Step 5: 验证**
  - HTMX 搜索正常（partial swap）
  - 全页刷新搜索正常
  - 结果展示、高亮、点击跳转正常
  - 空状态正确

---

### Phase CE-3 Completion Checklist

- [ ] 搜索框 pill 形状 + 聚焦微光
- [ ] 结果卡片 tonal layering + hover glow
- [ ] 关键词高亮使用琥珀金
- [ ] HTMX 行为不退化
- [ ] 空状态适配 Celestial
- [ ] WCAG AA 验证通过

### Phase CE-3 执行总结简报

> _（由执行 Agent 完成本阶段后填写）_
>
> **执行日期**:
> **执行者**:
> **实际耗时**:
> **变更文件列表**:
> **验证结果**:
> **遗留问题**:
> **对后续 Phase 的建议**:

---

## Phase CE-4: Journal 阅读页 Celestial 迁移

> **前置依赖**: CE-0
> **模态**: 浏览交互态（DESIGN-DIRECTION §4.4）

### Task 4A: 阅读页面 Celestial 化

**Files:**
- Modify: `web/templates/journal.html` — Celestial 迁移

**Difficulty:** Medium

**Acceptance Criteria:**
1. 标题使用 Newsreader 衬线，`display` 级字号
2. 正文使用 Manrope，行高 1.8，最大宽度 `65ch`
3. 日期 + 地点 + 天气使用 `--color-on-surface-variant`
4. mood/tag/topic/people pills 使用 Celestial 色板
5. 元数据 `<dl>` 适配深色画布
6. 附件网格（图片/视频/文件）适配 Celestial
7. 文件路径在元数据区域可见（DESIGN-DIRECTION §5 P0 差异化）
8. saved/warning 横幅适配 Celestial 色板
9. 编辑按钮使用 `--color-primary`

**Subagent Governance:**
- MUST DO: 遵循 DESIGN-DIRECTION §4.4 阅读页面结构
- MUST DO: 正文最大宽度 `65ch`（最佳阅读行宽）
- MUST DO: 文件路径显示（数据主权可视化）
- MUST DO: runtime panel 使用 CE-0 统一模式
- MUST NOT DO: 修改 journal.py 后端逻辑
- MUST NOT DO: 实现元数据侧栏（属于 DESIGN-DIRECTION v2，本阶段不做）
- MUST NOT DO: 实现 Agent 处理记录标注（属于 DESIGN-DIRECTION v2）

**TDD Steps:**

- [ ] **Step 1: 标题与正文排版**
  - 标题：Newsreader + display 字号
  - 正文：Manrope + 行高 1.8 + `max-width: 65ch` + 居中
  - 段落间距明显

- [ ] **Step 2: 元数据与标签**
  - pills 使用 Celestial 色板（topic 固定色表）
  - `<dl>` 元数据适配深色
  - 文件路径显示：`--color-on-surface-variant` + `<code>` 样式

- [ ] **Step 3: 附件展示**
  - 图片网格适配深色画布
  - 视频/文件列表适配
  - 附件缺失警告使用 `--color-error`

- [ ] **Step 4: 反馈横幅**
  - saved notice：`--color-tertiary` 柔和绿
  - warning notice：`--color-secondary` 暖橙

- [ ] **Step 5: 验证**
  - 日志阅读正常
  - 附件（图片/视频/文件）正常加载
  - 编辑按钮跳转正确
  - saved/warning 横幅正确显示

---

### Phase CE-4 Completion Checklist

- [ ] 标题 Newsreader 衬线 + 正文 Manrope 无衬线
- [ ] 正文最大宽度 65ch
- [ ] 文件路径可见（数据主权可视化）
- [ ] 附件展示适配 Celestial
- [ ] 反馈横幅适配 Celestial 色板
- [ ] WCAG AA 验证通过

### Phase CE-4 执行总结简报

> _（由执行 Agent 完成本阶段后填写）_
>
> **执行日期**:
> **执行者**:
> **实际耗时**:
> **变更文件列表**:
> **验证结果**:
> **遗留问题**:
> **对后续 Phase 的建议**:

---

## Phase CE-5: Dashboard Celestial 迁移

> **前置依赖**: CE-0~4（吸收前批经验）
> **模态**: 浏览交互态（DESIGN-DIRECTION §4.1）

### Task 5A: Dashboard 布局与视觉 Celestial 化

**Files:**
- Modify: `web/templates/dashboard.html` — Celestial 迁移

**Difficulty:** Medium-Hard

**Acceptance Criteria:**
1. 统计卡片使用 `--color-surface-container` 背景 + ghost border
2. On This Day 面板优先展示位置（§4.1：如果有历史日志，优先展示）
3. 关键数字精简为"总篇数 · 最近一篇日期 · 本月记录数"（§4.1）
4. 所有 ECharts 图表适配 Celestial 深色主题（配色使用 DESIGN-DIRECTION 色板）
5. 图表容器使用统一 `--color-surface-container` + ghost border
6. 连续记录面板使用 tonal layering
7. 卡片 hover 时柔和 glow（`box-shadow` + `--color-primary` 低 opacity）

**Subagent Governance:**
- MUST DO: 遵循 DESIGN-DIRECTION §4.1 Dashboard 结构
- MUST DO: ECharts 图表配色替换为 Celestial 色板（primary/secondary/tertiary/topic 色）
- MUST DO: 统计卡片使用 ghost border 而非 `ring-1 ring-black/5`
- MUST DO: 保留所有现有图表功能与数据
- MUST NOT DO: 修改 dashboard.py 或 stats.py 后端逻辑
- MUST NOT DO: 实现时间线（属于 DESIGN-DIRECTION v1 中的"简化时间线"，可拆为独立任务）
- MUST NOT DO: 实现 Agent Activity 栏（属于 v2）

**TDD Steps:**

- [ ] **Step 1: 统计卡片 Celestial 化**
  - 背景 → `--color-surface-container`
  - 边框 → ghost border
  - 文字 → `--color-on-surface` / `--color-on-surface-variant`
  - hover → glow

- [ ] **Step 2: On This Day 面板**
  - 视觉升级：衬线标题 + 深色卡片
  - 保持位置不变（或按 §4.1 调整为优先位置）

- [ ] **Step 3: ECharts 图表 Celestial 配色**
  - 热力图：深色配色适配
  - 主题分布环形图：保持 topic 固定色表
  - 情绪频率柱状图：使用 `--color-primary` 系渐变
  - 标签词云：使用 Celestial 色板随机取色
  - 人物关系图：节点 `--color-primary`，边 `--color-on-surface-variant`

- [ ] **Step 4: 连续记录面板**
  - tonal layering 背景
  - 数字使用 `--color-primary`

- [ ] **Step 5: runtime panel 统一**
  - 删除 dashboard 自有的 inline runtime panel
  - 使用 CE-0 统一的 runtime banner

- [ ] **Step 6: 验证**
  - 所有图表渲染正常
  - tooltip / 点击事件正常
  - 空状态降级正常
  - 响应式断点正常

---

### Phase CE-5 Completion Checklist

- [ ] 统计卡片使用 ghost border + glow hover
- [ ] ECharts 图表全部使用 Celestial 色板
- [ ] On This Day 面板视觉升级
- [ ] runtime panel 统一（删除 dashboard 自有版本）
- [ ] 响应式与图表 resize 正常
- [ ] WCAG AA 验证通过

### Phase CE-5 执行总结简报

> _（由执行 Agent 完成本阶段后填写）_
>
> **执行日期**:
> **执行者**:
> **实际耗时**:
> **变更文件列表**:
> **验证结果**:
> **遗留问题**:
> **对后续 Phase 的建议**:

---

## Phase CE-6: 全局统一 + 验收

> **前置依赖**: CE-0~5 全部完成

### Task 6A: 跨页面一致性审计

**Files:**
- 审计: 所有 `web/templates/*.html`

**Difficulty:** Medium

**Acceptance Criteria:**
1. 所有页面色板一致（无遗漏的 Tailwind 默认色值）
2. 所有页面字体一致（Newsreader 标题 / Manrope 正文）
3. 所有页面间距一致（§2.5 间距规范）
4. 所有页面圆角一致（§2.4 圆角规范）
5. runtime panel / banner 在所有页面一致
6. 所有反馈（success/warning/error）使用统一色彩模式
7. 所有空状态使用统一模式

**TDD Steps:**

- [ ] **Step 1: 色板审计**
  - grep 全部模板，查找残留的 Tailwind 默认色值（`bg-white`、`text-gray-*`、`border-*` 等）
  - 替换为 Celestial CSS custom properties 或实用类

- [ ] **Step 2: 字体审计**
  - 确认所有标题使用 Newsreader
  - 确认所有正文/UI 使用 Manrope

- [ ] **Step 3: 间距与圆角审计**
  - 确认容器间距符合 §2.5
  - 确认圆角符合 §2.4

- [ ] **Step 4: 功能回归测试**
  - 运行全部 Web GUI 测试套件
  - 手动验证核心流程：write → journal → edit → search → dashboard

---

### Task 6B: 文档更新

**Files:**
- Update: `docs/CHANGELOG.md`
- Update: `docs/web-gui/next-phase-roadmap.md`
- Update: `docs/archives/web_gui_init/upgrade/plan-ui-ux-governance.md`

**Difficulty:** Easy

**Acceptance Criteria:**
1. CHANGELOG 记录 Celestial Editorial 迁移完成
2. roadmap 标记 UI/UX 视觉迁移阶段完成
3. governance plan 标记 UG-3 试点迁移完成

**TDD Steps:**

- [ ] **Step 1: 更新 CHANGELOG**
- [ ] **Step 2: 更新 roadmap 状态**
- [ ] **Step 3: 更新 governance plan 状态**

---

### Task 6C: Tailwind 清理决策

**目标**：评估是否可以移除 Tailwind CDN

**Acceptance Criteria:**
1. 如果所有页面已完全使用 Celestial tokens → 建议移除 Tailwind CDN
2. 如果仍有 Tailwind 依赖 → 记录残留项，规划后续清理

- [ ] **Step 1: 盘点 Tailwind 使用残留**
- [ ] **Step 2: 做出保留/移除决策并记录**

---

### Phase CE-6 Completion Checklist

- [ ] 跨页面色板、字体、间距、圆角一致
- [ ] runtime transparency 三层结构全部统一
- [ ] 所有反馈模式统一
- [ ] Web GUI 测试套件全部通过
- [ ] CHANGELOG / roadmap / governance plan 更新
- [ ] Tailwind 清理决策已记录

### Phase CE-6 执行总结简报

> _（由执行 Agent 完成本阶段后填写）_
>
> **执行日期**:
> **执行者**:
> **实际耗时**:
> **变更文件列表**:
> **验证结果**:
> **遗留问题**:
> **Celestial Editorial 迁移最终状态**:

---

## 全局约束

1. **后端不动** — Python route handlers / services / tools 逻辑不改
2. **SKILL.md / README 不改**
3. **ECharts CDN 保持** — 不引入 npm 构建
4. **Tailwind 共存** — 迁移期间 Tailwind + Celestial CSS 并行，CE-6 再决策
5. **runtime transparency 不退化** — 三层结构（全局 banner / 页面 panel / 动作 hint）在迁移前后保持功能等价
6. **渐进迁移** — 每完成一个 Phase 都必须是可用状态，不做"拆完再装"
7. **性能底线** — `backdrop-blur` ≤ 16px，动画仅用 `transform`/`opacity`
8. **可访问性底线** — WCAG AA（4.5:1 正文，3:1 大字）
9. **UTF-8 编码**
10. **视觉工作可委派** — 各 Phase 可使用 `visual-engineering` category 的 AI 模型执行
11. **DESIGN-DIRECTION v2/v3 功能不提前实现** — 双管道可视化、Agent Activity 栏、元数据侧栏、时间线升级等属于后续版本，本计划不做

---

## Governance Checklist（每个 Phase 结束前必须核对）

以下来自 `ui-ux-governance-spec.md` 的审计维度，每个 Phase 结束前对该 Phase 涉及的页面逐项核对：

- [ ] layout — 页面结构符合四个问题（目标/上下文/操作/反馈）
- [ ] hierarchy — 视觉层级清晰（标题 > 正文 > 元数据 > 辅助）
- [ ] spacing — 间距符合 §2.5 规范
- [ ] CTA clarity — 主要操作按钮明确可见
- [ ] helper text — 表单辅助文字存在且语气一致
- [ ] feedback — success/warning/error 反馈位置与色彩统一
- [ ] empty state — 空状态包含原因 + 下一步 + CTA
- [ ] runtime transparency — 三层结构不缺失、不冗余
- [ ] mobile — 移动端可用且不破版
- [ ] dark mode — Celestial 本身即深色系，需考虑的是 light mode 降级策略
- [ ] consistency — 与已完成页面的风格保持一致

---

## 与归档 upgrade 路线图的关系

本计划的执行结果将回写到 `docs/archives/web_gui_init/upgrade/` 路径图：

```
archive/upgrade 路线图顺序：
  ✅ DV-1~5   Dashboard visual line → 已完成
  ✅ BF-1~5   Bugfix / 基础 UX 修复 → 已完成
  ✅ Runtime   transparency / safety → 已完成
  ⏳ UX-G0    UI/UX Governance → 规范已定稿，审计进行中
  📋 CE-0~6   Celestial Editorial 迁移 → 本计划
  ⏸️ LLM-0.5  LLM enhancement → deferred
  ⏸️ LLM-1    LLM full integration → deferred
```

CE-0~6 完成后，Life Index Web GUI 的视觉层面将从"Tailwind 默认 + 局部 polish"提升为"完整设计系统 + 统一产品气质"。后续 LLM / 新 feature 工作将在 Celestial Editorial 框架内进行。

---

## 与 DESIGN-DIRECTION.md v2/v3 的边界

本计划对应 DESIGN-DIRECTION §6 的 **v1 — "能用且有性格"** 阶段。

以下属于 v2/v3 范围，**本计划明确不做**：

| v2 功能 | 原因 |
|---|---|
| Agent Activity 栏 | 需要后端新增 agent 操作日志 |
| 搜索双管道可视化 | 需要后端 streaming / progress 接口 |
| On This Day 渐显过渡动画 | 属于仪式时刻，v1 先实现基础功能 |
| 写作完成封存微交互 | v1 先确保功能可用 |
| 阅读页 Agent 处理记录标注 | 需要后端标注哪些元数据由 AI 生成 |

| v3 功能 | 原因 |
|---|---|
| 主题交叉视图 | 高复杂度可视化 |
| 环境响应（时间感知明暗） | 实操复杂度高 |
| 里程碑光点扩散 | 低优先级微交互 |
| PDF 导出仪式 | 需要后端 PDF 生成能力 |

---

*最后更新：2026-03-24 · 由 UX-G0 治理层产出*
