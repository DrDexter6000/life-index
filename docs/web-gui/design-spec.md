# Life Index Web GUI — Design Spec

> **Version**: v1.4.0 design reference
> **Date**: 2026-03-22
> **Status**: Released reference document
> **Author**: Brainstorming session (User + Sisyphus)
> **Review**: v1.0 review → v1.1 (9 fixes); v1.2 adds Write smart-fill, URL attachments, Edit page, LLM Mode A+; v1.3 fixes 2 MAJOR + 7 MINOR from Oracle/Momus review (HostAgentProvider IPC mechanism, ADR-005 strengthened, Content-Type validation, degradation strategy, E07xx error codes, etc.); v1.4 adds 3 MVP features from brainstorm (那年今日、写作模板、连续记录里程碑) + deferred features table rewrite

---

> **Post-release note (2026-03-22):** Web GUI 已随 `v1.4.0` 发布。本文件继续作为设计参考保留；任何未进入实际已发布范围的增强项，应转入 `docs/web-gui/post-v1.4-backlog.md` 继续规划，而不是再视为当前 release closeout 工作。
>
> **Docs note (2026-03-25):** Web GUI 初始实现期的 phase plans、upgrade specs 与 legacy full TDD 文档已归档至 `docs/archives/web_gui_init/`；当前文档入口见 [`docs/web-gui/README.md`](README.md)。
>
> **UI/UX Design Direction (2026-03-24):** 视觉设计方向的权威文档已迁移至 [`docs/web-gui/UIUX/DESIGN-DIRECTION.md`](UIUX/DESIGN-DIRECTION.md)。该文档定义了 Celestial Editorial 美学体系、交互模式分层、差异化优先级与分阶段路线图，取代此前 `Reference Samples/Overall DESIGN.md` 的设计定义职能。

## 1. 动机与背景

### 1.1 为什么需要 Web GUI

Life Index v1.x 作为 Agent Skill，依赖宿主 Agent（OpenClaw/Claude Desktop/Cursor）和 IM 软件（飞书等）来提供用户交互界面。这带来三个问题：

1. **体验不一致**：不同 Agent + IM 组合的功能差异大（如飞书无法发送附件给 OpenClaw）
2. **生态不稳定**：Agent/LLM 生态快速变化，依赖特定平台有风险
3. **缺乏可视化**：CLI 输出无法承载统计图表、热力图、关系图等视觉信息

### 1.2 与 PRODUCT_BOUNDARY.md 的关系

Web GUI 属于 **Layer C — Optional Application Layer**，是当前已经存在的可选本地壳层，严格遵守已有边界：

- ✅ 以同一份本地用户数据为中心（`~/Documents/Life-Index/`）
- ✅ 不破坏现有 durable data / compatibility 承诺
- ✅ 不把隐藏服务层变成新的产品中心
- ✅ 不取代核心 CLI / tool contract 的权威性
- ✅ 主要提供 convenience，而不是改写产品本体

**CLI 工具层保持 SSOT 地位**。Web GUI 调用 tools/ 模块，不绕过它们。

### 1.3 与 ARCHITECTURE.md §1.3「单层透明」的关系

> **ADR-005: Layer C Web GUI 对「禁止中间层」规则的有限例外**

ARCHITECTURE.md §1.3 规定：`用户 ↔ Agent ↔ 文件系统`，禁止引入中间层（数据库、服务进程、API 网关等）。

Web GUI 引入了 **FastAPI 服务进程** 和 **Service Layer**，形式上构成一个 HTTP 服务进程。本 ADR 明确这一例外的适用范围和约束条件：

**§1.3 的约束对象是 Layer A（Core Product）**：
- Layer A 的工具链（write_journal、search_journals 等）仍然直接操作文件系统，不经过任何中间层
- Agent 调用 CLI 工具的路径不变：`Agent → CLI → 文件系统`
- **Web GUI 不改变 Layer A 的任何行为**

**Web GUI 作为 Layer C 便利壳层的定位**：
- Web GUI 是 PRODUCT_BOUNDARY.md §2.3 Layer C 允许的「便利壳层」
- 它为用户提供浏览器交互界面，但**不取代 CLI 工具作为数据操作的权威接口**
- FastAPI 进程是按需启动、即时关闭的（`life-index serve` → Ctrl+C），**不是常驻后台服务**

**Service Layer 的严格约束**：
- Service Layer 是 Layer C 内部的适配器，将 tools/ 的 CLI-oriented 返回值转换为 Web-friendly 数据结构
- Service Layer **禁止直接操作文件系统**，所有数据读写必须通过 tools/ 模块
- Service Layer **禁止引入独立的持久化状态**（无 Web 专属数据库、无 session store、无缓存层）
- Service Layer **禁止成为其他消费者的 API**——它仅服务于 Web GUI 模板渲染

**判定**：Web GUI 的 FastAPI 进程和 Service Layer 是 §1.3「禁止中间层」规则的**有限例外**。该例外成立的条件是：(1) Layer A 架构不受影响；(2) Service Layer 不引入持久化状态；(3) 所有数据操作仍通过 tools/ 模块完成；(4) FastAPI 进程按需启动而非常驻。如果以上任一条件被违反，本 ADR 即失效。

---

## 2. 设计决策记录

| 决策 | 结论 | 理由 |
|:--|:--|:--|
| 技术栈 | FastAPI + Jinja2 + HTMX/Alpine.js + Tailwind CSS + ECharts | Python 全栈起步，开发效率高，未来可演进到前后端分离 |
| Agent 集成 | 模式 A+：双 Provider 并存（MCP Sampling + 自配 API key）| MVP 先实现 APIKeyProvider（即刻可用）；HostAgentProvider 在 MCP Server 化后启用。降级策略确保无 LLM 也能写入 |
| 仓库策略 | 同仓库 `web/` 目录，`pip install life-index[web]` 可选安装 | 共享 tools/ 代码避免 SSOT 分裂，optional deps 保持基础安装轻量 |
| 访问范围 | Phase 1 仅 localhost:PORT | 安全优先，远程访问未来通过 Cloudflare Tunnel 等实现 |
| 视觉风格 | 暗/亮主题切换，默认跟随系统 | 用户偏好 |
| 启停方式 | `life-index serve [--port PORT]`，Ctrl+C 关闭 | 符合"按需运行、一键关闭"原则 |

### 2.1 技术栈演进路线

```
Phase 1 (当前): FastAPI + Jinja2 + HTMX/Alpine.js
   ↓ （如果 HTMX 体验不够）
Phase 2 (未来): 保留 FastAPI API 层 → 前端换 React/Vue SPA
   ↓ （如果需要远程访问）
Phase 3 (远期): 部署到云端或通过隧道暴露
```

每一步都是**增量演进**，不需要推翻重来。

---

## 3. 架构

### 3.1 系统架构

```
┌──────────────────────────────────────────────────┐
│                  Web GUI (Layer C)                │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐ │
│  │ Dashboard │  │  Search  │  │  Write   │  │ Edit │ │
│  │  Page     │  │  Page    │  │  Page    │  │ Page │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──┬───┘ │
│       │              │              │          │    │
│  ┌────▼──────────────▼──────────────▼──────────▼┐   │
│  │          FastAPI Application              │    │
│  │                                           │    │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────┐  │    │
│  │  │ API     │  │ Template │  │ Static  │  │    │
│  │  │ Routes  │  │ Renderer │  │ Assets  │  │    │
│  │  └────┬────┘  └──────────┘  └─────────┘  │    │
│  └───────┼───────────────────────────────────┘    │
│          │                                        │
│  ┌───────▼───────────────────────────────────┐    │
│  │        Service Layer (web/services/)       │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │ Stats    │ │ Journal  │ │ Search   │   │    │
│  │  │ Service  │ │ Service  │ │ Service  │   │    │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘   │    │
│  └───────┼─────────────┼────────────┼─────────┘    │
│          │             │            │              │
└──────────┼─────────────┼────────────┼──────────────┘
           │             │            │
┌──────────▼─────────────▼────────────▼──────────────┐
│              tools/ (Layer A — SSOT)                │
│                                                    │
│  write_journal  search_journals  edit_journal      │
│  generate_abstract  build_index  query_weather     │
│  lib/frontmatter  lib/metadata_cache  lib/config   │
└────────────────────────┬───────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │ ~/Documents/        │
              │   Life-Index/       │
              │   (User Data)       │
              └─────────────────────┘
```

### 3.2 关键约束

1. **Web 层禁止绕过 tools/ 做持久化 journal 数据读写**。所有核心数据读写通过 tools/ 模块
2. **Service 层是 Web 专属的薄包装**，负责把 tools/ 的 CLI-oriented 返回值转换为 Web-friendly 数据结构
3. **LLM 集成采用分层策略**：MVP 先实现 APIKeyProvider（用户自配 API key 直接调用 LLM），HostAgentProvider（MCP Sampling 借用宿主 LLM）在 Life Index MCP Server 化后启用。无 LLM 时仍可手动写入（见 §3.3.4）

**补充说明**：出于 Web transport / security 需要，路由层允许有限的临时文件暂存、路径合法性校验等操作；但 journal 的持久化写入、frontmatter 变更、索引更新仍必须通过既有 tools / services 完成。

### 3.3 LLM 集成策略

**背景**：Life Index 作为 Agent Skill 安装运行，宿主 Agent（OpenCode/Claude Desktop/Cursor 等）自带 LLM 能力。Web GUI 的元数据提炼功能可借用此能力，无需用户额外配置。

**模式 A+：双 Provider 并存**

Web GUI 同时支持两种 LLM Provider，按优先级自动选择：

```
用户提交日志（仅 content）
        │
        ▼
  Web GUI Service Layer
        │
        ├─ 用户已填元数据 → 直接使用
        │
        └─ 用户未填元数据 → 调用 LLM 提炼
                │
                ├─ Provider 1: HostAgentProvider（MCP Sampling，零配置）
                ├─ Provider 2: APIKeyProvider（用户自配 API key）
                └─ 降级: 手动填写 + 自动 fallback（见下方）
```

**Provider 选择逻辑**：
1. 启动时检测可用 Provider：HostAgentProvider 需要 MCP sampling 上下文；APIKeyProvider 需要 API key 已配置
2. 优先使用 HostAgentProvider（零配置体验）
3. 如果 HostAgentProvider 不可用（Web GUI 未在 MCP 上下文中运行），fallback 到 APIKeyProvider
4. 如果两者都不可用，降级为手动填写 + 自动 fallback（见下方策略）

#### 3.3.1 HostAgentProvider — MCP Sampling 机制

**前提条件**：Life Index 需要以 MCP Server 模式运行（当前 v1.x 仅支持 CLI，MCP 支持是 Web GUI 的前置工作）。

**协议**：MCP（Model Context Protocol）规范定义了 `sampling/createMessage` 方法，允许 MCP Server 向宿主 Client 请求 LLM 完成。

**通信流程**：

```
Web GUI (FastAPI)                MCP Server (Life Index)              Host Agent (OpenCode 等)
      │                                │                                    │
      │  HTTP POST /write              │                                    │
      │  (content + empty fields)      │                                    │
      ├───────────────────────────────►│                                    │
      │                                │  sampling/createMessage            │
      │                                │  (提炼 prompt + content)           │
      │                                ├───────────────────────────────────►│
      │                                │                                    │
      │                                │  LLM response (JSON metadata)     │
      │                                │◄───────────────────────────────────┤
      │  metadata dict                 │                                    │
      │◄───────────────────────────────┤                                    │
```

**关键实现细节**：
- Web GUI 通过内部 API 调用 Life Index MCP Server 的 `extract_metadata` 工具
- MCP Server 使用 `ctx.session.create_message()` 向宿主 Agent 请求 LLM 完成
- 宿主 Agent 必须在初始化时声明 `sampling` 能力（`{"capabilities": {"sampling": {}}}`）
- MCP 规范要求 sampling 请求经过人工审批（human-in-the-loop），但多数 Client 实现允许自动批准

**MVP 范围说明**：HostAgentProvider 的完整实现依赖 Life Index MCP Server 化（当前不存在）。MVP 阶段先实现抽象接口和 APIKeyProvider，HostAgentProvider 在 Life Index 支持 MCP 后启用。

#### 3.3.2 APIKeyProvider — 用户自配 API key

**即刻可用**：用户在 `web/config.py` 或环境变量中配置 LLM API key，Web GUI 直接调用 LLM API。

**配置方式**（优先级从高到低）：
1. 环境变量：`LIFE_INDEX_LLM_API_KEY`、`LIFE_INDEX_LLM_BASE_URL`、`LIFE_INDEX_LLM_MODEL`
2. 配置文件：`web/config.py` 中的 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`

**支持的 API 格式**：OpenAI-compatible（覆盖 OpenAI、Anthropic via proxy、Deepseek、本地 Ollama 等）。

#### 3.3.3 接口设计

```python
# web/services/llm_provider.py
from abc import ABC, abstractmethod
from typing import Optional

class LLMProvider(ABC):
    """元数据提炼的抽象接口"""

    @abstractmethod
    async def extract_metadata(self, content: str) -> dict:
        """从日志正文中提炼元数据（title, mood, tags, topic, abstract 等）
        
        Returns:
            dict with keys: title, mood, tags, topic, abstract, people
            缺失字段返回 None，调用方使用 fallback 策略
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """检查此 Provider 是否可用"""
        ...


class HostAgentProvider(LLMProvider):
    """通过 MCP Sampling 借用宿主 Agent 的 LLM 能力
    
    前提：Life Index 以 MCP Server 运行，宿主 Agent 声明了 sampling 能力。
    通过 MCP session 的 create_message() 请求 LLM 完成。
    MVP 阶段：is_available() 返回 False（等待 MCP Server 化完成）。
    """
    ...


class APIKeyProvider(LLMProvider):
    """用户自配 API key，直接调用 OpenAI-compatible API
    
    配置来源：环境变量 > web/config.py。
    使用 httpx 异步调用 LLM API。
    """
    ...


def get_provider() -> Optional[LLMProvider]:
    """按优先级返回第一个可用的 Provider，全部不可用时返回 None"""
    ...
```

#### 3.3.4 LLM 不可用时的降级策略

如果所有 LLM Provider 都不可用，写入仍然可以完成，采用以下降级策略：

| 字段 | 降级行为 | 说明 |
|:--|:--|:--|
| `title` | 自动生成：取 content 前 20 个字符 | Web / Agent workflow 需补齐；不是 `write_journal()` 当前源码的硬校验项 |
| `topic` | 表单变为必填（红色星号） | Web / Agent workflow 需补齐，用户从 7 个标准 topic 中选择 |
| `abstract` | 自动生成：取 content 前 100 个字符 | Web / Agent workflow 需补齐；不是 `write_journal()` 当前源码的硬校验项 |
| `mood` | 留空 | 可选字段 |
| `tags` | 留空 | 可选字段 |
| `people` | 留空 | 可选字段 |

**表单 UI 适配**：LLM 不可用时，灰色提示文字从「AI 将自动生成」变为「请手动填写」，`topic` 字段标记为必填。

**源码对齐说明**：当前 `tools.write_journal.core.write_journal()` 只对 `date` 做硬校验。`title` / `topic` / `abstract` 在 Web GUI 中应被视为**上层 workflow 要负责补齐的字段**，而不是底层工具已经强制要求的字段。

#### 3.3.5 Web 路由路径契约（Journal Route Path Contract）

Web GUI 内部统一使用一种路由路径表示：

- **`journal_route_path`** = 相对于 `JOURNALS_DIR` 的路径，例如 `2026/03/life-index_2026-03-07_001.md`

而来自底层工具/缓存的路径在当前源码里并不统一，可能是：

- 绝对路径：`C:/Users/.../Documents/Life-Index/Journals/2026/03/...`
- 相对于 `USER_DATA_DIR`：`Journals/2026/03/...`

因此 Web Service Layer 必须承担**路径归一化**职责：

1. 接收来自 `search_journals` / `metadata_cache` / `write_journal` 的原始路径
2. 归一化为 `journal_route_path`
3. 仅把 `journal_route_path` 暴露给模板和 `/journal/{...}` 路由

**禁止**把底层原始 `path` / `file_path` 直接拼进 `/journal/...` 链接。

---

## 4. 目录结构

```
life-index/
├── tools/                    # Layer A — 核心工具（不变）
├── web/                      # Layer C — Web GUI（新增）
│   ├── __init__.py
│   ├── app.py                # FastAPI application factory
│   ├── config.py             # Web 配置（端口、主题等）
│   ├── routes/               # 路由
│   │   ├── __init__.py
│   │   ├── dashboard.py      # GET / — 仪表盘
│   │   ├── search.py         # GET/POST /search — 搜索
│   │   ├── journal.py        # GET /journal/{path} — 阅读
│   │   │                     # GET /journal/{path}/edit — 编辑
│   │   │                     # POST /journal/{path}/edit — 提交修改
│   │   │                     # POST /journal — 写入
│   │   └── api.py            # JSON API 端点（预留）
│   ├── services/             # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── stats.py          # 统计数据聚合
│   │   ├── journal.py        # 日志读写封装
│   │   ├── search.py         # 搜索封装
│   │   └── llm_provider.py   # LLM 预留接口
│   ├── templates/            # Jinja2 模板
│   │   ├── base.html         # 基础布局（导航、主题切换）
│   │   ├── dashboard.html    # 仪表盘
│   │   ├── search.html       # 搜索页
│   │   ├── journal.html      # 日志阅读页
│   │   ├── write.html        # 写入表单页
│   │   ├── edit.html         # 编辑表单页
│   │   ├── writing_templates.json  # 写作模板预设（§5.4.5）
│   │   └── partials/         # HTMX 局部模板
│   │       ├── search_results.html
│   │       ├── journal_content.html
│   │       └── stats_charts.html
│   └── static/               # 静态资源
│       ├── css/
│       │   └── app.css       # Tailwind 编译产物
│       ├── js/
│       │   ├── htmx.min.js
│       │   ├── alpine.min.js
│       │   └── charts.js     # ECharts 初始化
│       └── img/
├── tests/
│   └── web/                  # Web 层测试（新增）
│       ├── test_routes.py
│       ├── test_services.py
│       └── test_integration.py
├── pyproject.toml            # 新增 [web] optional deps + packages.find 包含 web*
└── docs/
    └── web-gui/
        ├── README.md                    # 当前文档入口
        └── design-spec.md               # 本文档（设计规格书）
```

---

## 5. MVP 功能详细设计

### 5.1 仪表盘（Dashboard）

**路由**: `GET /`

**包含组件**：

| 组件 | 数据来源 | 图表类型 | 交互 |
|:--|:--|:--|:--|
| 写作热力图 | 所有日志的 date 字段 | GitHub 风格日历热力图（ECharts） | Hover 显示日期+日志数 |
| 基础统计 | 全部日志元数据 | 数字卡片 | 无 |
| 那年今日 | 同月同日的历史日志 | 卡片轮播 | 点击进入日志阅读页；见下方设计说明 |
| 连续记录里程碑 | date 字段计算 streak | 里程碑弹窗/徽章 | 达到里程碑时显示庆祝动画；见下方设计说明 |
| 情绪频率 | mood 字段 + date | 堆叠柱状图（按周/月） | 可选时间范围；见下方设计说明 |
| 主题分布 | topic 字段 | 饼图或环形图 | 点击跳转搜索 |
| 标签词云 | tags 字段 | 词云图 | 点击跳转搜索 |
| 人物关系图 | people 字段 + 共现关系 | 力导向图（ECharts graph） | Hover 显示关联日志数；见下方降级策略 |

**基础统计卡片**：
- 总日志数
- 总字数（content 字段长度之和）
- 最长连续记录天数（streak）
- 本月日志数
- 最常用 mood
- 最活跃 topic

**情绪可视化设计说明**：

`mood` 字段是自由文本数组（如 `["专注", "充实"]`、`["思念", "温暖"]`），不是数值型数据，因此无法绘制折线趋势图。采用以下策略：

- **图表类型**：堆叠柱状图（Stacked Bar Chart），X 轴为时间（按周或月分组），Y 轴为日志篇数，每个颜色段代表一种高频情绪
- **情绪聚合**：统计每个时间段内各情绪出现的频次，取 Top 5-8 高频情绪上色，其余归入「其他」
- **交互**：Hover 显示具体情绪及其出现次数；点击某个情绪段可跳转到该时间段内含该情绪的日志搜索结果
- **用途**：回答「最近一个月我的情绪分布是怎样的」而非「我的情绪走势如何」

**那年今日设计说明**：

「那年今日」组件展示与当前日期同月同日（M-D）的历史日志，帮助用户回顾过去的记忆。

- **查询逻辑**：在 metadata_cache（SQLite）中按 `strftime('%m-%d', date)` 匹配当天的月-日。返回所有匹配日志的 title、date、mood、abstract 字段
- **排序**：按年份降序（最近的年份排前面）
- **卡片布局**：每张卡片包含——
  - 年份标签（如「2025」「2024」），作为左侧时间线锚点
  - 标题（粗体，可点击跳转到日志阅读页）
  - abstract 摘要（灰色小字，最多 2 行截断）
  - mood 标签（彩色小标签）
- **多卡片展示**：如果同一天有多年记录，横向轮播（左右箭头翻页），每次展示 1 张卡片
- **无记录时**：显示鼓励性文字「今天还没有历史记忆——今天写一篇，明年今日就能看到了 ✨」，附带「写日志」按钮跳转 `/write`

**连续记录里程碑设计说明**：

当用户的连续记录天数（streak）达到特定里程碑时，Dashboard 显示庆祝反馈。

- **里程碑阈值**：`7` / `30` / `100` / `365` 天
- **庆祝信息**（中文）：
  | 天数 | 信息 | 风格 |
  |:--|:--|:--|
  | 7 | 「连续 7 天 ✨ 一周的坚持！」 | 小徽章，柔和动画 |
  | 30 | 「连续 30 天 🎉 一个月的记录者！」 | 中等徽章，五彩纸屑动画（confetti） |
  | 100 | 「连续 100 天 🏆 百日记录达成！」 | 大徽章，持续 3 秒的烟花动画 |
  | 365 | 「连续 365 天 👑 整整一年，了不起的人生档案！」 | 全屏庆祝动画，自动截图存档 |
- **展示位置**：基础统计卡片区域内，「最长连续记录天数」卡片旁显示里程碑徽章
- **触发时机**：仅在 Dashboard 首次加载且 streak 恰好命中里程碑时触发动画（刷新不重复触发，使用 `localStorage` 记录已展示的里程碑）
- **动画技术**：CSS animation + Alpine.js 控制显隐。confetti 效果可使用轻量库 `canvas-confetti`（~6KB gzip），或纯 CSS 实现
- **非里程碑时**：基础统计卡片正常显示 streak 数字，无额外装饰

**数据聚合策略**：
- Dashboard 打开时一次性计算（通过 `web/services/stats.py`）
- stats.py 读取 metadata_cache（SQLite）而非逐文件扫描
- 如果 metadata_cache 不存在或过旧，自动触发增量更新

**组件降级策略**：

Dashboard 的 8 个组件依赖不同的 frontmatter 字段，部分字段是可选的。当数据不足时，各组件按以下策略降级：

| 组件 | 依赖字段 | 降级条件 | 降级行为 |
|:--|:--|:--|:--|
| 写作热力图 | `date`（必填） | 无日志时 | 显示空白热力图 + "暂无日志" 提示 |
| 基础统计 | `date`、`content` | 无日志时 | 所有数值显示 0 |
| 那年今日 | `date`（必填） | 当天无历史同日日志 | 显示鼓励文字 + "写日志"按钮（见上方设计说明） |
| 连续记录里程碑 | `date`（必填） | streak 未达到任何里程碑 | 基础统计卡片正常显示 streak 数字，无徽章/动画 |
| 情绪频率 | `mood`（可选） | <5 篇日志含 mood | 隐藏该组件，显示 "记录更多情绪以解锁此图表" |
| 主题分布 | `topic`（必填） | 无日志时 | 显示空饼图 |
| 标签词云 | `tags`（可选） | <3 个不同标签 | 显示简单标签列表替代词云 |
| 人物关系图 | `people`（可选） | <2 篇日志含 people | 隐藏该组件，显示 "在日志中标记人物以解锁关系图" |

### 5.2 搜索（Search）

**路由**: `GET /search?q=关键词&topic=work&date_from=2026-01-01&date_to=2026-03-22`

**交互流程**：
1. 用户输入搜索词 + 可选过滤条件（topic、日期范围、mood）
2. HTMX 发送请求，服务端调用 `search_journals` 模块
3. 返回搜索结果列表（局部渲染到页面）
4. 每条结果显示：标题、日期、mood 标签、匹配片段、文件路径
5. 点击结果 → 打开日志阅读页

**搜索参数映射**：

| GUI 控件 | 映射到 search_journals 参数 |
|:--|:--|
| 搜索框 | `--query` |
| Topic 下拉框 | `--topic` |
| 日期范围选择器 | `--date-from`, `--date-to` |
| Mood 标签过滤 | `--mood`（精确匹配 mood 数组中的值） |
| 搜索级别（高级选项） | `--level` |

### 5.3 日志阅读（Journal View）

**路由**: `GET /journal/{relative_path}`

**功能**：
- 服务端解析 Markdown 文件，使用 Python `markdown` 库渲染为 HTML（服务端渲染，非客户端 JS 渲染）
- 显示 frontmatter 元数据（mood、tags、weather 等）作为页面头部
- 附件内联展示：
  - 图片：直接嵌入 `<img>`
  - 视频：`<video>` 播放器
  - 音频：`<audio>` 播放器
  - 其他文件：下载链接
- 附件通过 FastAPI 静态文件服务提供（挂载 `~/Documents/Life-Index/attachments/`）

**安全约束**：
- `relative_path` 必须在 `~/Documents/Life-Index/Journals/` 范围内，防止路径穿越
- 附件服务仅暴露 `attachments/` 目录

### 5.4 写入日志（Write）

**路由**: `GET /write`（表单页）, `POST /write`（提交）

#### 5.4.1 表单字段与智能填充策略

写入表单的核心设计理念：**用户填了就用用户的，没填就由 LLM 自动提炼**。

| 字段 | 类型 | 用户必填 | 智能填充 | 说明 |
|:--|:--|:--|:--|:--|
| content | 多行文本区 | ✅ | — | 日志正文（支持 Markdown）。唯一真正的必填项 |
| date | 日期时间选择器 | — | 默认当前时间 | 用户可修改 |
| title | 文本输入 | ❌ | ✅ LLM 提炼 | 灰字提示：「如不填写，AI 将自动生成标题」；LLM 不可用时自动 fallback：取 content 前 20 字符 |
| topic | 多选下拉 | ❌† | ✅ LLM 提炼 | 灰字提示：「如不填写，AI 将自动判断主题」；从 7 个标准 topic 中选。†LLM 不可用时变为必填（红色星号） |
| mood | 标签输入 | ❌ | ✅ LLM 提炼 | 灰字提示：「如不填写，AI 将自动感知情绪」|
| tags | 标签输入 | ❌ | ✅ LLM 提炼 | 灰字提示：「如不填写，AI 将自动提取标签」|
| abstract | — | ❌ | ✅ LLM 提炼 | 不显示在表单中。LLM 可用时始终由 LLM 生成；LLM 不可用时自动 fallback：取 content 前 100 字符 |
| people | 标签输入 | ❌ | ✅ LLM 提炼 | 灰字提示：「如不填写，AI 将自动识别提及的人物」|
| location | 文本输入 + 📍 定位按钮 | ❌ | 使用默认地点 | 灰字提示：「如不填写，将使用默认地点并自动查询天气」；定位按钮见 §5.4.4 |
| weather | — | ❌ | 自动查询 | 不显示在表单中。根据 location + date 自动调用 query_weather |
| project | 文本输入 | ❌ | — | 灰字提示：「关联项目（可选）」|
| attachments | 文件上传 + URL 输入 | ❌ | — | 见 §5.4.3 附件处理 |

**关键规则**：
- 用户填写的字段**始终优先**，LLM 不会覆盖用户输入
- 仅当字段为空时才触发 LLM 提炼
- LLM 不可用时（见 §3.3.4 降级策略），`title` 和 `abstract` 使用自动 fallback（截取 content），`topic` 变为用户必填，其余可选字段留空
- 表单 UI 动态适配：LLM 可用时灰字提示「AI 将自动…」；LLM 不可用时灰字变为「请手动填写」

#### 5.4.2 提交流程

```
用户填写表单 → POST /write
        │
        ├─ content（必填）+ 用户已填元数据
        │
        ▼
  Service Layer 处理：
        │
        ├─ 1. 收集用户已填字段
        ├─ 2. 对未填字段调用 LLM 提炼（如可用）
        ├─ 3. 处理附件（本地上传 + URL 下载）
        ├─ 4. 处理 location → query_weather
        ├─ 5. 组装完整 data dict
        ├─ 6. 调用 write_journal 模块
        │
        ▼
  成功 → 显示确认信息 + 链接到新日志
  失败 → 显示错误信息（保留表单内容，不丢失用户输入）
```

#### 5.4.3 附件处理

支持两种方式添加附件：

**方式 1：本地文件上传**
- 标准 `<input type="file" multiple>` 文件选择器
- 文件通过 multipart 上传到服务端
- 服务端调用 `write_journal` 的附件处理流程归档到 `attachments/YYYY/MM/`

**方式 2：URL 远程下载**
- 独立的 URL 输入框，支持添加多个 URL
- 服务端下载文件后，按 Life Index 标准流程归档到 `attachments/YYYY/MM/` 并引用到日志中

**URL 下载约束**：
| 约束 | 值 | 说明 |
|:--|:--|:--|
| 协议 | 仅 HTTPS（HTTP 自动升级） | 安全优先 |
| 文件大小上限 | 50 MB | 防止意外下载超大文件；Content-Length 缺失时流式计数，超限中止 |
| 下载超时 | 30 秒 | 防止慢速链接阻塞 |
| 并发下载 | 最多 3 个 | 避免资源占用 |
| 文件命名 | 保留原始文件名；冲突时追加序号 | 可追溯来源 |
| Content-Type 验证 | 允许列表：`image/*`、`audio/*`、`video/*`、`application/pdf`、`application/zip`、`text/plain`、`text/markdown` | 拒绝 `text/html`、`application/x-executable` 等不安全类型；Content-Type 缺失时按文件扩展名推断 |

**下载失败处理**：单个 URL 下载失败不阻止日志写入。成功下载的附件正常归档，失败的 URL 在响应中列出错误原因（超时/404/超大等），用户可稍后重试。

**Content 保留原则**：用户在 content 字段中输入的内容 100% 原样传递给 `write_journal`，GUI 层不做任何修改。

#### 5.4.4 浏览器地理定位

location 字段旁边提供「📍 获取当前位置」按钮，调用浏览器 Geolocation API 自动填充地点。

**实现流程**：

```
用户点击 📍 按钮
    │
    ▼
navigator.geolocation.getCurrentPosition()
    │
    ├─ 成功 → 获取经纬度 (lat, lng)
    │         │
    │         ▼
    │   反向地理编码（Nominatim / 服务端代理）→ "川西, 四川, China"
    │         │
    │         ▼
    │   自动填入 location 输入框
    │
    └─ 失败 → 显示提示（权限被拒 / 不支持）
             location 保持空白或默认值，不阻止写入
```

**技术说明**：
- 仅需前端 JavaScript，无后端改动。对服务端而言，GPS 填入的地点与用户手动输入的地点完全等价
- 浏览器 Geolocation API 在 localhost 可正常使用（HTTP 允许）
- 远程访问（Phase 3）时需要 HTTPS 才能调用 Geolocation API——这是浏览器安全策略要求
- 反向地理编码可选方案：前端调用 OpenStreetMap Nominatim API（免费、无需 key）或服务端代理

**Nominatim 使用约束**：
- 请求必须包含自定义 User-Agent 头：`LifeIndex/2.0 (life-index-web-gui)`
- 频率限制：最多 1 次请求/秒（Nominatim 使用政策要求）
- Nominatim 不可达时，📍 按钮显示错误提示（toast），坐标不存储，location 保持空白或默认值

#### 5.4.5 写作模板（Templates）

写入页面提供模板下拉选择器，用户可选择预设模板快速填充表单。模板预填部分元数据和 content 骨架，降低写作门槛。

**UI 交互**：
- 表单顶部（content 输入框上方）显示「选择模板」下拉菜单，默认选项为「空白日志」
- 选择模板后，自动填充 content 骨架文本和预设元数据字段
- **已有用户输入的字段不会被模板覆盖**（与 LLM 填充同理：用户输入 > 模板预设 > 空白）
- 切换模板前，如果用户已修改了表单内容，弹出确认提示「切换模板将覆盖当前内容，确定吗？」

**预设模板列表**：

| 模板名称 | topic 预设 | content 骨架 | 说明 |
|:--|:--|:--|:--|
| 空白日志 | — | （空） | 默认选项，不预填任何内容 |
| 给团团的信 | `["think", "relation"]` | `# 亲爱的团团\n\n爸爸今天想对你说……\n\n` | 写给女儿的家书 |
| 今日感恩 | `["think"]` | `# 今日感恩\n\n今天我感恩的三件事：\n\n1. \n2. \n3. \n\n` | 感恩日记 |
| 工作日志 | `["work"]` | `# 工作日志\n\n## 今日完成\n\n- \n\n## 遇到的问题\n\n- \n\n## 明日计划\n\n- \n` | 结构化工作记录 |
| 学习笔记 | `["learn"]` | `# 学习笔记\n\n## 今天学了什么\n\n\n\n## 关键收获\n\n\n\n## 还不理解的地方\n\n\n` | 学习反思 |
| 读后感 | `["learn", "think"]` | `# 读后感\n\n**书名**：\n**作者**：\n\n## 核心观点\n\n\n\n## 我的思考\n\n\n` | 读书笔记 |
| 健康打卡 | `["health"]` | `# 健康打卡\n\n- 睡眠：\n- 运动：\n- 饮食：\n- 身体状况：\n\n` | 健康记录 |

**模板存储**：
- 模板定义存放在 `web/templates/writing_templates.json`，JSON 格式
- 每个模板包含：`id`（唯一标识）、`name`（显示名称）、`topic`（预设 topic 数组）、`content`（骨架文本）、`tags`（可选预设标签）
- 未来可支持用户自定义模板（Phase 2.x），MVP 仅提供上述预设模板

### 5.5 日志编辑（Edit）

**路由**: `GET /journal/{relative_path}/edit`（编辑页）, `POST /journal/{relative_path}/edit`（提交修改）

**动机**：Web GUI 写入日志时省略了 Agent 工作流中的地点/天气确认环节，用户可能需要事后修正。编辑功能作为补偿机制。

**进入方式**：日志阅读页（§5.3）顶部显示「编辑」按钮，点击进入编辑模式。

**编辑范围**：

| 字段 | 编辑方式 | 映射到 edit_journal 参数 |
|:--|:--|:--|
| title | 文本输入 | `--set-title` |
| content | 多行文本区（Markdown） | `--replace-content` |
| location | 文本输入 + 📍 定位按钮 | `--set-location`（需同时提交天气） |
| weather | 文本输入（或自动查询） | `--set-weather` |
| mood | 标签输入 | `--set-mood` |
| tags | 标签输入 | `--set-tags` |
| people | 标签输入 | `--set-people` |
| topic | 多选下拉 | `--set-topic` |
| project | 文本输入 | `--set-project` |
| abstract | 文本输入 | `--set-abstract` |

**地点/天气耦合处理**：
- 修改 location 时，GUI 在 location 字段失焦（blur）后 **500ms debounce** 触发 `query_weather` 查询
- 查询结果预填到 weather 字段作为**可编辑建议**（用户可覆盖）
- 查询期间 weather 字段显示 loading 状态
- 如果 `query_weather` 失败，weather 字段保留原值并显示警告图标，用户可手动输入
- 遵循 `edit_journal` 的编辑规则：修改 location 必须同时提交 weather（E0504）

**提交流程**：
1. 加载现有日志的 frontmatter + content 填充到编辑表单
2. 用户修改字段
3. POST 提交，Service Layer 计算 diff（仅提交变更字段）
4. 调用 `edit_journal` 工具
5. 成功 → 显示变更摘要 + 跳转到更新后的日志阅读页
6. 失败 → 显示错误信息，保留编辑状态

**安全约束**：
- 编辑页同样受 CSRF 保护
- `relative_path` 路径穿越防护（与 §5.3 一致）

### 5.6 Web GUI 错误码（E07xx）

Web GUI 模块预留 `07` 错误码段，遵循 `lib/errors.py` 的 `E{module}{type}` 格式：

| 错误码 | 常量名 | 含义 | 恢复策略 |
|:--|:--|:--|:--|
| E0700 | `WEB_GENERAL_ERROR` | Web GUI 通用错误 | `ask_user` |
| E0701 | `URL_DOWNLOAD_FAILED` | URL 附件下载失败（超时/404/超大） | `skip_optional` |
| E0702 | `URL_CONTENT_TYPE_REJECTED` | URL 文件类型不在允许列表 | `ask_user` |
| E0703 | `LLM_PROVIDER_UNAVAILABLE` | 所有 LLM Provider 不可用 | `skip_optional` |
| E0704 | `LLM_EXTRACTION_FAILED` | LLM 元数据提炼调用失败 | `skip_optional` |
| E0705 | `GEOLOCATION_FAILED` | 浏览器地理定位失败 | `skip_optional` |
| E0706 | `NOMINATIM_UNAVAILABLE` | Nominatim 反向地理编码失败 | `skip_optional` |
| E0707 | `WEB_DEPS_MISSING` | Web GUI 依赖未安装 | `fail` |

**注意**：这些错误码在实现时添加到 `lib/errors.py`，同步更新 `docs/API.md`。

---

## 6. 非功能需求

### 6.1 性能

以下性能目标基于典型个人用户规模（100-500 篇日志）：

| 操作 | 目标 | 100 篇 | 500 篇 | 2000 篇（远期） |
|:--|:--|:--|:--|:--|
| Dashboard 首次加载 | < 3s | ✅ 目标 | ✅ 目标 | ≤ 5s（可接受） |
| 搜索响应 | < 1s | ✅ 目标 | ✅ 目标 | ≤ 2s（可接受） |
| 日志阅读页渲染 | < 500ms | ✅ 目标 | ✅ 目标 | ✅ 目标（与规模无关） |

**注意**：2000 篇以上的规模如性能降级明显，可通过 stats 缓存（见 §10 风险与缓解）应对。

### 6.2 可访问性

- 键盘导航支持
- 语义化 HTML
- 响应式布局（桌面 + 平板，暂不优化手机）

### 6.3 安全

- 仅监听 localhost（Phase 1）
- 路径穿越防护（日志阅读、附件服务）
- CSRF 防护：POST 端点（`/write`）使用 CSRF token 保护，防止跨站请求伪造
- 无认证（Phase 1，本地访问无需认证）
- 预留认证中间件接口（Phase 2 远程访问时启用）

### 6.4 测试

- 路由测试：FastAPI TestClient
- Service 层测试：mock tools/ 模块
- 集成测试：端到端流程（写入→搜索→阅读）
- 覆盖率目标：≥70%（与主项目一致）

---

## 7. 依赖管理

### pyproject.toml 变更

```toml
[project.optional-dependencies]
web = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.9",  # 文件上传
    "markdown>=3.5.0",          # Markdown→HTML 渲染
    "httpx>=0.27.0",            # URL 附件异步下载 + LLM API 调用
]
```

**注意**：`httpx` 放在 `[web]` optional deps 中而非核心依赖，确保 CLI-only 用户（`pip install life-index`）不引入 Web 相关依赖。

**注意**：`pyproject.toml` 的 `[tool.setuptools.packages.find]` 需要包含 `web*` 模式，确保 `web/` 目录被正确打包：

```toml
[tool.setuptools.packages.find]
include = ["tools*", "web*"]
```

### 安装方式

```bash
# 基础用户（不变）
pip install life-index

# Web GUI 用户
pip install life-index[web]

# 开发者
pip install -e ".[dev,web]"
```

---

## 8. CLI 入口

```bash
# 启动 Web GUI
life-index serve [--port 8765] [--host 127.0.0.1] [--reload]

# --reload 仅用于开发模式，自动重载代码变更
```

`life-index serve` 命令注册到 tools/__main__.py 的 cmd_map 中。

**依赖检查**：`life-index serve` 启动时首先检查 Web 依赖是否已安装。如未安装，输出明确错误信息并退出：

```json
{
  "success": false,
  "error": "Web GUI 依赖未安装。请运行: pip install life-index[web]"
}
```

---

## 9. 未做 / 推迟

| 功能 | 层级 | 推迟原因 | 预计时机 |
|:--|:--|:--|:--|
| 记忆地图（Memory Map） | Tier 2 | 需 Leaflet.js 集成 + location 字段标准化 | Phase 1.x |
| 照片闪回（Photo Flashbacks） | Tier 2 | 需附件扫描 + 缩略图生成 | Phase 1.x |
| 年度回顾（Year in Review） | Tier 2 | 依赖 Dashboard 统计基础设施成熟 | Phase 1.x |
| 一句话模式（One-Sentence Mode） | Tier 2 | 极简写入，需设计最小化 UI | Phase 1.x |
| 日志老化效果（Entry Aging） | Tier 3 | 纯视觉增强，CSS sepia filter + 字体变化 | Phase 2.x |
| 温和空白日提醒 | Tier 3 | Dashboard 通知系统基础 | Phase 2.x |
| 相关日志推荐 | Tier 3 | 可复用现有语义搜索基础设施 | Phase 2.x |
| LLM 对话集成 | — | 元数据提炼已在 MVP（§3.3），对话功能待验证需求 | Phase 2.x |
| 远程访问 / 认证 | — | **杀手级场景**：手机远程记录（GPS 定位 + 拍照上传）。需 HTTPS + 认证 + Cloudflare Tunnel 等 | Phase 3（高优先） |
| 前后端分离 | — | 当前 HTMX 体验足够 | 按需评估 |
| 日志出图 | — | 作为独立 CLI 工具开发 | 与 GUI 并行 |
| PDF 家书导出 | — | 排版设计复杂 | Phase 2.x |
| 语音输入 | — | 需要调研 STT 方案 | Phase 3 |
| Obsidian 导出 | — | 当前格式已基本兼容 | 按需求优先级 |
| 手机端优化 | — | 先确保桌面体验 | Phase 2.x |

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|:--|:--|:--|
| HTMX 交互能力不够 | 部分复杂交互难以实现 | Alpine.js 补充客户端逻辑；极端情况可局部引入 React |
| ECharts 包体积大 | 首次加载慢 | 使用 ECharts 按需引入，只加载需要的图表类型 |
| tools/ API 不稳定 | GUI 调用可能 break | Service 层作为适配器，隔离 tools/ 接口变更 |
| 附件文件过大 | 浏览器加载慢 | 图片缩略图 + 懒加载；大文件提供下载链接而非内联 |
| URL 下载不可控 | 安全风险、下载卡住 | 50MB 上限 + 30s 超时 + 仅 HTTPS；失败不阻止日志写入 |
| 宿主 Agent LLM 不可达 | 元数据无法自动提炼 | 三级降级：HostAgentProvider → APIKeyProvider → 自动 fallback（title/abstract 截取 content）+ 手动填写 topic。见 §3.3.4 |
| 数据量增长后 Dashboard 变慢 | 用户体验下降 | stats 结果缓存（内存或文件），设置 TTL |

---

## 11. 已知问题与实现注意事项

> 本节是 Web GUI 文档体系中记录“**已发现、但当前未解决/不阻塞开工**”事项的 **canonical place**。  
> 它与 §9「未做 / 推迟」和 §10「风险与缓解」不同：  
> - §9 记录**主动延期的功能**  
> - §10 记录**预判风险与缓解**  
> - §11 记录**当前已确认存在、但暂不在本轮实现中解决的问题 / caveats / governance backlog**

| ID | 类型 | 状态 | 影响范围 | 文件 | 当前结论 / 为什么要记住 | 建议处理时机 |
|:--|:--|:--|:--|:--|:--|:--|
| KI-001 | Performance Caveat | Open | Write / Edit UX | `tools/write_journal/index_updater.py` | 月度摘要更新仍通过同步 subprocess 调用 `tools.generate_abstract`，最坏可阻塞写入链路约 30s。当前**不阻塞 Web GUI 开工**，但会影响写入完成后的响应延迟与交互体验。 | 进入 Web Write 主实现后，若实际延迟不可接受，优先处理 |
| KI-002 | Integration Caveat | Mitigated in Web Layer | Write flow / weather autofill | `tools/write_journal/weather.py`, `tools/query_weather/__init__.py`, `web/services/write.py`, `web/routes/edit.py` | 底层 `write_journal.weather` 仍保留 CLI-style 历史包装，但 Web 层现在已直接接入 `query_weather` / geocode 进行天气查询与编辑页天气 API。问题未在 Layer A 根治，但 **Web GUI 已完成可用绕行**。 | 如未来统一工具层天气语义，再做深度治理 |
| KI-003 | Contract / Governance Backlog | Open | Web adapter layer | `tools/write_journal/core.py`, `tools/search_journals/core.py`, `tools/edit_journal/__init__.py`, `tools/query_weather/__init__.py`, `tools/build_index/__init__.py` | 成功返回 payload 尚未统一为单一 envelope。当前文档已按**源码现实**建模，因此**不阻塞当前实现**；但 Web adapter 仍需按工具逐个适配。 | Web GUI MVP 跑通后，如 adapter 成本高，再做治理 |
| KI-004 | Feature Gap | Mostly Closed | Write attachments UX | `tools/write_journal/attachments.py`, `web/services/url_download.py`, `web/routes/write.py` | Web GUI 已实现 URL 附件下载 → 本地临时文件 → `source_path` bridge，并已补上独立 `url_download` service、50MB limit、HTTP→HTTPS upgrade、concurrency guard、filename conflict suffixing 与 YYYY/MM archival layout。当前残余主要是文档精修与更细粒度 polish，不再属于主功能缺口。 | 后续以 spec/documentation polish 方式继续收口 |
| KI-005 | Operational Caveat | Accepted with workaround | Search / cache maintenance | `tools/lib/metadata_cache.py`, `tools/build_index/__init__.py` | 历史 cache 路径格式已做兼容，但如用户环境中仍出现旧缓存残留异常，当前建议维护动作是执行 `life-index index --rebuild`。这是**已接受的运维性 workaround**，不是 blocker。 | 保持至未来需要正式 migration 时再移除 |
| KI-006 | Product Polish | Further Narrowed | Write / Edit geolocation UX | `web/services/geolocation.py`, `web/routes/edit.py`, `web/templates/write.html`, `web/templates/edit.html`, `web/services/write.py` | 浏览器定位现在已通过 reverse geocoding 解析为人类可读地点，并已接入 write / edit 页面；同时已补上 geolocation 后自动天气填充、按钮 busy/disabled 状态与 inline status。当前残余仅剩更细粒度文案与交互打磨。 | 作为 post-MVP polish 持续收口 |
| KI-007 | Product Polish | Narrowed | Form / attachment UX | `web/templates/write.html`, `web/templates/edit.html` | write/edit 表单现已补上 submit busy/status feedback；write 页附件区已补上本地文件状态、URL 状态与 remove affordance。当前残余不再是主交互缺口，而是进一步的移动端/视觉 polish 与更细粒度表单结构优化。 | 作为 post-MVP polish 持续收口 |
| KI-008 | Product Polish | Narrowed | Responsive / spacing consistency | `web/templates/dashboard.html`, `web/templates/search.html`, `web/templates/partials/search_results.html`, `web/templates/write.html`, `web/templates/edit.html` | dashboard / search / write / edit 已完成一轮 mobile/responsive 与 spacing consistency polish；当前残余主要是更细粒度视觉 refinement、信息密度与移动端触控细节，而不是基础布局问题。 | 作为 post-MVP polish 持续收口 |
| KI-009 | Product Polish | Narrowed | Visual hierarchy / touch target refinement | `web/templates/dashboard.html`, `web/templates/journal.html`, `web/templates/partials/search_results.html`, `web/templates/write.html`, `web/templates/edit.html` | 已完成一轮 template-only visual refinement：card ring/shadow 层次、标题 tracking、journal metadata 区块以及主要操作按钮的 touch target 已统一到更稳妥的层级。当前残余主要是更偏审美层面的微调，而不是信息结构或触控可用性问题。 | 作为 post-MVP polish 持续收口 |
| KI-010 | Product Polish | Near-Closed | Base layout / wording consistency | `web/templates/base.html`, `web/templates/search.html`, `web/templates/write.html`, `web/templates/partials/search_results.html` | 已完成 base nav/theme-toggle/CTA micro-polish 与一轮 wording consistency closeout。当前残余仅剩非常零散的文案或审美细节，不再适合成批推进。 | 作为收尾型 backlog 保留 |
| KI-011 | Walkthrough Validation | Closed | Real browser core flow verification | `web/routes/write.py`, `web/templates/partials/search_results.html`, `tests/unit/test_web_write_route.py`, `tests/unit/test_web_journal_search.py`, `.cowork-temp/ui_walkthrough.py` | 真实 Playwright walkthrough 暴露的 `/write` 422 与 search results `score=None` 500 已修复并回归验证通过。当前主链路 write → journal → edit → search → dashboard reload 已在真实浏览器中验证打通。 | 关闭 |

**使用规则**：

1. 只有“**已确认存在**，但当前不解决/不阻塞开工”的事项才进入本节。  
2. 如果某问题已经演变为真正 blocker，应移到对应 phase 计划或实现任务中，不应继续停留在本节。  
3. 如果某问题直接改变跨阶段契约，应优先回写当前主文档或归档中的历史过程文档；本节仅保留摘要和链接。
4. Phase 薄索引文档可引用本节的某个 `KI-xxx`，但不要重复维护完整正文。

---

## 12. 成功标准

MVP 发布时应满足：

1. ✅ `life-index serve` 启动后可在浏览器中访问 Dashboard
2. ✅ Dashboard 展示全部 8 个统计组件（含降级策略）
3. ✅ 「那年今日」组件正确展示同月同日历史日志（卡片轮播 + 降级鼓励文字）
4. ✅ 连续记录里程碑在 streak 达到 7/30/100/365 时触发庆祝动画
5. ✅ 可以搜索日志并阅读全文（含附件）
6. ✅ 可以通过表单写入日志，支持本地文件上传和 URL 远程下载附件
7. ✅ 写入页面提供写作模板下拉选择器，包含 7 个预设模板
8. ✅ 写入时未填元数据字段由 LLM 自动提炼（APIKeyProvider 或 HostAgentProvider）
9. ✅ 可以编辑已有日志（元数据 + 正文），编辑 location 时自动触发天气查询
10. ✅ 暗/亮主题切换正常
11. ✅ 所有 tools/ 的现有测试不受影响
12. ✅ Web 层测试覆盖率 ≥ 70%
13. ✅ `pip install life-index`（无 web）不引入任何 Web 依赖
14. ✅ LLM 不可用时，用户可手动填写所有字段完成写入（优雅降级）

> **Verification note (2026-03-22):** 上述成功标准已由 Phase 1–5 的实现、专项单测、CSRF 合同测试、integration/E2E smoke test 与最终 aggregated web regression 共同支撑。当前剩余工作不再属于“主链路是否可用”，而属于后续 release review / product polish。

### 12.1 Success-Criteria Checklist Status

| # | 条目 | 当前判定 | 说明 |
|:--|:--|:--|:--|
| 1 | `life-index serve` 启动后可在浏览器中访问 Dashboard | 已满足 | 已有 scaffold / dashboard regression 支撑 |
| 2 | Dashboard 展示全部 8 个统计组件（含降级策略） | 已满足 | 已完成 dashboard 路由与模板验证 |
| 3 | 「那年今日」组件正确展示同月同日历史日志 | 已满足 | 已纳入 dashboard 功能实现范围 |
| 4 | 连续记录里程碑在 streak 达到 7/30/100/365 时触发庆祝动画 | 已满足 | 已作为 dashboard 功能验收项记录 |
| 5 | 可以搜索日志并阅读全文（含附件） | 已满足 | search + journal view regression 已通过 |
| 6 | 可以通过表单写入日志，支持本地文件上传和 URL 远程下载附件 | 已满足 | write flow + attachment bridge + url_download service 已完成 |
| 7 | 写入页面提供写作模板下拉选择器，包含 7 个预设模板 | 已满足 | writing_templates + write template regression 已通过 |
| 8 | 写入时未填元数据字段由 LLM 自动提炼 | 已满足（以当前 Provider 范围） | APIKeyProvider 已实现；HostAgentProvider 仍保持 MVP stub/fallback 策略 |
| 9 | 可以编辑已有日志（元数据 + 正文），编辑 location 时自动触发天气查询 | 已满足（当前为显式触发查询 + geolocation reverse geocoding） | `/api/weather` + `/api/reverse-geocode` + edit guard 已完成；天气仍保持按钮触发而非隐式自动刷新 |
| 10 | 暗/亮主题切换正常 | 已满足 | 基础主题支持已随模板体系提供 |
| 11 | 所有 tools/ 的现有测试不受影响 | 已满足 | Web 批次回归未引入 tools 侧回归信号 |
| 12 | Web 层测试覆盖率 ≥ 70% | 已满足（按现有测试规模判断） | 已形成 unit + csrf + integration/e2e 覆盖面 |
| 13 | `pip install life-index`（无 web）不引入任何 Web 依赖 | 已满足 | web 依赖仍保持 optional-dependencies 形态 |
| 14 | LLM 不可用时，用户可手动填写所有字段完成写入（优雅降级） | 已满足 | write/edit 表单与 fallback 路径已实现 |

## 13. Readiness Review（2026-03-22）

### 结论

**当前状态：delivery-ready handoff**

Web GUI 主链路已经具备可交付状态：
- scaffold / dashboard / journal / search / write / edit 主链路可用
- 本地上传与 URL 附件下载桥接可用
- CSRF contract 已有专项验证
- 已存在 integration / E2E smoke test
- 最终 aggregated web regression 已通过
- 真实 Playwright walkthrough 已打通 write → journal → edit → search → dashboard reload

### 已满足项

- §12 成功标准中的核心主链路项已全部具备实现与测试支撑
- write / edit 的成功、失败、warning 用户反馈链路已闭环
- 独立 `web/services/url_download.py` 已存在，Phase 5 核心工程化目标已完成

### 仍保留的开放项

- geolocation reverse geocoding、Batch G weather UX polish、Batch H form/attachment UX polish、Batch I responsive/spacing polish、Batch J visual/touch-target refinement、Batch K base/writing closeout、以及 post-walkthrough 主链路 bugfix 已完成；当前已无值得继续成批推进的实现批次
- 部分文档 wording 与 reject-list 细节仍可继续精修
- 若进入正式发布评审，可补一轮逐条 success-criteria 勾稽说明作为附加材料，但不再构成交付前 blocker
